#!/usr/bin/env python3
"""Interactive Tkinter front-end for run_com.py: runs a real MSX-DOS .COM
binary on the z80.py CPU (via cpm_bdos.py) in a background thread, and
renders the ACTUAL TMS9918 VRAM contents (name/pattern/color tables, decoded
per the real chip's addressing rules for Text1/SCREEN0 and Graphic2/SCREEN2)
to a live Tkinter canvas, with real keyboard input fed back into the
emulated console/BIOS key routines. This is what lets a program like
ABRETELA.COM/LOCADORA.COM -- which draws its screen by bit-banging VDP ports
exactly like the real MSX hardware driver did -- actually be seen and used,
without pretending to know what it draws ahead of time.

Usage:
    python msx_gui_runner.py VIDEOLOC.DSK ABRETELA.COM LOCADORA.COM
    python msx_gui_runner.py "dBASE II.dsk" DBASE.COM
"""
from __future__ import annotations

import argparse
import queue
import sys
import threading
import tkinter as tk

from dskimage import DskImage
from cpm_bdos import CpmHost, CpmError, ProgramExit, Terminal
from msx_vdp_ports import VdpPorts

SCALE = 3
SCREEN_W, SCREEN_H = 256, 192

MSX_COLORS = {
    0: "#000000", 1: "#000000", 2: "#3EB849", 3: "#74D07D",
    4: "#5955E0", 5: "#8076F1", 6: "#B95E51", 7: "#65DBEF",
    8: "#DB6559", 9: "#FF897D", 10: "#CCC35E", 11: "#DED087",
    12: "#3AA241", 13: "#B766B5", 14: "#CCCCCC", 15: "#FFFFFF",
}


class QueueTerminal(Terminal):
    """A console that reads keystrokes from a Tkinter-fed queue instead of
    the real OS console, so BDOS conin/BIOS CHGET see the keys typed into
    the display window. Text-mode console output (BDOS function 2/9, used
    by dBASE/COBOL-family programs) still goes to the launching terminal
    via the inherited ADM-3A-to-ANSI translation; VIDEOLOC's own suite
    draws through the VDP ports instead, which the canvas renders."""

    def __init__(self):
        super().__init__(interactive=False)
        self.keys: "queue.Queue[int]" = queue.Queue()

    def push_key(self, code: int) -> None:
        self.keys.put(code)

    def status(self) -> bool:
        return not self.keys.empty()

    def in_char(self) -> int:
        try:
            return self.keys.get(timeout=5.0)
        except queue.Empty:
            return 0x1A

    def readline(self, maxlen: int) -> str:
        chars = []
        while True:
            c = self.in_char()
            if c in (0x0D, 0x0A, 0x1A):
                break
            chars.append(chr(c))
        return "".join(chars)[:maxlen]


class CpuThread(threading.Thread):
    def __init__(self, dsk_path: str, com_names: list[str], terminal: QueueTerminal,
                 vdp_ports: VdpPorts, status_cb):
        super().__init__(daemon=True)
        self.dsk_path = dsk_path
        self.com_names = com_names
        self.terminal = terminal
        self.vdp_ports = vdp_ports
        self.status_cb = status_cb

    def run(self) -> None:
        drive = DskImage.load(self.dsk_path)
        host = CpmHost({"A": drive}, terminal=self.terminal, vdp_ports=self.vdp_ports)
        for name in self.com_names:
            if not drive.exists(name):
                self.status_cb(f"'{name}' not found on disk")
                return
            code = drive.read_file(name)
            host.load_com(code)
            self.status_cb(f"running {name} ({len(code)} bytes)...")
            try:
                host.run(max_steps=2_000_000_000)
            except CpmError as e:
                self.status_cb(f"{name} stopped: {e}")
                return
        self.status_cb("all programs finished")


def decode_frame(vdp) -> list[list[int]]:
    """Decode the current VRAM into a 256x192 grid of MSX color indices,
    following real TMS9918 addressing for Text1 (SCREEN0) or Graphic2
    (SCREEN2) -- whichever the register bits currently select."""
    r0, r1 = vdp.registers[0], vdp.registers[1]
    m1 = bool(r1 & 0x10)
    m2 = bool(r0 & 0x02)
    m3 = bool(r1 & 0x08)
    frame = [[4] * SCREEN_W for _ in range(SCREEN_H)]

    if m1 and not m2 and not m3:
        # Text1 / SCREEN 0: 40x24 chars, 6x8 visible cell, single fg/bg pair.
        cols, rows = 40, 24
        nt_base = (vdp.registers[2] & 0x0F) << 10
        pg_base = (vdp.registers[4] & 0x07) << 11
        fg = (vdp.registers[7] >> 4) & 0x0F
        bg = vdp.registers[7] & 0x0F
        cell_w = 6
        for r in range(rows):
            for c in range(cols):
                code = vdp.read_vram(nt_base + r * cols + c)
                for py in range(8):
                    pat = vdp.read_vram(pg_base + code * 8 + py)
                    for px in range(cell_w):
                        bit = (pat >> (7 - px)) & 1
                        y = r * 8 + py
                        x = c * cell_w + px
                        if y < SCREEN_H and x < SCREEN_W:
                            frame[y][x] = fg if bit else bg
        return frame

    # Default to Graphic2 / SCREEN 2 (256x192 bitmap, 3 pattern/color pages).
    nt_base = (vdp.registers[2] & 0x0F) << 10
    col_base = (vdp.registers[3] & 0x80) << 6
    pg_base = (vdp.registers[4] & 0x04) << 11
    for row in range(SCREEN_H):
        char_row = row // 8
        fine_row = row % 8
        third = char_row // 8
        for col8 in range(32):
            name_index = char_row * 32 + col8
            pattern_num = vdp.read_vram(nt_base + name_index)
            addr = third * 2048 + pattern_num * 8 + fine_row
            pat = vdp.read_vram(pg_base + addr)
            colb = vdp.read_vram(col_base + addr)
            fg = (colb >> 4) & 0x0F
            bg = colb & 0x0F
            for px in range(8):
                bit = (pat >> (7 - px)) & 1
                frame[row][col8 * 8 + px] = fg if bit else bg
    return frame


class DisplayWindow:
    def __init__(self, terminal: QueueTerminal, vdp_ports: VdpPorts, title: str):
        self.terminal = terminal
        self.vdp_ports = vdp_ports
        self.root = tk.Tk()
        self.root.title(title)
        self.canvas = tk.Canvas(self.root, width=SCREEN_W * SCALE, height=SCREEN_H * SCALE,
                                 highlightthickness=0, bg="#000000")
        self.canvas.pack()
        self.status_var = tk.StringVar(value="starting...")
        tk.Label(self.root, textvariable=self.status_var, anchor="w").pack(fill="x")
        self.root.bind("<KeyPress>", self._on_key)
        self._img_items: list = []
        self._last_frame = None
        self._schedule_render()

    def set_status(self, text: str) -> None:
        self.status_var.set(text)

    def _on_key(self, event) -> None:
        ch = event.char
        keymap = {"Return": 0x0D, "BackSpace": 0x08, "Escape": 0x1B,
                  "Up": 0x1E, "Down": 0x1F, "Left": 0x1D, "Right": 0x1C, "Tab": 0x09}
        if event.keysym in keymap:
            self.terminal.push_key(keymap[event.keysym])
        elif ch:
            self.terminal.push_key(ord(ch) & 0xFF)

    def _schedule_render(self) -> None:
        self.render()
        self.root.after(80, self._schedule_render)

    def render(self) -> None:
        frame = decode_frame(self.vdp_ports.vdp)
        self.canvas.delete("all")
        # Coalesce runs of same-color pixels per row to keep draw calls sane.
        for y in range(SCREEN_H):
            row = frame[y]
            x = 0
            while x < SCREEN_W:
                color = row[x]
                x2 = x + 1
                while x2 < SCREEN_W and row[x2] == color:
                    x2 += 1
                self.canvas.create_rectangle(
                    x * SCALE, y * SCALE, x2 * SCALE, (y + 1) * SCALE,
                    fill=MSX_COLORS.get(color, "#000000"), outline="")
                x = x2

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dsk")
    ap.add_argument("com", nargs="+", help="one or more .COM files to run in sequence, same VDP/session")
    args = ap.parse_args()

    terminal = QueueTerminal()
    vdp_ports = VdpPorts()
    window = DisplayWindow(terminal, vdp_ports, title=f"{args.dsk} - {' -> '.join(args.com)}")

    cpu_thread = CpuThread(args.dsk, args.com, terminal, vdp_ports, window.set_status)
    cpu_thread.start()
    window.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
