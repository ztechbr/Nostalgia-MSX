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
