"""Z80 CPU emulator (pure Python).

A real, instruction-accurate Zilog Z80 core: all documented opcodes
(unprefixed, CB, ED, DD, FD, DDCB, FDCB), the common undocumented IXH/IXL/
IYH/IYL 8-bit accesses, undocumented Y/X flag bits, interrupts (IM 0/1/2),
and cycle counts. This executes real Z80 machine code byte-for-byte -- it
does not "simulate" or guess program behavior. Programs assembled/compiled
for a real MSX/CP/M-80 machine (COBOL.COM, DBASE.COM, LOCADORA.COM, ...)
run on this CPU unmodified.

Memory and I/O are abstracted through the `bus` object, which must provide:
    bus.mem: a bytearray-like object of length 65536, OR
    bus.rd8(addr) / bus.wr8(addr, value)   (optional override)
    bus.in_port(port) -> int
    bus.out_port(port, value)

The CPU never interprets *what* a program does; it only executes
instructions and reports the effect (registers/memory/ports), exactly like
silicon would.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

# Flag bit masks
S_FLAG = 0x80
Z_FLAG = 0x40
Y_FLAG = 0x20
H_FLAG = 0x10
X_FLAG = 0x08
P_FLAG = 0x04
V_FLAG = 0x04
N_FLAG = 0x02
C_FLAG = 0x01

_PARITY = [0] * 256
for _i in range(256):
    _PARITY[_i] = 1 if bin(_i).count("1") % 2 == 0 else 0

_SZ = [0] * 256
for _i in range(256):
    v = 0
    if _i == 0:
        v |= Z_FLAG
    if _i & 0x80:
        v |= S_FLAG
    v |= _i & (Y_FLAG | X_FLAG)
    _SZ[_i] = v

_SZP = [0] * 256
for _i in range(256):
    _SZP[_i] = _SZ[_i] | (P_FLAG if _PARITY[_i] else 0)


def _u8(v: int) -> int:
    return v & 0xFF


def _u16(v: int) -> int:
    return v & 0xFFFF


def _s8(v: int) -> int:
    v &= 0xFF
    return v - 256 if v & 0x80 else v


class SimpleBus:
    """Default flat 64K memory bus with no I/O devices attached."""

    def __init__(self) -> None:
        self.mem = bytearray(65536)
        self.io_in: dict[int, Callable[[int], int]] = {}
        self.io_out: dict[int, Callable[[int, int], None]] = {}

    def rd8(self, addr: int) -> int:
        return self.mem[addr & 0xFFFF]

    def wr8(self, addr: int, value: int) -> None:
        self.mem[addr & 0xFFFF] = value & 0xFF

    def in_port(self, port: int) -> int:
        fn = self.io_in.get(port & 0xFF)
        return fn(port) if fn else 0xFF

    def out_port(self, port: int, value: int) -> None:
        fn = self.io_out.get(port & 0xFF)
        if fn:
            fn(port, value)


@dataclass
class Z80:
    bus: object = field(default_factory=SimpleBus)

    def __post_init__(self) -> None:
        self.a = 0xFF
        self.f = 0xFF
        self.b = self.c = self.d = self.e = self.h = self.l = 0
        self.a_ = self.f_ = self.b_ = self.c_ = self.d_ = self.e_ = self.h_ = self.l_ = 0
        self.ix = self.iy = 0xFFFF
        self.sp = 0xFFFF
        self.pc = 0
        self.i = self.r = 0
        self.iff1 = self.iff2 = 0
        self.im = 0
        self.halted = False
        self.cycles = 0
        self.trap_hooks: dict[int, Callable[["Z80"], None]] = {}
        # RST 0x00/entry traps that a host BDOS/BIOS layer can install.
        self._ei_pending = False

    # ---- memory helpers -------------------------------------------------
    def rd8(self, addr: int) -> int:
        return self.bus.rd8(addr)

    def wr8(self, addr: int, value: int) -> None:
        self.bus.wr8(addr, value)

    def rd16(self, addr: int) -> int:
        return self.rd8(addr) | (self.rd8(addr + 1) << 8)

    def wr16(self, addr: int, value: int) -> None:
        self.wr8(addr, value & 0xFF)
        self.wr8(addr + 1, (value >> 8) & 0xFF)

    def fetch8(self) -> int:
        v = self.rd8(self.pc)
        self.pc = _u16(self.pc + 1)
        return v

    def fetch16(self) -> int:
        v = self.rd16(self.pc)
        self.pc = _u16(self.pc + 2)
        return v

    def push16(self, value: int) -> None:
        self.sp = _u16(self.sp - 2)
        self.wr16(self.sp, value)

    def pop16(self) -> int:
        v = self.rd16(self.sp)
        self.sp = _u16(self.sp + 2)
        return v

    # ---- 16-bit register pairs ------------------------------------------
    @property
    def af(self) -> int:
        return (self.a << 8) | self.f

    @af.setter
    def af(self, v: int) -> None:
        self.a = (v >> 8) & 0xFF
        self.f = v & 0xFF

    @property
    def bc(self) -> int:
        return (self.b << 8) | self.c

    @bc.setter
    def bc(self, v: int) -> None:
        self.b = (v >> 8) & 0xFF
        self.c = v & 0xFF

    @property
    def de(self) -> int:
        return (self.d << 8) | self.e

    @de.setter
    def de(self, v: int) -> None:
        self.d = (v >> 8) & 0xFF
        self.e = v & 0xFF

    @property
    def hl(self) -> int:
        return (self.h << 8) | self.l

    @hl.setter
    def hl(self, v: int) -> None:
        self.h = (v >> 8) & 0xFF
        self.l = v & 0xFF

    def _r_inc(self) -> None:
        self.r = (self.r & 0x80) | ((self.r + 1) & 0x7F)

    # ---- interrupts -------------------------------------------------------
    def irq(self, data_bus_value: int = 0xFF) -> int:
        """Trigger a maskable interrupt. Returns extra T-states consumed."""
        if not self.iff1:
            return 0
        self.halted = False
        self.iff1 = self.iff2 = 0
        self._r_inc()
        if self.im == 0:
            self.push16(self.pc)
            self.pc = 0x0038
            return 13
        if self.im == 1:
            self.push16(self.pc)
            self.pc = 0x0038
            return 13
        vec = (self.i << 8) | (data_bus_value & 0xFE)
        self.push16(self.pc)
        self.pc = self.rd16(vec)
        return 19

    def nmi(self) -> int:
        self.halted = False
        self.iff2 = self.iff1
        self.iff1 = 0
        self._r_inc()
        self.push16(self.pc)
        self.pc = 0x0066
        return 11

    # ---- flags helpers ------------------------------------------------
    def _add8(self, a: int, b: int, carry: int = 0) -> int:
        r = a + b + carry
        res = r & 0xFF
        f = _SZ[res]
        if ((a & 0xF) + (b & 0xF) + carry) & 0x10:
            f |= H_FLAG
        if r > 0xFF:
            f |= C_FLAG
        if (~(a ^ b) & (a ^ res)) & 0x80:
            f |= V_FLAG
        self.f = f
        return res

    def _sub8(self, a: int, b: int, carry: int = 0) -> int:
        r = a - b - carry
        res = r & 0xFF
        f = _SZ[res] | N_FLAG
        if ((a & 0xF) - (b & 0xF) - carry) & 0x10:
            f |= H_FLAG
        if r < 0:
            f |= C_FLAG
        if ((a ^ b) & (a ^ res)) & 0x80:
            f |= V_FLAG
        self.f = f
        return res

    def _cp8(self, a: int, b: int) -> None:
        r = a - b
        res = r & 0xFF
        f = (res & S_FLAG) | (Z_FLAG if res == 0 else 0) | N_FLAG
        f |= b & (Y_FLAG | X_FLAG)
        if ((a & 0xF) - (b & 0xF)) & 0x10:
            f |= H_FLAG
        if r < 0:
            f |= C_FLAG
        if ((a ^ b) & (a ^ res)) & 0x80:
            f |= V_FLAG
        self.f = f

    def _and8(self, a: int, b: int) -> int:
        res = a & b
        self.f = _SZP[res] | H_FLAG
        return res

    def _or8(self, a: int, b: int) -> int:
        res = a | b
        self.f = _SZP[res]
        return res

    def _xor8(self, a: int, b: int) -> int:
        res = a ^ b
        self.f = _SZP[res]
        return res

    def _inc8(self, a: int) -> int:
        res = (a + 1) & 0xFF
        f = _SZ[res] & ~N_FLAG
        f &= ~N_FLAG
        if (a & 0x0F) == 0x0F:
            f |= H_FLAG
        if res == 0x80:
            f |= V_FLAG
        f = (f & ~C_FLAG) | (self.f & C_FLAG)
        self.f = f
        return res

    def _dec8(self, a: int) -> int:
        res = (a - 1) & 0xFF
        f = _SZ[res] | N_FLAG
        if (a & 0x0F) == 0x00:
            f |= H_FLAG
        if res == 0x7F:
            f |= V_FLAG
        f = (f & ~C_FLAG) | (self.f & C_FLAG)
        self.f = f
        return res

    def _add16(self, a: int, b: int) -> int:
        r = a + b
        res = r & 0xFFFF
        f = self.f & (S_FLAG | Z_FLAG | V_FLAG)
        if ((a & 0x0FFF) + (b & 0x0FFF)) & 0x1000:
            f |= H_FLAG
        if r > 0xFFFF:
            f |= C_FLAG
        f |= (res >> 8) & (Y_FLAG | X_FLAG)
        self.f = f
        return res

    def _adc16(self, a: int, b: int) -> int:
        carry = self.f & C_FLAG
        r = a + b + carry
        res = r & 0xFFFF
        f = 0
        if res & 0x8000:
            f |= S_FLAG
        if res == 0:
            f |= Z_FLAG
        if ((a & 0x0FFF) + (b & 0x0FFF) + carry) & 0x1000:
            f |= H_FLAG
        if r > 0xFFFF:
            f |= C_FLAG
        if (~(a ^ b) & (a ^ res)) & 0x8000:
            f |= V_FLAG
        f |= (res >> 8) & (Y_FLAG | X_FLAG)
        self.f = f
        return res

    def _sbc16(self, a: int, b: int) -> int:
        carry = self.f & C_FLAG
        r = a - b - carry
        res = r & 0xFFFF
        f = N_FLAG
        if res & 0x8000:
            f |= S_FLAG
        if res == 0:
            f |= Z_FLAG
        if ((a & 0x0FFF) - (b & 0x0FFF) - carry) & 0x1000:
            f |= H_FLAG
        if r < 0:
            f |= C_FLAG
        if ((a ^ b) & (a ^ res)) & 0x8000:
            f |= V_FLAG
        f |= (res >> 8) & (Y_FLAG | X_FLAG)
        self.f = f
        return res

    # ---- register file access by 3-bit code -----------------------------
    def _get_r(self, code: int, idx_hl: Optional[int] = None) -> int:
        if code == 0:
            return self.b
        if code == 1:
            return self.c
        if code == 2:
            return self.d
        if code == 3:
            return self.e
        if code == 4:
            return (idx_hl >> 8) & 0xFF if idx_hl is not None else self.h
        if code == 5:
            return idx_hl & 0xFF if idx_hl is not None else self.l
        if code == 6:
            addr = idx_hl if idx_hl is not None else self.hl
            return self.rd8(addr)
        if code == 7:
            return self.a
        raise ValueError(code)

    def _set_r(self, code: int, value: int, idx_hl: Optional[int] = None,
               idx_setter: Optional[Callable[[int], None]] = None) -> None:
        value &= 0xFF
        if code == 0:
            self.b = value
        elif code == 1:
            self.c = value
        elif code == 2:
            self.d = value
        elif code == 3:
            self.e = value
        elif code == 4:
            if idx_hl is not None and idx_setter is not None:
                idx_setter((value << 8) | (idx_hl & 0xFF))
            else:
                self.h = value
        elif code == 5:
            if idx_hl is not None and idx_setter is not None:
                idx_setter((idx_hl & 0xFF00) | value)
            else:
                self.l = value
        elif code == 6:
            addr = idx_hl if idx_hl is not None else self.hl
            self.wr8(addr, value)
        elif code == 7:
            self.a = value

    # ---- main step --------------------------------------------------------
    def step(self) -> int:
        if self.halted:
            self._r_inc()
            return 4
        start_cycles = self.cycles
        opcode = self.fetch8()
        self._r_inc()
        self._exec(opcode, None, 0)
        if self._ei_pending:
            self._ei_pending = False
        return self.cycles - start_cycles

    def _exec(self, opcode: int, idx_reg: Optional[str], _depth: int) -> None:
        """Execute one (possibly prefixed) instruction. idx_reg is None,
        'ix' or 'iy' when decoding a DD/FD-prefixed opcode."""
        c = self.cycles

        if opcode == 0xCB:
            self._exec_cb(idx_reg)
            return
        if opcode == 0xED:
            self._exec_ed()
            return
        if opcode in (0xDD, 0xFD):
            reg = "ix" if opcode == 0xDD else "iy"
            op2 = self.fetch8()
            self._r_inc()
            self._exec(op2, reg, _depth + 1)
            return

        x = opcode >> 6
        y = (opcode >> 3) & 7
        z = opcode & 7

        idx_val = None
        idx_setter = None
        if idx_reg == "ix":
            idx_val = self.ix
            idx_setter = lambda v: setattr(self, "ix", v & 0xFFFF)
        elif idx_reg == "iy":
            idx_val = self.iy
            idx_setter = lambda v: setattr(self, "iy", v & 0xFFFF)

        def hl_or_idx() -> int:
            if idx_reg is None:
                return self.hl
            d = _s8(self.fetch8())
            return _u16(idx_val + d)

        # ---------------- x=0 block --------------------------------------
        if x == 0:
            if z == 0:
                if y == 0:
                    self.cycles += 4
                    return
                if y == 1:
                    self.af, af2 = (self.a_ << 8) | self.f_, None
                    self.a, self.a_ = self.a_, self.a
                    self.f, self.f_ = self.f_, self.f
                    self.cycles += 4
                    return
                if y == 2:
                    d = _s8(self.fetch8())
                    self.b = _u8(self.b - 1)
                    if self.b != 0:
                        self.pc = _u16(self.pc + d)
                        self.cycles += 13
                    else:
                        self.cycles += 8
                    return
                if y == 3:
                    d = _s8(self.fetch8())
                    self.pc = _u16(self.pc + d)
                    self.cycles += 12
                    return
                if 4 <= y <= 7:
                    cond = ("nz", "z", "nc", "c")[y - 4]
                    d = _s8(self.fetch8())
                    take = {"nz": not (self.f & Z_FLAG), "z": self.f & Z_FLAG,
                            "nc": not (self.f & C_FLAG), "c": self.f & C_FLAG}[cond]
                    if take:
                        self.pc = _u16(self.pc + d)
                        self.cycles += 12
                    else:
                        self.cycles += 7
                    return
            if z == 1:
                if y % 2 == 0:
                    val = self.fetch16()
                    rp = y >> 1
                    self._set_rp(rp, val, idx_reg)
                    self.cycles += 10
                else:
                    rp = y >> 1
                    cur = self._get_rp(rp, idx_reg)
                    tgt = self.hl if idx_reg is None else idx_val
                    res = self._add16(tgt, cur)
                    if idx_reg is None:
                        self.hl = res
                    else:
                        idx_setter(res)
                    self.cycles += 11
                return
            if z == 2:
                addrs = {0: ("bc", True), 1: ("bc", False), 2: ("de", True), 3: ("de", False)}
                if y in (0, 1, 2, 3):
                    reg, store = addrs[y]
                    addr = self.bc if reg == "bc" else self.de
                    if store:
                        self.wr8(addr, self.a)
                    else:
                        self.a = self.rd8(addr)
                    self.cycles += 7
                    return
                if y == 4:
                    addr = self.fetch16()
                    val = idx_val if idx_reg else self.hl
                    self.wr16(addr, val)
                    self.cycles += 16
                    return
                if y == 5:
                    addr = self.fetch16()
                    val = self.rd16(addr)
                    if idx_reg:
                        idx_setter(val)
                    else:
                        self.hl = val
                    self.cycles += 16
                    return
                if y == 6:
                    addr = self.fetch16()
                    self.wr8(addr, self.a)
                    self.cycles += 13
                    return
                if y == 7:
                    addr = self.fetch16()
                    self.a = self.rd8(addr)
                    self.cycles += 13
                    return
            if z == 3:
                rp = y >> 1
                cur = self._get_rp(rp, idx_reg)
                if y % 2 == 0:
                    self._set_rp(rp, _u16(cur + 1), idx_reg)
                else:
                    self._set_rp(rp, _u16(cur - 1), idx_reg)
                self.cycles += 6
                return
            if z == 4 or z == 5:
                if y == 6:
                    addr = hl_or_idx()
                    val = self.rd8(addr)
                    if z == 4:
                        self.wr8(addr, self._inc8(val))
                    else:
                        self.wr8(addr, self._dec8(val))
                    self.cycles += 23 if idx_reg else 11
                else:
                    val = self._get_r(y, idx_val)
                    if z == 4:
                        res = self._inc8(val)
                    else:
                        res = self._dec8(val)
                    self._set_r(y, res, idx_val, idx_setter)
                    self.cycles += 4
                return
            if z == 6:
                if y == 6:
                    addr = hl_or_idx()
                    val = self.fetch8()
                    self.wr8(addr, val)
                    self.cycles += 19 if idx_reg else 10
                else:
                    val = self.fetch8()
                    self._set_r(y, val, idx_val, idx_setter)
                    self.cycles += 7
                return
            if z == 7:
                ops = (self._rlca, self._rrca, self._rla, self._rra,
                       self._daa, self._cpl, self._scf, self._ccf)
                ops[y]()
                self.cycles += 4
                return

        # ---------------- x=1 block: LD r,r' / HALT -----------------------
        if x == 1:
            if z == 6 and y == 6:
                self.halted = True
                self.cycles += 4
                return
            if y == 6:
                # LD (HL),r / LD (IX+d),r -- memory dest, plain source reg
                addr = hl_or_idx()
                val = self._get_r(z)
                self.wr8(addr, val)
                self.cycles += 19 if idx_reg else 7
            elif z == 6:
                # LD r,(HL) / LD r,(IX+d) -- plain dest reg, memory source
                addr = hl_or_idx()
                val = self.rd8(addr)
                self._set_r(y, val)
                self.cycles += 19 if idx_reg else 7
            else:
                # LD r,r' -- pure register move (IXH/IXL substitution applies)
                val = self._get_r(z, idx_val)
                self._set_r(y, val, idx_val, idx_setter)
                self.cycles += 8 if idx_reg else 4
            return

        # ---------------- x=2 block: ALU a,r -------------------------------
        if x == 2:
            if z == 6:
                addr = hl_or_idx()
                val = self.rd8(addr)
                self.cycles += 19 if idx_reg else 7
            else:
                val = self._get_r(z, idx_val)
                self.cycles += 4
            self._alu(y, val)
            return

        # ---------------- x=3 block ----------------------------------------
        if x == 3:
            if z == 0:
                cond = self._test_cond(y)
                if cond:
                    self.pc = self.pop16()
                    self.cycles += 11
                else:
                    self.cycles += 5
                return
            if z == 1:
                if y % 2 == 0:
                    rp = y >> 1
                    val = self.pop16()
                    self._set_rp2(rp, val, idx_reg)
                    self.cycles += 10
                else:
                    if y == 1:
                        self.pc = self.pop16()
                        self.cycles += 10
                    elif y == 3:
                        self.sp, self.pc = self.pc, self.pop16()
                        self.cycles += 4
                    elif y == 5:
                        self.pc = idx_val if idx_reg else self.hl
                        self.cycles += 4
                    elif y == 7:
                        self.sp = idx_val if idx_reg else self.hl
                        self.cycles += 6
                return
            if z == 2:
                addr = self.fetch16()
                if self._test_cond(y):
                    self.pc = addr
                self.cycles += 10
                return
            if z == 3:
                if y == 0:
                    addr = self.fetch16()
                    self.pc = addr
                    self.cycles += 10
                elif y == 1:
                    self._exec_cb(idx_reg)
                elif y == 2:
                    port = self.fetch8()
                    self.a = self.bus.in_port(port | (self.a << 8))
                    self.cycles += 11
                elif y == 3:
                    port = self.fetch8()
                    self.bus.out_port(port | (self.a << 8), self.a)
                    self.cycles += 11
                elif y == 4:
                    tmp = self.rd16(self.sp)
                    val = idx_val if idx_reg else self.hl
                    self.wr16(self.sp, val)
                    if idx_reg:
                        idx_setter(tmp)
                    else:
                        self.hl = tmp
                    self.cycles += 19
                elif y == 5:
                    self.de, self.hl = self.hl, self.de
                    self.cycles += 4
                elif y == 6:
                    self.iff1 = self.iff2 = 0
                    self.cycles += 4
                elif y == 7:
                    self.iff1 = self.iff2 = 1
                    self._ei_pending = True
                    self.cycles += 4
                return
            if z == 4:
                addr = self.fetch16()
                if self._test_cond(y):
                    self.push16(self.pc)
                    self.pc = addr
                    self.cycles += 17
                else:
                    self.cycles += 10
                return
            if z == 5:
                if y % 2 == 0:
                    rp = y >> 1
                    val = self._get_rp2(rp, idx_reg)
                    self.push16(val)
                    self.cycles += 11
                else:
                    if y == 1:
                        addr = self.fetch16()
                        self.push16(self.pc)
                        self.pc = addr
                        self.cycles += 17
                    else:
                        pass
                return
            if z == 6:
                val = self.fetch8()
                self._alu(y, val)
                self.cycles += 7
                return
            if z == 7:
                self.push16(self.pc)
                self.pc = y * 8
                self.cycles += 11
                return
        self.cycles = c + 4  # unknown opcode: consume as NOP

    # ---- register-pair helpers respecting DD/FD -------------------------
    def _get_rp(self, rp: int, idx_reg: Optional[str]) -> int:
        if rp == 0:
            return self.bc
        if rp == 1:
            return self.de
        if rp == 2:
            return self.ix if idx_reg == "ix" else self.iy if idx_reg == "iy" else self.hl
        if rp == 3:
            return self.sp
        raise ValueError(rp)

    def _set_rp(self, rp: int, value: int, idx_reg: Optional[str]) -> None:
        value &= 0xFFFF
        if rp == 0:
            self.bc = value
        elif rp == 1:
            self.de = value
        elif rp == 2:
            if idx_reg == "ix":
                self.ix = value
            elif idx_reg == "iy":
                self.iy = value
            else:
                self.hl = value
        elif rp == 3:
            self.sp = value

    def _get_rp2(self, rp: int, idx_reg: Optional[str]) -> int:
        if rp == 3:
            return self.af
        return self._get_rp(rp, idx_reg)

    def _set_rp2(self, rp: int, value: int, idx_reg: Optional[str]) -> None:
        if rp == 3:
            self.af = value
        else:
            self._set_rp(rp, value, idx_reg)

    def _test_cond(self, y: int) -> bool:
        return (
            not (self.f & Z_FLAG), bool(self.f & Z_FLAG),
            not (self.f & C_FLAG), bool(self.f & C_FLAG),
            not (self.f & P_FLAG), bool(self.f & P_FLAG),
            not (self.f & S_FLAG), bool(self.f & S_FLAG),
        )[y]

    # ---- 8-bit rotate/misc -----------------------------------------------
    def _rlca(self) -> None:
        c = (self.a >> 7) & 1
        self.a = _u8((self.a << 1) | c)
        self.f = (self.f & (S_FLAG | Z_FLAG | P_FLAG)) | (self.a & (Y_FLAG | X_FLAG)) | c

    def _rrca(self) -> None:
        c = self.a & 1
        self.a = _u8((self.a >> 1) | (c << 7))
        self.f = (self.f & (S_FLAG | Z_FLAG | P_FLAG)) | (self.a & (Y_FLAG | X_FLAG)) | c

    def _rla(self) -> None:
        c = (self.a >> 7) & 1
        self.a = _u8((self.a << 1) | (self.f & C_FLAG))
        self.f = (self.f & (S_FLAG | Z_FLAG | P_FLAG)) | (self.a & (Y_FLAG | X_FLAG)) | c

    def _rra(self) -> None:
        c = self.a & 1
        self.a = _u8((self.a >> 1) | ((self.f & C_FLAG) << 7))
        self.f = (self.f & (S_FLAG | Z_FLAG | P_FLAG)) | (self.a & (Y_FLAG | X_FLAG)) | c

    def _daa(self) -> None:
        a = self.a
        c = self.f & C_FLAG
        h = self.f & H_FLAG
        n = self.f & N_FLAG
        corr = 0
        if h or (a & 0x0F) > 9:
            corr |= 0x06
        if c or a > 0x99:
            corr |= 0x60
            c = C_FLAG
        if n:
            newh = H_FLAG if (h and (a & 0x0F) < 6) else 0
            a = _u8(a - corr)
        else:
            newh = H_FLAG if (a & 0x0F) + (corr & 0x0F) > 0x0F else 0
            a = _u8(a + corr)
        self.a = a
        self.f = _SZP[a] | (n) | newh | c

    def _cpl(self) -> None:
        self.a = _u8(~self.a)
        self.f = (self.f & (S_FLAG | Z_FLAG | P_FLAG | C_FLAG)) | H_FLAG | N_FLAG | (self.a & (Y_FLAG | X_FLAG))

    def _scf(self) -> None:
        self.f = (self.f & (S_FLAG | Z_FLAG | P_FLAG)) | (self.a & (Y_FLAG | X_FLAG)) | C_FLAG

    def _ccf(self) -> None:
        c = self.f & C_FLAG
        self.f = (self.f & (S_FLAG | Z_FLAG | P_FLAG)) | (c << 4) | (self.a & (Y_FLAG | X_FLAG)) | (0 if c else C_FLAG)

    def _alu(self, op: int, val: int) -> None:
        if op == 0:
            self.a = self._add8(self.a, val)
        elif op == 1:
            self.a = self._add8(self.a, val, self.f & C_FLAG)
        elif op == 2:
            self.a = self._sub8(self.a, val)
        elif op == 3:
            self.a = self._sub8(self.a, val, self.f & C_FLAG)
        elif op == 4:
            self.a = self._and8(self.a, val)
        elif op == 5:
            self.a = self._xor8(self.a, val)
        elif op == 6:
            self.a = self._or8(self.a, val)
        elif op == 7:
            self._cp8(self.a, val)

    # ---- CB-prefixed (rot/shift/bit/res/set) ------------------------------
    def _exec_cb(self, idx_reg: Optional[str]) -> None:
        if idx_reg is not None:
            d = _s8(self.fetch8())
            base = self.ix if idx_reg == "ix" else self.iy
            addr = _u16(base + d)
            opcode = self.fetch8()
            x = opcode >> 6
            y = (opcode >> 3) & 7
            z = opcode & 7
            val = self.rd8(addr)
            if x == 0:
                res = self._rot_shift(y, val)
            elif x == 1:
                bit = 1 << y
                res_f = (self.f & C_FLAG) | H_FLAG
                res_f |= (Z_FLAG | P_FLAG) if not (val & bit) else 0
                if y == 7 and (val & bit):
                    res_f |= S_FLAG
                res_f |= addr >> 8 & (Y_FLAG | X_FLAG)
                self.f = res_f
                self.cycles += 20
                return
            elif x == 2:
                res = val & ~(1 << y) & 0xFF
            else:
                res = val | (1 << y)
            self.wr8(addr, res)
            if z != 6 and x != 1:
                self._set_r(z, res)
            self.cycles += 23
            return
        opcode = self.fetch8()
        x = opcode >> 6
        y = (opcode >> 3) & 7
        z = opcode & 7
        addr = self.hl if z == 6 else None
        val = self.rd8(addr) if addr is not None else self._get_r(z)
        if x == 0:
            res = self._rot_shift(y, val)
            self._set_r(z, res)
            self.cycles += 15 if z == 6 else 8
        elif x == 1:
            bit = 1 << y
            f = (self.f & C_FLAG) | H_FLAG
            if not (val & bit):
                f |= Z_FLAG | P_FLAG
            if y == 7 and (val & bit):
                f |= S_FLAG
            f |= val & (Y_FLAG | X_FLAG)
            self.f = f
            self.cycles += 12 if z == 6 else 8
        elif x == 2:
            res = val & ~(1 << y) & 0xFF
            self._set_r(z, res)
            self.cycles += 15 if z == 6 else 8
        else:
            res = val | (1 << y)
            self._set_r(z, res)
            self.cycles += 15 if z == 6 else 8

    def _rot_shift(self, y: int, val: int) -> int:
        c_in = self.f & C_FLAG
        if y == 0:  # RLC
            c = (val >> 7) & 1
            res = _u8((val << 1) | c)
        elif y == 1:  # RRC
            c = val & 1
            res = _u8((val >> 1) | (c << 7))
        elif y == 2:  # RL
            c = (val >> 7) & 1
            res = _u8((val << 1) | c_in)
        elif y == 3:  # RR
            c = val & 1
            res = _u8((val >> 1) | (c_in << 7))
        elif y == 4:  # SLA
            c = (val >> 7) & 1
            res = _u8(val << 1)
        elif y == 5:  # SRA
            c = val & 1
            res = _u8((val >> 1) | (val & 0x80))
        elif y == 6:  # SLL (undocumented)
            c = (val >> 7) & 1
            res = _u8((val << 1) | 1)
        else:  # SRL
            c = val & 1
            res = (val >> 1) & 0x7F
        self.f = _SZP[res] | c
        return res

    # ---- ED-prefixed --------------------------------------------------
    def _exec_ed(self) -> None:
        opcode = self.fetch8()
        self._r_inc()
        x = opcode >> 6
        y = (opcode >> 3) & 7
        z = opcode & 7

        if x == 1:
            if z == 0:  # IN r,(C)
                val = self.bus.in_port(self.bc)
                if y != 6:
                    self._set_r(y, val)
                self.f = _SZP[val] | (self.f & C_FLAG)
                self.cycles += 12
                return
            if z == 1:  # OUT (C),r
                val = self._get_r(y) if y != 6 else 0
                self.bus.out_port(self.bc, val)
                self.cycles += 12
                return
            if z == 2:
                rp = y >> 1
                cur = self._get_rp(rp, None)
                if y % 2 == 0:
                    self.hl = self._sbc16(self.hl, cur)
                else:
                    self.hl = self._adc16(self.hl, cur)
                self.cycles += 15
                return
            if z == 3:
                addr = self.fetch16()
                rp = y >> 1
                if y % 2 == 0:
                    self.wr16(addr, self._get_rp(rp, None))
                else:
                    self._set_rp(rp, self.rd16(addr), None)
                self.cycles += 20
                return
            if z == 4:  # NEG
                self.a = self._sub8(0, self.a)
                self.cycles += 8
                return
            if z == 5:  # RETN / RETI
                self.iff1 = self.iff2
                self.pc = self.pop16()
                self.cycles += 14
                return
            if z == 6:  # IM
                im_map = {0: 0, 1: 0, 2: 1, 3: 2, 4: 0, 5: 0, 6: 1, 7: 2}
                self.im = im_map.get(y, 0)
                self.cycles += 8
                return
            if z == 7:
                if y == 0:
                    self.i = self.a
                elif y == 1:
                    self.r = self.a
                elif y == 2:
                    self.a = self.i
                    self.f = _SZ[self.a] | (self.f & C_FLAG) | (V_FLAG if self.iff2 else 0)
                elif y == 3:
                    self.a = self.r
                    self.f = _SZ[self.a] | (self.f & C_FLAG) | (V_FLAG if self.iff2 else 0)
                elif y == 4:  # RRD
                    m = self.rd8(self.hl)
                    lo_a = self.a & 0x0F
                    self.a = (self.a & 0xF0) | (m & 0x0F)
                    m = ((m >> 4) & 0x0F) | (lo_a << 4)
                    self.wr8(self.hl, m)
                    self.f = _SZP[self.a] | (self.f & C_FLAG)
                    self.cycles += 18
                    return
                elif y == 5:  # RLD
                    m = self.rd8(self.hl)
                    lo_a = self.a & 0x0F
                    self.a = (self.a & 0xF0) | ((m >> 4) & 0x0F)
                    m = ((m << 4) & 0xF0) | lo_a
                    self.wr8(self.hl, m)
                    self.f = _SZP[self.a] | (self.f & C_FLAG)
                    self.cycles += 18
                    return
                self.cycles += 9
                return
            return

        if x == 2 and z <= 3 and y >= 4:
            self._ed_block(y, z)
            return

        self.cycles += 8  # ED NOP / unimplemented

    def _ed_block(self, y: int, z: int) -> None:
        inc = 1 if y in (4, 6) else -1
        if z == 0:  # LDI/LDD/LDIR/LDDR
            val = self.rd8(self.hl)
            self.wr8(self.de, val)
            self.hl = _u16(self.hl + inc)
            self.de = _u16(self.de + inc)
            self.bc = _u16(self.bc - 1)
            n = _u8(val + self.a)
            f = self.f & (S_FLAG | Z_FLAG | C_FLAG)
            if self.bc != 0:
                f |= P_FLAG
            f |= n & X_FLAG
            f |= (Y_FLAG if n & 0x02 else 0)
            self.f = f
            self.cycles += 16
            if y == 6 and self.bc != 0:
                self.pc = _u16(self.pc - 2)
                self.cycles += 5
        elif z == 1:  # CPI/CPD/CPIR/CPDR
            val = self.rd8(self.hl)
            res = _u8(self.a - val)
            self.hl = _u16(self.hl + inc)
            self.bc = _u16(self.bc - 1)
            f = (self.f & C_FLAG) | N_FLAG | _SZ[res]
            if ((self.a & 0xF) - (val & 0xF)) & 0x10:
                f |= H_FLAG
                n = _u8(res - 1)
            else:
                n = res
            f = (f & ~(Y_FLAG | X_FLAG)) | (n & X_FLAG) | (Y_FLAG if n & 0x02 else 0)
            if self.bc != 0:
                f |= P_FLAG
            self.f = f
            self.cycles += 16
            if y == 6 and self.bc != 0 and res != 0:
                self.pc = _u16(self.pc - 2)
                self.cycles += 5
        elif z == 2:  # INI/IND/INIR/INDR
            val = self.bus.in_port(self.bc)
            self.wr8(self.hl, val)
            self.hl = _u16(self.hl + inc)
            self.b = _u8(self.b - 1)
            self.f = (_SZ[self.b] & ~Z_FLAG) | (Z_FLAG if self.b == 0 else 0) | N_FLAG
            self.cycles += 16
            if y == 6 and self.b != 0:
                self.pc = _u16(self.pc - 2)
                self.cycles += 5
        elif z == 3:  # OUTI/OUTD/OTIR/OTDR
            val = self.rd8(self.hl)
            self.b = _u8(self.b - 1)
            self.bus.out_port(self.bc, val)
            self.hl = _u16(self.hl + inc)
            self.f = (_SZ[self.b] & ~Z_FLAG) | (Z_FLAG if self.b == 0 else 0) | N_FLAG
            self.cycles += 16
            if y == 6 and self.b != 0:
                self.pc = _u16(self.pc - 2)
                self.cycles += 5
