"""Real TMS9918 VDP I/O-port protocol (ports 0x98/0x99), for programs that
bit-bang the video chip directly instead of going through BIOS calls -- this
is exactly what MSX Turbo Pascal's CRT unit does (ABRETELA.COM/LOCADORA.COM
never call CHPUT; they write straight to the VDP ports like the real
hardware driver did). Backed by the VRAM/register model already in
msxbasic_runtime.py (MSXVDP) so this reuses the repo's existing VDP state,
it just adds the missing port-level read/write state machine real silicon
implements: the address/register write-toggle latch and the auto-
incrementing VRAM pointer.
"""
from __future__ import annotations

import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
from msxbasic_runtime import MSXVDP  # noqa: E402


class VdpPorts:
    def __init__(self, vdp: MSXVDP | None = None):
        self.vdp = vdp or MSXVDP()
        self._latch: int | None = None
        self._addr = 0
        self._write_mode = False
        self.status = 0x9F  # bit7 set: report vblank already happened
        self.frame = 0

    # ---- port 0x98: VRAM data --------------------------------------------
    def read_data(self, port: int = 0x98) -> int:
        v = self.vdp.read_vram(self._addr)
        self._addr = (self._addr + 1) & 0x3FFF
        return v

    def write_data(self, port: int, value: int) -> None:
        self.vdp.write_vram(self._addr, value)
        self._addr = (self._addr + 1) & 0x3FFF

    # ---- port 0x99: register/address port + status ------------------------
    def read_status(self, port: int = 0x99) -> int:
        self._latch = None
        s = self.status
        self.status &= 0x7F  # reading clears the frame-interrupt flag
        return s

    def write_control(self, port: int, value: int) -> None:
        if self._latch is None:
            self._latch = value & 0xFF
            return
        first = self._latch
        self._latch = None
        if value & 0x80:
            reg = value & 0x07
            self.vdp.write_register(reg, first)
        else:
            self._addr = (first | ((value & 0x3F) << 8)) & 0x3FFF
            self._write_mode = bool(value & 0x40)

    def attach(self, bus) -> None:
        bus.io_in[0x98] = self.read_data
        bus.io_in[0x99] = self.read_status
        bus.io_out[0x98] = self.write_data
        bus.io_out[0x99] = self.write_control


def decode_text_screen(vdp: MSXVDP, cols: int = 40, rows: int = 24,
                        font_bitmap: dict[int, bytes] | None = None) -> list[str]:
    """Best-effort decode of a SCREEN 0/1-style text display straight out of
    VRAM: read the name table (register 2) and, if a font_bitmap map (glyph
    pattern bytes -> character) is supplied, translate each cell's pattern
    back to a printable character by comparing 8x8 patterns -- this lets a
    headless run be inspected/verified without opening a Tk window."""
    name_base = (vdp.registers[2] & 0x0F) << 10
    pattern_base = (vdp.registers[4] & 0x07) << 11
    lines = []
    for r in range(rows):
        line_chars = []
        for c in range(cols):
            code = vdp.read_vram(name_base + r * cols + c)
            ch = None
            if font_bitmap is not None:
                pat = bytes(vdp.read_vram(pattern_base + code * 8 + i) for i in range(8))
                ch = font_bitmap.get(pat)
            line_chars.append(ch if ch else (chr(code) if 32 <= code < 127 else "."))
        lines.append("".join(line_chars))
    return lines
