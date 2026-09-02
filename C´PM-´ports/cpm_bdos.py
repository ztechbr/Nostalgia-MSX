"""CP/M-80 / MSX-DOS 1 BDOS+BIOS trap layer for the z80.py CPU core.

Loads a real .COM program at 0x0100 (the standard CP/M/MSX-DOS 1 Transient
Program Area base) and services BDOS calls (CALL 0x0005) and program
termination (jump/return to 0x0000) exactly as MSX-DOS 1 / CP/M 2.2 did,
so the ORIGINAL machine code in COBOL.COM, DBASE.COM, DBASEOVR.COM,
LOCADORA.COM, ABRETELA.COM and COMANDO.COM runs unmodified -- this
executes the real program, it does not simulate its behavior.

File I/O is serviced against a mounted DskImage (the real extracted .DSK
filesystem), using the FCB (File Control Block) conventions CP/M-80/MSX-DOS1
programs already expect: EX/S2/CR/random-record fields are read out of
guest RAM to compute the byte offset into the target file, so callers doing
normal sequential/random record I/O work without any changes.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Callable, Optional

from z80 import Z80, SimpleBus
from dskimage import DskImage, DskError

RECORD_SIZE = 128


class CpmBus(SimpleBus):
    """64K flat memory bus; I/O ports are unused by pure CP/M-80 programs
    but left available for MSX BIOS/VDP hooking by subclasses."""
    pass


class Terminal:
    """Console I/O. Uses raw single-key reads on Windows (msvcrt) so BDOS
    functions 1/6/11 behave like a real serial console; falls back to
    line-buffered stdin elsewhere."""

    def __init__(self, interactive: bool = True):
        self._msvcrt = None
        try:
            import msvcrt
            # msvcrt.getch()/kbhit() talk to the real console, bypassing
            # stdin redirection entirely -- on a non-interactive stdin
            # (piped/redirected, as in automated runs) that blocks forever
            # waiting for a keypress that can never arrive. sys.stdin.isatty()
            # is not reliable enough to detect this on its own (some wrapped/
            # ptty'd non-interactive shells still report a tty), so callers
            # running unattended must pass interactive=False explicitly.
            if interactive:
                self._msvcrt = msvcrt
        except ImportError:
            pass
        self._esc_state = 0  # ADM-3A/H19-style "ESC Y row col" cursor addressing
        self._esc_row = 0

    def out(self, ch: int) -> None:
        c = ch & 0x7F
        # dBASE II / many CP/M-era business programs drive an ADM-3A/H19-class
        # terminal: ESC 'Y' <row+32> <col+32> positions the cursor. Translate
        # that into a real ANSI escape so it renders on a modern terminal.
        if self._esc_state == 0 and c == 0x1B:
            self._esc_state = 1
            return
        if self._esc_state == 1:
            if c == ord("Y"):
                self._esc_state = 2
            else:
                self._esc_state = 0
                sys.stdout.write("\x1b")
                sys.stdout.write(chr(c))
            return
        if self._esc_state == 2:
            self._esc_row = max(0, c - 0x20)
            self._esc_state = 3
            return
        if self._esc_state == 3:
            col = max(0, c - 0x20)
            self._esc_state = 0
            sys.stdout.write(f"\x1b[{self._esc_row + 1};{col + 1}H")
            sys.stdout.flush()
            return
        if c == 0x0D:
            return  # CR handled together with LF by the host terminal
        if c == 0x0C:
            sys.stdout.write("\x1b[2J\x1b[H")  # ADM-3A form-feed clears the screen
        elif c != 0x1A:
            sys.stdout.write(chr(c))
        sys.stdout.flush()

    def status(self) -> bool:
        if self._msvcrt:
            return self._msvcrt.kbhit()
        return False

    def in_char(self) -> int:
        if self._msvcrt:
            ch = self._msvcrt.getch()
            if ch in (b"\x00", b"\xe0"):
                self._msvcrt.getch()
                return 0
            c = ch[0]
            if c == 0x0D:
                sys.stdout.write("\n")
            else:
                sys.stdout.write(ch.decode("latin1"))
            sys.stdout.flush()
            return 0x0D if c == 0x0D else c
        data = sys.stdin.read(1)
        return ord(data) if data else 0x1A

    def readline(self, maxlen: int) -> str:
        line = sys.stdin.readline().rstrip("\n").rstrip("\r")
        return line[:maxlen]


class CpmError(Exception):
    pass


class ProgramExit(Exception):
    def __init__(self, code: int = 0):
        self.code = code


@dataclass
class OpenSearch:
    pattern_base: bytes
    pattern_ext: bytes
    results: list = field(default_factory=list)
    index: int = 0


class CpmHost:
    """The BDOS+BIOS emulation. Owns the Z80 CPU, mounted drives, and
    console. `run()` drives the fetch/execute loop and intercepts calls
    to 0x0000 (warm boot / exit) and 0x0005 (BDOS entry)."""

    BDOS_ENTRY = 0x0005
    WARM_BOOT = 0x0000
    DEFAULT_DMA = 0x0080
    TPA_BASE = 0x0100

    # MSX BIOS page-0 jump-table addresses this host recognizes and
    # services directly (CALSLT dispatches into these; a few, like RDSLT/
    # WRSLT/CALSLT itself, are also called directly since we run everything
    # in one flat address space instead of real hardware slots).
    BIOS_CALSLT = 0x001C
    BIOS_RDSLT = 0x000C
    BIOS_WRSLT = 0x0014
    BIOS_ENASLT = 0x0024
    BIOS_CHPUT = 0x00A2
    BIOS_CHGET = 0x009F
    BIOS_CHSNS = 0x009C
    BIOS_BEEP = 0x00C0
    BIOS_CLS = 0x00C3
    BIOS_POSIT = 0x00C6
    BIOS_DISSCR = 0x0041
    BIOS_ENASCR = 0x0044
    BIOS_WRTVDP = 0x0047
    BIOS_RDVRM = 0x004A
    BIOS_WRTVRM = 0x004D
    BIOS_SETRD = 0x0050
    BIOS_SETWRT = 0x0053
    BIOS_FILVRM = 0x0056
    BIOS_LDIRMV = 0x0059
    BIOS_LDIRVM = 0x005C
    BIOS_CHGMOD = 0x005F
    BIOS_INITXT = 0x006C
    BIOS_INIT32 = 0x006F
    BIOS_INIGRP = 0x0072
    BIOS_INIMLT = 0x0075

    def __init__(self, drives: dict[str, DskImage], terminal: Optional[Terminal] = None,
                 trace: bool = False, vdp_ports=None):
        self.bus = CpmBus()
        self.cpu = Z80(bus=self.bus)
        self.drives = {k.upper(): v for k, v in drives.items()}
        self.current_drive = "A"
        self.dma = self.DEFAULT_DMA
        self.terminal = terminal or Terminal()
        self.trace = trace
        self._search: Optional[OpenSearch] = None
        self.max_steps: Optional[int] = None
        self.vdp_ports = vdp_ports
        if vdp_ports is not None:
            vdp_ports.attach(self.bus)

        # The whole low page (0x0000-0x00FF) is the fixed MSX BIOS jump
        # table. Programs call dozens of entry points there directly (not
        # just BDOS/CALSLT); without real BIOS ROM mapped in, an
        # unimplemented entry must still behave like *some* routine that
        # returns, or execution drifts into zeroed memory, decodes it as
        # random opcodes, and eventually jumps into total garbage. Default
        # every page-0 address to an immediate RET; the specific ones we
        # actually implement are serviced by _bios_traps/BDOS before the
        # CPU ever executes that RET.
        for addr in range(0x00, 0x100):
            self.bus.mem[addr] = 0xC9
        self._bios_traps = {
            self.BIOS_CALSLT: self._bios_calslt,
            self.BIOS_RDSLT: self._bios_rdslt,
            self.BIOS_WRSLT: self._bios_wrslt,
            self.BIOS_ENASLT: self._bios_enaslt,
            self.BIOS_CHPUT: self._bios_chput,
            self.BIOS_CHGET: self._bios_chget,
            self.BIOS_CHSNS: self._bios_chsns,
            self.BIOS_BEEP: self._bios_beep,
            self.BIOS_CLS: self._bios_cls,
            self.BIOS_POSIT: self._bios_posit,
            self.BIOS_DISSCR: self._bios_noop,
            self.BIOS_ENASCR: self._bios_noop,
            self.BIOS_WRTVDP: self._bios_wrtvdp,
            self.BIOS_RDVRM: self._bios_rdvrm,
            self.BIOS_WRTVRM: self._bios_wrtvrm,
            self.BIOS_SETRD: self._bios_noop,
            self.BIOS_SETWRT: self._bios_noop,
            self.BIOS_FILVRM: self._bios_filvrm,
            self.BIOS_LDIRMV: self._bios_ldirmv,
            self.BIOS_LDIRVM: self._bios_ldirvm,
            self.BIOS_CHGMOD: self._bios_chgmod,
            self.BIOS_INITXT: self._bios_initxt,
            self.BIOS_INIT32: self._bios_init32,
            self.BIOS_INIGRP: self._bios_inigrp,
            self.BIOS_INIMLT: self._bios_inimlt,
        }
        self._cursor = (0, 0)

    # ---- program loading --------------------------------------------------
    def load_com(self, data: bytes) -> None:
        if len(data) > 0xFF00 - self.TPA_BASE:
            raise CpmError("program too large for TPA")
        # Everything above the loaded program (and below the BIOS jump
        # table, which load_com/__init__ already fills) is memory no real
        # code was ever placed in from our side. On real hardware that
        # space might hold a resident driver (e.g. this disk's own
        # DDXDOS.SYS, which COMANDO.COM/ABRETELA.COM/LOCADORA.COM appear to
        # CALL into directly at fixed high addresses for custom I/O) that
        # we don't load. Rather than leaving it zeroed -- which decodes as
        # NOP and lets a stray jump drift through random "garbage code" --
        # default it to an immediate RET, so any such call is a safe no-op
        # instead of undefined behavior.
        end = self.TPA_BASE + len(data)
        for addr in range(end, 0x10000):
            self.bus.mem[addr] = 0xC9
        self.bus.mem[self.TPA_BASE:end] = data
        self.cpu.pc = self.TPA_BASE
        self.cpu.sp = 0xFF00
        # BIOS warm-boot vector + BDOS entry vector at low memory, as CP/M sets up.
        self.bus.mem[1] = 0x00
        self.bus.mem[2] = 0xFE  # fake "BIOS base high byte" some programs peek at
        self.bus.mem[6] = 0x00
        self.bus.mem[7] = 0xFE
        # default (empty) command tail
        self.bus.mem[0x0080] = 0x00

    def set_command_tail(self, tail: str) -> None:
        raw = tail.encode("ascii", "replace")[:127]
        self.bus.mem[0x0080] = len(raw)
        self.bus.mem[0x0081:0x0081 + len(raw)] = raw

    # ---- run loop -----------------------------------------------------
    def run(self, max_steps: Optional[int] = None) -> int:
        steps = 0
        try:
            while True:
                if self.cpu.pc == self.WARM_BOOT:
                    return 0
                if self.cpu.pc == self.BDOS_ENTRY:
                    self._bdos_call()
                    continue
                trap = self._bios_traps.get(self.cpu.pc)
                if trap is not None:
                    trap()
                    self.cpu.pc = self.cpu.pop16()
                    continue
                self.cpu.step()
                steps += 1
                if max_steps is not None and steps >= max_steps:
                    raise CpmError(f"max_steps exceeded (pc={self.cpu.pc:04x})")
        except ProgramExit as e:
            return e.code

    # ---- BDOS dispatch --------------------------------------------------
    def _bdos_ret(self) -> None:
        self.cpu.pc = self.cpu.pop16()

    def _bdos_call(self) -> None:
        fn = self.cpu.c
        de = self.cpu.de
        if self.trace:
            print(f"[bdos {fn:3d}] DE={de:04x} A={self.cpu.a:02x}", file=sys.stderr)
        handler = self._HANDLERS.get(fn)
        if handler is None:
            self.cpu.a = 0x00
            self._bdos_ret()
            return
        handler(self, de)
        self._bdos_ret()

    # -- console -----------------------------------------------------
    def _f_conin(self, de: int) -> None:
        self.cpu.a = self.terminal.in_char() & 0x7F

    def _f_conout(self, de: int) -> None:
        self.terminal.out(self.cpu.e)

    def _f_rawio(self, de: int) -> None:
        e = self.cpu.e
        if e == 0xFF:
            self.cpu.a = self.terminal.in_char() if self.terminal.status() else 0x00
        elif e == 0xFE:
            self.cpu.a = 0xFF if self.terminal.status() else 0x00
        else:
            self.terminal.out(e)
            self.cpu.a = 0x00

    def _f_prstr(self, de: int) -> None:
        addr = de
        out = []
        while True:
            ch = self.cpu.rd8(addr)
            if ch == ord("$"):
                break
            out.append(chr(ch & 0x7F))
            addr = (addr + 1) & 0xFFFF
            if addr == de:
                break
        text = "".join(out).replace("\r\n", "\n").replace("\r", "\n")
        sys.stdout.write(text)
        sys.stdout.flush()

    def _f_readstr(self, de: int) -> None:
        maxlen = self.cpu.rd8(de)
        line = self.terminal.readline(maxlen)
        self.cpu.wr8((de + 1) & 0xFFFF, len(line))
        for i, ch in enumerate(line):
            self.cpu.wr8((de + 2 + i) & 0xFFFF, ord(ch) & 0x7F)

    def _f_constat(self, de: int) -> None:
        self.cpu.a = 0xFF if self.terminal.status() else 0x00

    def _f_version(self, de: int) -> None:
        self.cpu.hl = 0x0022  # MSX-DOS 1 reports as CP/M 2.2-compatible

    def _f_reset_disk(self, de: int) -> None:
        self.current_drive = "A"
        self.dma = self.DEFAULT_DMA

    def _f_select_disk(self, de: int) -> None:
        letter = chr(ord("A") + (self.cpu.e & 0x1F))
        if letter in self.drives:
            self.current_drive = letter
            self.cpu.hl = 0x0001
        else:
            self.cpu.a = 0xFF
            self.cpu.hl = 0x0000

    def _f_curdisk(self, de: int) -> None:
        self.cpu.a = ord(self.current_drive) - ord("A")

    def _f_setdma(self, de: int) -> None:
        self.dma = de

    # -- FCB helpers -----------------------------------------------------
    def _fcb_name(self, fcb: int) -> tuple[str, str]:
        name = "".join(chr(self.cpu.rd8(fcb + 1 + i)) for i in range(8)).rstrip()
        ext = "".join(chr(self.cpu.rd8(fcb + 9 + i)) for i in range(3)).rstrip()
        return name, ext

    def _fcb_filename(self, fcb: int) -> str:
        name, ext = self._fcb_name(fcb)
        return f"{name}.{ext}" if ext else name

    def _fcb_drive(self, fcb: int) -> DskImage:
        d = self.cpu.rd8(fcb)
        letter = self.current_drive if d == 0 else chr(ord("A") + d - 1)
        drive = self.drives.get(letter)
        if drive is None:
            raise DskError(f"drive {letter}: not ready")
        return drive

    def _fcb_seq_pos(self, fcb: int) -> int:
        ex = self.cpu.rd8(fcb + 12)
        s2 = self.cpu.rd8(fcb + 14) & 0x3F
        cr = self.cpu.rd8(fcb + 32)
        return ((s2 * 32 + ex) * 128 + cr) * RECORD_SIZE

    def _fcb_advance_seq(self, fcb: int) -> None:
        cr = self.cpu.rd8(fcb + 32) + 1
        if cr >= 128:
            cr = 0
            ex = self.cpu.rd8(fcb + 12) + 1
            if ex >= 32:
                ex = 0
                s2 = self.cpu.rd8(fcb + 14) + 1
                self.cpu.wr8(fcb + 14, s2 & 0xFF)
            self.cpu.wr8(fcb + 12, ex & 0xFF)
        self.cpu.wr8(fcb + 32, cr & 0xFF)

    def _fcb_random_pos(self, fcb: int) -> int:
        r0 = self.cpu.rd8(fcb + 33)
        r1 = self.cpu.rd8(fcb + 34)
        r2 = self.cpu.rd8(fcb + 35)
        rec = r0 | (r1 << 8) | (r2 << 16)
        return rec * RECORD_SIZE

    # -- file operations -------------------------------------------------
    def _f_open(self, de: int) -> None:
        try:
            drive = self._fcb_drive(de)
            name = self._fcb_filename(de)
            if not drive.exists(name):
                self.cpu.a = 0xFF
                return
            size = drive.file_size(name)
            self.cpu.wr8(de + 12, 0)
            self.cpu.wr8(de + 14, 0)
            self.cpu.wr8(de + 15, min(128, (size + 127) // RECORD_SIZE))
            self.cpu.wr8(de + 32, 0)
            self.cpu.a = 0x00
        except DskError:
            self.cpu.a = 0xFF

    def _f_close(self, de: int) -> None:
        self.cpu.a = 0x00

    def _f_make(self, de: int) -> None:
        try:
            drive = self._fcb_drive(de)
            name = self._fcb_filename(de)
            drive.create_file(name)
            self.cpu.wr8(de + 12, 0)
            self.cpu.wr8(de + 32, 0)
            self.cpu.a = 0x00
        except DskError:
            self.cpu.a = 0xFF

    def _f_delete(self, de: int) -> None:
        try:
            drive = self._fcb_drive(de)
            name = self._fcb_filename(de)
            self.cpu.a = 0x00 if drive.delete_file(name) else 0xFF
        except DskError:
            self.cpu.a = 0xFF

    def _f_rename(self, de: int) -> None:
        try:
            drive = self._fcb_drive(de)
            old = self._fcb_filename(de)
            new_name = "".join(chr(self.cpu.rd8(de + 17 + i)) for i in range(8)).rstrip()
            new_ext = "".join(chr(self.cpu.rd8(de + 25 + i)) for i in range(3)).rstrip()
            new = f"{new_name}.{new_ext}" if new_ext else new_name
            content = drive.read_file(old)
            drive.delete_file(old)
            drive.write_file(new, content)
            self.cpu.a = 0x00
        except (DskError, FileNotFoundError):
            self.cpu.a = 0xFF

    def _f_read(self, de: int) -> None:
        try:
            drive = self._fcb_drive(de)
            name = self._fcb_filename(de)
            content = drive.read_file(name)
            pos = self._fcb_seq_pos(de)
            if pos >= len(content):
                self.cpu.a = 0x01  # EOF
                return
            chunk = content[pos:pos + RECORD_SIZE]
            chunk = chunk + b"\x1a" * (RECORD_SIZE - len(chunk))
            for i, b in enumerate(chunk):
                self.cpu.wr8((self.dma + i) & 0xFFFF, b)
            self._fcb_advance_seq(de)
            self.cpu.a = 0x00
        except (DskError, FileNotFoundError):
            self.cpu.a = 0x09

    def _f_write(self, de: int) -> None:
        try:
            drive = self._fcb_drive(de)
            name = self._fcb_filename(de)
            chunk = bytes(self.cpu.rd8((self.dma + i) & 0xFFFF) for i in range(RECORD_SIZE))
            pos = self._fcb_seq_pos(de)
            drive.write_at(name, pos, chunk)
            self._fcb_advance_seq(de)
            self.cpu.a = 0x00
        except DskError:
            self.cpu.a = 0x01

    def _f_read_rand(self, de: int) -> None:
        try:
            drive = self._fcb_drive(de)
            name = self._fcb_filename(de)
            content = drive.read_file(name)
            pos = self._fcb_random_pos(de)
            if pos >= len(content):
                self.cpu.a = 0x01
                return
            chunk = content[pos:pos + RECORD_SIZE]
            chunk = chunk + b"\x1a" * (RECORD_SIZE - len(chunk))
            for i, b in enumerate(chunk):
                self.cpu.wr8((self.dma + i) & 0xFFFF, b)
            self.cpu.a = 0x00
        except (DskError, FileNotFoundError):
            self.cpu.a = 0x09

    def _f_write_rand(self, de: int) -> None:
        try:
            drive = self._fcb_drive(de)
            name = self._fcb_filename(de)
            chunk = bytes(self.cpu.rd8((self.dma + i) & 0xFFFF) for i in range(RECORD_SIZE))
            pos = self._fcb_random_pos(de)
            drive.write_at(name, pos, chunk)
            self.cpu.a = 0x00
        except DskError:
            self.cpu.a = 0x01

    def _f_size(self, de: int) -> None:
        try:
            drive = self._fcb_drive(de)
            name = self._fcb_filename(de)
            size = drive.file_size(name)
            recs = (size + RECORD_SIZE - 1) // RECORD_SIZE
            self.cpu.wr8(de + 33, recs & 0xFF)
            self.cpu.wr8(de + 34, (recs >> 8) & 0xFF)
            self.cpu.wr8(de + 35, (recs >> 16) & 0xFF)
        except (DskError, FileNotFoundError):
            self.cpu.wr8(de + 33, 0)
            self.cpu.wr8(de + 34, 0)
            self.cpu.wr8(de + 35, 0)

    def _f_setrandrec(self, de: int) -> None:
        cr = self.cpu.rd8(de + 32)
        ex = self.cpu.rd8(de + 12)
        s2 = self.cpu.rd8(de + 14) & 0x3F
        rec = (s2 * 32 + ex) * 128 + cr
        self.cpu.wr8(de + 33, rec & 0xFF)
        self.cpu.wr8(de + 34, (rec >> 8) & 0xFF)
        self.cpu.wr8(de + 35, (rec >> 16) & 0xFF)

    # -- search first/next -------------------------------------------------
    def _f_sfirst(self, de: int) -> None:
        name, ext = self._fcb_name(de)
        drive = self._fcb_drive(de)
        results = []
        for entry in drive.list_dir():
            base, dot, e_ext = entry["name"].partition(".")
            if self._glob_match(name, base.ljust(8)) and self._glob_match(ext, e_ext.ljust(3)):
                results.append(entry)
        self._search = OpenSearch(name.encode(), ext.encode(), results, 0)
        self._emit_search_result()

    def _f_snext(self, de: int) -> None:
        if self._search is None:
            self.cpu.a = 0xFF
            return
        self._emit_search_result()

    def _emit_search_result(self) -> None:
        s = self._search
        if s is None or s.index >= len(s.results):
            self.cpu.a = 0xFF
            return
        entry = s.results[s.index]
        s.index += 1
        base = self.dma
        for i in range(32):
            self.cpu.wr8(base + i, 0)
        base_name, _, ext_name = entry["name"].partition(".")
        nb = base_name.ljust(8)[:8].encode("ascii", "replace")
        eb = ext_name.ljust(3)[:3].encode("ascii", "replace")
        for i in range(8):
            self.cpu.wr8(base + 1 + i, nb[i])
        for i in range(3):
            self.cpu.wr8(base + 9 + i, eb[i])
        self.cpu.a = 0x00

    @staticmethod
    def _glob_match(pattern: str, value: str) -> bool:
        pattern = pattern.ljust(len(value))[:len(value)]
        for p, v in zip(pattern, value):
            if p == "?" or p == "\x00":
                continue
            if p != v:
                return False
        return True

    # -- misc no-ops needed by some runtimes --------------------------------
    def _f_getlogvec(self, de: int) -> None:
        self.cpu.hl = 0x0001  # only drive A logged in

    def _f_user(self, de: int) -> None:
        if self.cpu.e == 0xFF:
            self.cpu.a = 0x00

    def _f_termcpm(self, de: int) -> None:
        raise ProgramExit(0)

    # -- MSX BIOS page-0 entry points --------------------------------------
    # We run everything in one flat 64K space (no real hardware slots), so
    # CALSLT is serviced by dispatching on the target address exactly like
    # a direct call to that fixed BIOS vector would behave on real hardware.
    def _bios_calslt(self) -> None:
        target = self.cpu.ix
        handler = self._bios_traps.get(target)
        if handler is not None and handler is not self._bios_calslt:
            handler()
        elif self.trace:
            print(f"[bios] CALSLT to unhandled IX={target:04x}", file=sys.stderr)

    def _bios_rdslt(self) -> None:
        self.cpu.a = self.cpu.rd8(self.cpu.hl)

    def _bios_wrslt(self) -> None:
        self.cpu.wr8(self.cpu.hl, self.cpu.a)

    def _bios_enaslt(self) -> None:
        pass  # single flat address space: page switch is a no-op

    def _bios_chput(self) -> None:
        self.terminal.out(self.cpu.a)

    def _bios_chget(self) -> None:
        self.cpu.a = self.terminal.in_char() & 0x7F

    def _bios_chsns(self) -> None:
        self.cpu.f = (self.cpu.f | 0x40) if not self.terminal.status() else (self.cpu.f & ~0x40)

    def _bios_beep(self) -> None:
        sys.stdout.write("\a")
        sys.stdout.flush()

    def _bios_cls(self) -> None:
        sys.stdout.write("\x1b[2J\x1b[H")
        sys.stdout.flush()
        self._cursor = (0, 0)

    def _bios_posit(self) -> None:
        row, col = self.cpu.h, self.cpu.l
        self._cursor = (row, col)
        sys.stdout.write(f"\x1b[{row + 1};{col + 1}H")
        sys.stdout.flush()

    def _bios_noop(self) -> None:
        pass

    # -- VDP access (serviced directly against the attached MSXVDP model,
    # the same state the port-level protocol in msx_vdp_ports.py reads/
    # writes, so BIOS calls and raw port bit-banging stay consistent). ----
    def _bios_wrtvdp(self) -> None:
        if self.vdp_ports is not None:
            self.vdp_ports.vdp.write_register(self.cpu.b, self.cpu.a)

    def _bios_rdvrm(self) -> None:
        if self.vdp_ports is not None:
            self.cpu.a = self.vdp_ports.vdp.read_vram(self.cpu.hl)

    def _bios_wrtvrm(self) -> None:
        if self.vdp_ports is not None:
            self.vdp_ports.vdp.write_vram(self.cpu.hl, self.cpu.a)

    def _bios_filvrm(self) -> None:
        if self.vdp_ports is not None:
            self.vdp_ports.vdp.fill_vram(self.cpu.hl, self.cpu.a, self.cpu.de)

    def _bios_ldirvm(self) -> None:
        # RAM(HL) -> VRAM(DE), length BC
        if self.vdp_ports is not None:
            for i in range(self.cpu.bc):
                self.vdp_ports.vdp.write_vram(self.cpu.de + i, self.cpu.rd8(self.cpu.hl + i))

    def _bios_ldirmv(self) -> None:
        # VRAM(HL) -> RAM(DE), length BC
        if self.vdp_ports is not None:
            for i in range(self.cpu.bc):
                self.cpu.wr8(self.cpu.de + i, self.vdp_ports.vdp.read_vram(self.cpu.hl + i))

    def _bios_chgmod(self) -> None:
        self._set_screen_mode(self.cpu.a)

    def _bios_initxt(self) -> None:
        self._set_screen_mode(0)

    def _bios_init32(self) -> None:
        self._set_screen_mode(1)

    def _bios_inigrp(self) -> None:
        self._set_screen_mode(2)

    def _bios_inimlt(self) -> None:
        self._set_screen_mode(3)

    def _set_screen_mode(self, mode: int) -> None:
        if self.vdp_ports is not None and mode in (0, 1, 2, 3):
            self.vdp_ports.vdp.change_mode(mode)

    _HANDLERS: dict = {}


CpmHost._HANDLERS = {
    0: CpmHost._f_termcpm,
    1: CpmHost._f_conin,
    2: CpmHost._f_conout,
    6: CpmHost._f_rawio,
    9: CpmHost._f_prstr,
    10: CpmHost._f_readstr,
    11: CpmHost._f_constat,
    12: CpmHost._f_version,
    13: CpmHost._f_reset_disk,
    14: CpmHost._f_select_disk,
    15: CpmHost._f_open,
    16: CpmHost._f_close,
    17: CpmHost._f_sfirst,
    18: CpmHost._f_snext,
    19: CpmHost._f_delete,
    20: CpmHost._f_read,
    21: CpmHost._f_write,
    22: CpmHost._f_make,
    23: CpmHost._f_rename,
    24: CpmHost._f_getlogvec,
    25: CpmHost._f_curdisk,
    26: CpmHost._f_setdma,
    32: CpmHost._f_user,
    33: CpmHost._f_read_rand,
    34: CpmHost._f_write_rand,
    35: CpmHost._f_size,
    36: CpmHost._f_setrandrec,
}
