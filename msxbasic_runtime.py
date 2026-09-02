"""
MSX BASIC / BIOS compatibility layer in Python
==============================================

Port arquitetural baseado em:
- msxbasic.asm
- msxbasic.def
- msxhook.def
- MSXFONT.BIN

Objetivo:
    Reproduzir em Python as principais abstrações expostas pelo BIOS/MSX-BASIC:
    RAM, VRAM, VDP, PSG, console, teclado, joystick, hooks e fonte 8x8.

Isto NÃO é um emulador Z80 nem uma tradução linha-a-linha dos ~349 KB de assembly.
É uma reimplementação Python da interface lógica documentada pelo código-fonte.

Execução:
    python msxbasic_runtime.py

Teclas na janela demo:
    ESC - sair
    setas - joystick
    espaço - trigger

A classe MSXMachine pode ser reutilizada pelos ports de programas MSX-BASIC.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import tkinter as tk
import time


RAM_SIZE = 0x10000
VRAM_SIZE = 0x4000
VDP_REGS = 8
PSG_REGS = 16

MSX_COLORS = {
    0: "#000000", 1: "#000000", 2: "#3EB849", 3: "#74D07D",
    4: "#5955E0", 5: "#8076F1", 6: "#B95E51", 7: "#65DBEF",
    8: "#DB6559", 9: "#FF897D", 10: "#CCC35E", 11: "#DED087",
    12: "#3AA241", 13: "#B766B5", 14: "#CCCCCC", 15: "#FFFFFF",
}

# Endereços principais da work area do MSX-BASIC.
USRTAB = 0xF39A
LINL40 = 0xF3AE
LINL32 = 0xF3AF
LINLEN = 0xF3B0
CRTCNT = 0xF3B1
FORCLR = 0xF3E9
BAKCLR = 0xF3EA
BDRCLR = 0xF3EB
JIFFY = 0xFC9E
SCRMOD = 0xFCAF
HKEYI = 0xFD9A
HTIMI = 0xFD9F


class MSXMemory:
    def __init__(self):
        self.ram = bytearray(RAM_SIZE)

    def peek(self, address: int) -> int:
        return self.ram[address & 0xFFFF]

    def poke(self, address: int, value: int) -> None:
        self.ram[address & 0xFFFF] = value & 0xFF

    def peek16(self, address: int) -> int:
        lo = self.peek(address)
        hi = self.peek(address + 1)
        return lo | (hi << 8)

    def poke16(self, address: int, value: int) -> None:
        self.poke(address, value)
        self.poke(address + 1, value >> 8)


class MSXVDP:
    """TMS9918-style compatibility model for MSX1."""

    def __init__(self):
        self.vram = bytearray(VRAM_SIZE)
        self.registers = bytearray(VDP_REGS)
        self.mode = 0
        self.foreground = 15
        self.background = 4
        self.border = 4

    # RDVRM
    def read_vram(self, address: int) -> int:
        return self.vram[address & 0x3FFF]

    # WRTVRM
    def write_vram(self, address: int, value: int) -> None:
        self.vram[address & 0x3FFF] = value & 0xFF

    # FILVRM
    def fill_vram(self, address: int, value: int, length: int) -> None:
        for i in range(length):
            self.write_vram(address + i, value)

    # LDIRVM
    def ram_to_vram(self, memory: MSXMemory, ram_address: int,
                    vram_address: int, length: int) -> None:
        for i in range(length):
            self.write_vram(vram_address + i, memory.peek(ram_address + i))

    # LDIRMV
    def vram_to_ram(self, memory: MSXMemory, vram_address: int,
                    ram_address: int, length: int) -> None:
        for i in range(length):
            memory.poke(ram_address + i, self.read_vram(vram_address + i))

    # WRTVDP
    def write_register(self, register: int, value: int) -> None:
        if 0 <= register < len(self.registers):
            self.registers[register] = value & 0xFF

    # CHGMOD
    def change_mode(self, mode: int) -> None:
        if mode not in (0, 1, 2, 3):
            raise ValueError("This compatibility layer implements MSX1 SCREEN 0..3")
        self.mode = mode

    # CHGCLR
    def change_colors(self, foreground: int, background: int, border: int) -> None:
        self.foreground = foreground & 0x0F
        self.background = background & 0x0F
        self.border = border & 0x0F


class MSXPSG:
    """Estado lógico do AY-3-8910. Síntese sonora pode ser acoplada posteriormente."""

    def __init__(self):
        self.registers = bytearray(PSG_REGS)

    # WRTPSG
    def write(self, register: int, value: int) -> None:
        if 0 <= register < PSG_REGS:
            self.registers[register] = value & 0xFF

    # RDPSG
    def read(self, register: int) -> int:
        if 0 <= register < PSG_REGS:
            return self.registers[register]
        return 0

    # GICINI
    def initialize(self) -> None:
        self.registers[:] = b"\x00" * PSG_REGS


@dataclass
class HookTable:
    callbacks: dict[int, callable] = field(default_factory=dict)

    def install(self, address: int, callback) -> None:
        self.callbacks[address & 0xFFFF] = callback

    def remove(self, address: int) -> None:
        self.callbacks.pop(address & 0xFFFF, None)

    def call(self, address: int, *args, **kwargs):
        callback = self.callbacks.get(address & 0xFFFF)
        if callback is not None:
            return callback(*args, **kwargs)
        return None


class MSXFont:
    def __init__(self, data: bytes):
        if len(data) != 2048:
            raise ValueError("MSXFONT.BIN must contain 2048 bytes (256 x 8)")
        self.data = data

    def glyph(self, code: int) -> list[list[int]]:
        code &= 0xFF
        rows = self.data[code * 8: code * 8 + 8]
        return [
            [1 if row & (0x80 >> x) else 0 for x in range(8)]
            for row in rows
        ]


class MSXMachine:
    def __init__(self, font_data: bytes):
        self.memory = MSXMemory()
        self.vdp = MSXVDP()
        self.psg = MSXPSG()
        self.hooks = HookTable()
        self.font = MSXFont(font_data)

        self.cursor_x = 0
        self.cursor_y = 0
        self.width = 40
        self.rows = 24
        self.text = [[32] * self.width for _ in range(self.rows)]

        self.joystick = 0
        self.trigger = False

        self.reset_work_area()

    def reset_work_area(self):
        self.memory.poke(LINL40, 37)
        self.memory.poke(LINL32, 29)
        self.memory.poke(LINLEN, 37)
        self.memory.poke(CRTCNT, 24)
        self.memory.poke(FORCLR, 15)
        self.memory.poke(BAKCLR, 4)
        self.memory.poke(BDRCLR, 4)
        self.memory.poke(SCRMOD, 0)
        self.memory.poke16(JIFFY, 0)

    # CHGMOD
    def screen(self, mode: int):
        self.vdp.change_mode(mode)
        self.memory.poke(SCRMOD, mode)
        if mode == 0:
            self.width = 40
        elif mode == 1:
            self.width = 32
        else:
            self.width = 32
        self.text = [[32] * self.width for _ in range(self.rows)]
        self.cursor_x = self.cursor_y = 0

    # CHGCLR
    def color(self, foreground: int, background: int, border: int | None = None):
        if border is None:
            border = background
        self.vdp.change_colors(foreground, background, border)
        self.memory.poke(FORCLR, foreground)
        self.memory.poke(BAKCLR, background)
        self.memory.poke(BDRCLR, border)

    # CLS
    def cls(self):
        self.text = [[32] * self.width for _ in range(self.rows)]
        self.cursor_x = self.cursor_y = 0

    # POSIT
    def locate(self, x: int, y: int):
        self.cursor_x = max(0, min(self.width - 1, x))
        self.cursor_y = max(0, min(self.rows - 1, y))

    # CHPUT / OUTDO
    def chput(self, value: int | str):
        code = ord(value) if isinstance(value, str) else value & 0xFF

        if code == 13:
            self.cursor_x = 0
            return
        if code == 10:
            self.cursor_y += 1
            self._scroll_if_needed()
            return
        if code == 7:
            self.beep()
            return

        self.text[self.cursor_y][self.cursor_x] = code
        self.cursor_x += 1
        if self.cursor_x >= self.width:
            self.cursor_x = 0
            self.cursor_y += 1
            self._scroll_if_needed()

    def print_text(self, value: str, newline: bool = True):
        for ch in value:
            self.chput(ch)
        if newline:
            self.chput(13)
            self.chput(10)

    def _scroll_if_needed(self):
        if self.cursor_y >= self.rows:
            self.text.pop(0)
            self.text.append([32] * self.width)
            self.cursor_y = self.rows - 1

    # BEEP
    def beep(self):
        # Mantém a semântica do BIOS. A GUI usa o bell do Tk.
        pass

    # GTSTCK
    def gtstck(self, port: int = 0) -> int:
        return self.joystick

    # GTTRIG
    def gttrig(self, port: int = 0) -> int:
        return -1 if self.trigger else 0

    def tick(self):
        self.memory.poke16(JIFFY, (self.memory.peek16(JIFFY) + 1) & 0xFFFF)
        self.hooks.call(HKEYI)
        self.hooks.call(HTIMI)


class MSXWindow:
    def __init__(self, machine: MSXMachine, scale: int = 2):
        self.machine = machine
        self.scale = scale
        self.root = tk.Tk()
        self.root.title("Python MSX BASIC Runtime")
        self.canvas = tk.Canvas(
            self.root, width=320 * scale, height=192 * scale,
            highlightthickness=0,
            bg=MSX_COLORS[machine.vdp.border]
        )
        self.canvas.pack()
        self.root.bind("<KeyPress>", self.key_down)
        self.root.bind("<KeyRelease>", self.key_up)
        self.running = True
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def close(self):
        self.running = False
        self.root.destroy()

    def key_down(self, event):
        k = event.keysym.lower()
        if k == "escape":
            self.close()
            return
        mapping = {"up": 1, "upright": 2, "right": 3, "downright": 4,
                   "down": 5, "downleft": 6, "left": 7, "upleft": 8}
        if k in mapping:
            self.machine.joystick = mapping[k]
        if k == "space":
            self.machine.trigger = True

    def key_up(self, event):
        if event.keysym.lower() in ("up", "right", "down", "left"):
            self.machine.joystick = 0
        if event.keysym.lower() == "space":
            self.machine.trigger = False

    def render(self):
        m = self.machine
        self.canvas.configure(bg=MSX_COLORS[m.vdp.border])
        self.canvas.delete("all")

        # SCREEN 0 logical 40x24: 8x8 glyphs = 320x192.
        fg = MSX_COLORS[m.vdp.foreground]
        bg = MSX_COLORS[m.vdp.background]

        self.canvas.create_rectangle(
            0, 0, 320*self.scale, 192*self.scale,
            fill=bg, outline=""
        )

        for row, line in enumerate(m.text):
            for col, code in enumerate(line):
                if code == 32:
                    continue
                glyph = m.font.glyph(code)
                ox = col * 8
                oy = row * 8
                for y, pixels in enumerate(glyph):
                    for x, bit in enumerate(pixels):
                        if bit:
                            self.canvas.create_rectangle(
                                (ox+x)*self.scale,
                                (oy+y)*self.scale,
                                (ox+x+1)*self.scale,
                                (oy+y+1)*self.scale,
                                fill=fg, outline=""
                            )

    def run(self):
        interval_ms = 1000 // 60

        def frame():
            if not self.running:
                return
            self.machine.tick()
            self.render()
            self.root.after(interval_ms, frame)

        frame()
        self.root.mainloop()


def load_font() -> bytes:
    path = Path(__file__).with_name("MSXFONT.BIN")
    if not path.exists():
        raise FileNotFoundError(
            "MSXFONT.BIN must be in the same directory as msxbasic_runtime.py"
        )
    return path.read_bytes()


def demo():
    msx = MSXMachine(load_font())
    msx.screen(0)
    msx.color(15, 4, 4)
    msx.cls()
    msx.locate(4, 3)
    msx.print_text("MSX BASIC BIOS -> PYTHON")
    msx.locate(4, 5)
    msx.print_text("MSXFONT.BIN 8x8 ATIVO")
    msx.locate(4, 8)
    msx.print_text("JIFFY:")
    msx.locate(4, 11)
    msx.print_text("SETAS = STICK")
    msx.locate(4, 12)
    msx.print_text("ESPACO = STRIG")
    msx.locate(4, 15)
    msx.print_text("ESC = SAIR")

    # Demonstra o hook HTIMI atualizado a cada interrupção lógica de 60 Hz.
    def htimi():
        value = msx.memory.peek16(JIFFY)
        text = f"{value:05d}"
        msx.locate(11, 8)
        msx.print_text(text, newline=False)

        msx.locate(11, 11)
        msx.print_text(f"{msx.gtstck(0):02d}", newline=False)

        msx.locate(13, 12)
        msx.print_text("ON " if msx.gttrig(0) else "OFF", newline=False)

    msx.hooks.install(HTIMI, htimi)

    MSXWindow(msx, scale=2).run()


if __name__ == "__main__":
    demo()
