# Nostalgia-MSX

Python reimplementations and preservation ports of classic MSX (and one TRS-80)
software: BASIC/BIOS internals, DOS, games, and music theory examples. None of
these run the original Z80 machine code — each is a behavioral recreation in
pure Python, built from disassembly, BASIC source, or documented behavior of
the original programs.

## Core MSX runtime

| File | Description |
|---|---|
| [`msxbasic_runtime.py`](msxbasic_runtime.py) | MSX BASIC/BIOS compatibility layer: RAM, VRAM, VDP, PSG, console, keyboard, joystick, hooks and the 8x8 font, exposed as a reusable `MSXMachine` class for other ports. |
| [`msxdos2_py.py`](msxdos2_py.py) | Behavioral reimplementation of `MSXDOS2.SYS 2.40` (NYYRIKKI): virtual drives, `COMMAND2.COM` boot, `AUTOEXEC.BAT`/`AUTOEXEC.BAS`, and an MSX-DOS-style shell. See [`README_MSXDOS2_PY.md`](README_MSXDOS2_PY.md) for usage. |
| [`msx_constants.json`](msx_constants.json) | MSX BIOS/work-area memory map (symbol name → address) used by the runtime and ports. |
| [`MSXFONT.BIN`](MSXFONT.BIN) | Original MSX 8x8 character font ROM data, used by `msxbasic_runtime.py`. |
| [`turbo_pascal_python.py`](turbo_pascal_python.py) | Recreation of the Turbo Pascal 3 IDE workflow (Edit/Compile/Run/Save) plus a small Pascal interpreter supporting a useful language subset. |

## Games — [`gameS/`](gameS/)

| File | Description |
|---|---|
| [`froger_msx_python.py`](gameS/froger_msx_python.py) | Port of `froger.bas` (Frogger clone by OSYMER for MSX Extra) to Python/Tkinter, reproducing movement, hazards, oxygen, lives, score and levels. |
| [`galaga_msx_python.py`](gameS/galaga_msx_python.py) | Playable Python/Tkinter recreation of the MSX Galaga loader/binaries, rebuilt from reverse-engineered load addresses and copy/jump routines. |
| [`platoon_msx_python.py`](gameS/platoon_msx_python.py) | Text-mode preservation port of *Platoon* (OBA Soft, 1987), reconstructed from `PLATOONB.ASM`/`PLATOONC.ASM` recovered from the original disk image. |
| [`gameS/NostalgiaPlatoon/`](gameS/NostalgiaPlatoon/) | Flask web version of the Platoon port (`app.py`, `game/engine.py`, `game/data.py`), with HTML templates and Tailwind styling. |
| [`gameS/dancing/`](gameS/dancing/) | *The Dancing Demon* — Pygame recreation of the 1979/1986 TRS-80 Color Computer program by Leo Christopherson (music score editor, dance routine editor, synced playback, save/load, preset shows). |
| [`gameS/original/`](gameS/original/) | Decoded source used as reference for the ports (e.g. `froger_decoded.bas`). |
| [`gameS/Platoon_MSX/`](gameS/Platoon_MSX/) | Original Platoon MSX ROM image, kept for reference/preservation. |
| `dance1.txt`, `dance2.txt`, `dncdm86a.bas`, `dncdm86b.bas` | Original Dancing Demon BASIC source and sample dance/score data used as the basis for the `gameS/dancing/` port. |

## dBASE II — [`dBASEII_Python/`](dBASEII_Python/)

This folder holds two independent approaches to the same source material
(the `dBASE II.dsk` MSX-DOS disk image), covering both ends of "port vs.
emulate":

**Native rewrite — [`dBASEII_Python/dbase2py/`](dBASEII_Python/dbase2py/)**
A from-scratch Python implementation of the dBASE II 2.4 engine and command
processor (native `.DBF`/`.MEM` I/O, expression parser, `USE`/`APPEND`/
`REPLACE`/`INDEX`/`REPORT`/control-flow and more — see
[`dBASEII_Python/README.md`](dBASEII_Python/README.md) for the full command
list and compatibility notes). It does not touch the Z80 or CP/M at all.

| File | Description |
|---|---|
| [`dBASEII_Python/dbase2py/dbf.py`](dBASEII_Python/dbase2py/dbf.py) | Native dBASE II `.DBF` table format (header, fields, records) read/write. |
| [`dBASEII_Python/dbase2py/engine.py`](dBASEII_Python/dbase2py/engine.py) | Command processor (`USE`, `APPEND`, `REPLACE`, `LIST`/`DISPLAY`, `DELETE`/`PACK`, `INDEX`/`FIND`, `SORT`, `TOTAL`, `JOIN`, control flow, `.CMD` scripts, etc). |
| [`dBASEII_Python/dbase2py/expr.py`](dBASEII_Python/dbase2py/expr.py) | dBASE II expression parser/evaluator (`.AND.`/`.OR.`/`.NOT.`, comparisons, string/arith ops, built-in functions). |
| [`dBASEII_Python/dbase2py/index.py`](dBASEII_Python/dbase2py/index.py) / [`mem.py`](dBASEII_Python/dbase2py/mem.py) | Index (`.NDX`) and memory-variable (`.MEM`) persistence. |
| [`dBASEII_Python/main.py`](dBASEII_Python/main.py) / [`dbase2py/cli.py`](dBASEII_Python/dbase2py/cli.py) | Interactive/scripted CLI entry point (`python main.py --cwd ./data`). |
| [`dBASEII_Python/tests/`](dBASEII_Python/tests/) | Automated tests covering DBF round-trip, update/delete/pack/index/memory behavior and `.CMD` control flow. |

**Real Z80/CP-M-80 execution** — unlike the rewrite above, this side runs the
*original, unmodified machine code* from real `.DSK`/`.ROM` images on a real
Z80 CPU emulator hosted in Python.

| File | Description |
|---|---|
| [`dBASEII_Python/z80.py`](dBASEII_Python/z80.py) | Full Zilog Z80 CPU core (all documented opcodes incl. `CB`/`ED`/`DD`/`FD`/`DDCB`/`FDCB`, undocumented `IXH`/`IXL`/`IYH`/`IYL`, correct flags incl. undocumented Y/X bits, IM 0/1/2 interrupts). |
| [`dBASEII_Python/dskimage.py`](dBASEII_Python/dskimage.py) | FAT12 reader/writer for MSX `.DSK` images — mounts the real on-disk filesystem. |
| [`dBASEII_Python/cpm_bdos.py`](dBASEII_Python/cpm_bdos.py) | CP/M-80 / MSX-DOS 1 BDOS + MSX BIOS page-0 host: runs a `.COM` unmodified, servicing its disk/console/BIOS calls. |
| [`dBASEII_Python/msx_vdp_ports.py`](dBASEII_Python/msx_vdp_ports.py) | Real TMS9918 VDP port protocol (`0x98`/`0x99`) for programs that bit-bang video hardware directly. |
| [`dBASEII_Python/run_com.py`](dBASEII_Python/run_com.py) / [`msx_gui_runner.py`](dBASEII_Python/msx_gui_runner.py) | CLI and Tkinter runners. See [`dBASEII_Python/README.md`](dBASEII_Python/README.md) for what's on each disk and what's been validated: the real Microsoft MS-COBOL 4.66 compiler and dBASE II (1985) both boot to their genuine banners/prompts; `VIDEOLOC.DSK`'s Turbo-Pascal video-rental-store app ("CONTROLE DE VIDEO CLUBE") runs through hardware setup and needs the GUI runner's live display to be seen. |

The `.DSK`/`.ROM` disk images those runners load live in
[`` C´PM-´ports/ ``](<C´PM-´ports/>) alongside a copy of the same Python
files (kept as-is for reference).

## DATAGAME MSX-VTX — [`DATAGAME_Modern_Python/`](DATAGAME_Modern_Python/) and [`datagame_msx.py`](datagame_msx.py)

Two takes on the `DATAGAME.ROM` MSX videotex/modem cartridge (Datagame
MSX-VTX DG 1.1), reverse-engineered from the ROM's header, strings and
alphamosaic Level-1 terminal behavior. Neither executes Z80 — both are
behavioral reimplementations with a Tkinter UI.

| File | Description |
|---|---|
| [`datagame_msx.py`](datagame_msx.py) | Single-file recreation of the ROM's terminal/modem workflow (config dataclass, transport abstraction, TCP/serial). |
| [`DATAGAME_Modern_Python/`](DATAGAME_Modern_Python/) | Fuller rewrite aimed at real-world transports instead of a simulated backend: real TCP, UDP and serial-modem (`pyserial`) links, a `Videotexto TCP` mode that prompts for host/port per connection, real AT commands for serial modems, and full binary capture of received traffic to `logs/`. See [`DATAGAME_Modern_Python/README.md`](DATAGAME_Modern_Python/README.md) (Portuguese) for the alphamosaic feature set, wiring notes and technical limits. |
| [`DATAGAME_Modern_Python/datagame/app.py`](DATAGAME_Modern_Python/datagame/app.py) | GUI, keyboard handling and rendering. |
| [`DATAGAME_Modern_Python/datagame/transports.py`](DATAGAME_Modern_Python/datagame/transports.py) | Real TCP/UDP/serial transport implementations. |
| [`DATAGAME_Modern_Python/datagame/videotex.py`](DATAGAME_Modern_Python/datagame/videotex.py) | Videotex/alphamosaic decoder and terminal state. |
| [`DATAGAME_Modern_Python/tools/inspect_rom.py`](DATAGAME_Modern_Python/tools/inspect_rom.py) | Inspects the original ROM header/strings. |

## Music — [`musica/`](musica/)

Examples built around the **PLAY** command from the MSX, based on *Curso de
Música* (Barbieri & Piazzi, Editora Aleph, 1988) — see
[`musica/curso_de_musica_msx.pdf`](musica/curso_de_musica_msx.pdf).

| File | Description |
|---|---|
| [`musica/exemplos_python/msx_music.py`](musica/exemplos_python/msx_music.py) | Base library: translates MSX `PLAY` notation into sound and implements the equal-temperament note→frequency mapping. |
| `01_altura.py` … `06_musica_completa.py` | Progressive lessons (pitch, duration, scales, accidentals, transposition, a full transcribed piece) — see [`musica/exemplos_python/README.md`](musica/exemplos_python/README.md) for the full lesson index. |

## Requirements

- Python 3 with Tkinter for `msxbasic_runtime.py`, `turbo_pascal_python.py`, `froger_msx_python.py`, `galaga_msx_python.py`.
- `gameS/dancing/`: see [`requirements.txt`](gameS/dancing/requirements.txt) (Pygame, NumPy).
- `gameS/NostalgiaPlatoon/`: see [`requirements.txt`](gameS/NostalgiaPlatoon/requirements.txt) (Flask, Flask-Session) and `package.json` (Tailwind).
- `musica/exemplos_python/`: Python 3 on Windows (uses `winsound`).
- `dBASEII_Python/`: Python 3, no third-party dependencies (`pytest` for the tests in `tests/`).
- `DATAGAME_Modern_Python/` and `datagame_msx.py`: Python 3 with Tkinter; see [`requirements.txt`](DATAGAME_Modern_Python/requirements.txt) (`pyserial`) for real serial-modem support.
