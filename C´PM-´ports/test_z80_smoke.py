"""Smoke tests for z80.py -- hand-assembled tiny programs, checked for
correct register/memory/flag results. Not exhaustive, but catches gross
decode/flag bugs before running real MSX-DOS binaries on the core."""
from z80 import Z80, SimpleBus


def run(code: bytes, org: int = 0x100, max_steps: int = 10000) -> Z80:
    bus = SimpleBus()
    bus.mem[org:org + len(code)] = code
    cpu = Z80(bus=bus)
    cpu.pc = org
    steps = 0
    while not cpu.halted and steps < max_steps:
        cpu.step()
        steps += 1
    assert cpu.halted, f"did not halt after {max_steps} steps, pc={cpu.pc:04x}"
    return cpu


def test_basic_arith():
    # LD A,5 ; ADD A,3 ; LD B,A ; HALT
    cpu = run(bytes([0x3E, 0x05, 0xC6, 0x03, 0x47, 0x76]))
    assert cpu.a == 8
    assert cpu.b == 8
    print("basic_arith OK, A=", cpu.a)


def test_flags_sub_zero():
    # LD A,5 ; SUB 5 ; HALT -> Z flag set, A=0
    cpu = run(bytes([0x3E, 0x05, 0xD6, 0x05, 0x76]))
    assert cpu.a == 0
    assert cpu.f & 0x40, "Z flag should be set"
    print("flags_sub_zero OK")


def test_call_ret():
    # ORG 0x100
    # LD HL,0        ; 21 00 00
    # CALL 0x108     ; CD 08 01
    # LD B,H         ; 44
    # HALT           ; 76
    # ; at 0x108:
    # LD H,0x42      ; 26 42
    # RET            ; C9
    code = bytes([0x21, 0x00, 0x00, 0xCD, 0x08, 0x01, 0x44, 0x76,
                  0x26, 0x42, 0xC9])
    cpu = run(code)
    assert cpu.b == 0x42
    print("call_ret OK")


def test_djnz_loop():
    # LD A,0 ; LD B,5 ; loop: INC A ; DJNZ loop ; HALT
    code = bytes([0x3E, 0x00, 0x06, 0x05, 0x3C, 0x10, 0xFD, 0x76])
    cpu = run(code)
    assert cpu.a == 5
    print("djnz_loop OK, A=", cpu.a)


def test_ldir_block_copy():
    bus = SimpleBus()
    src = bytes(range(10))
    bus.mem[0x2000:0x2000 + 10] = src
    # LD HL,2000 ; LD DE,3000 ; LD BC,10 ; LDIR ; HALT
    code = bytes([0x21, 0x00, 0x20, 0x11, 0x00, 0x30, 0x01, 0x0A, 0x00,
                  0xED, 0xB0, 0x76])
    org = 0x100
    bus.mem[org:org + len(code)] = code
    cpu = Z80(bus=bus)
    cpu.pc = org
    steps = 0
    while not cpu.halted and steps < 10000:
        cpu.step()
        steps += 1
    dst = bytes(bus.mem[0x3000:0x3000 + 10])
    assert dst == src, f"LDIR copy mismatch: {dst!r} != {src!r}"
    print("ldir_block_copy OK")


def test_ix_indexed():
    # LD IX,0x3000 ; LD (IX+2),0x55 ; LD A,(IX+2) ; HALT
    code = bytes([0xDD, 0x21, 0x00, 0x30, 0xDD, 0x36, 0x02, 0x55,
                  0xDD, 0x7E, 0x02, 0x76])
    cpu = run(code)
    assert cpu.a == 0x55
    print("ix_indexed OK")


def test_stack_push_pop():
    # LD HL,0x1234 ; PUSH HL ; POP DE ; HALT
    code = bytes([0x21, 0x34, 0x12, 0xE5, 0xD1, 0x76])
    cpu = run(code)
    assert cpu.de == 0x1234
    print("stack_push_pop OK")


def test_bit_ops():
    # LD A,0x80 ; RLCA ; HALT -> A=1, C=1
    cpu = run(bytes([0x3E, 0x80, 0x07, 0x76]))
    assert cpu.a == 0x01
    assert cpu.f & 0x01
    print("bit_ops OK")


def test_conditional_jump():
    # LD A,0 ; CP 0 ; JR Z,+3 ; LD A,99 ; HALT ; (skip target) LD A,7 ; HALT
    code = bytes([0x3E, 0x00, 0xFE, 0x00, 0x28, 0x03, 0x3E, 0x63, 0x76,
                  0x3E, 0x07, 0x76])
    cpu = run(code)
    assert cpu.a == 7, f"expected jump taken, got A={cpu.a}"
    print("conditional_jump OK")


if __name__ == "__main__":
    test_basic_arith()
    test_flags_sub_zero()
    test_call_ret()
    test_djnz_loop()
    test_ldir_block_copy()
    test_ix_indexed()
    test_stack_push_pop()
    test_bit_ops()
    test_conditional_jump()
    print("\nAll smoke tests passed.")
