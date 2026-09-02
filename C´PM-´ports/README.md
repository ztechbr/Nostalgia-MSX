# dBASEII_Python — real MSX/CP-M-80 execution in Python

This is **not** a behavioral rewrite of the programs on these disks. It is a
real **Zilog Z80 CPU emulator** (`z80.py`) plus a **CP/M-80 / MSX-DOS 1
BDOS+BIOS host** (`cpm_bdos.py`) and a **FAT12 `.DSK` mounter**
(`dskimage.py`). Together they run the *original, unmodified machine code*
straight off the real disk images in this folder — `COBOL.DSK`,
`dBASE II.dsk`, `VIDEOLOC.DSK` — the same way real MSX/CP-M hardware would,
just hosted in pure Python instead of silicon. Nothing about a program's
logic is reimplemented or guessed; only the CPU and the system-call surface
it expects (disk I/O, console I/O, the fixed MSX BIOS jump table) are.

## Files

| File | What it is |
|---|---|
| [`z80.py`](z80.py) | Full Z80 CPU core: all documented opcodes (unprefixed, `CB`, `ED`, `DD`, `FD`, `DDCB`/`FDCB`), undocumented `IXH`/`IXL`/`IYH`/`IYL` 8-bit access, correct flag behavior including the undocumented Y/X bits, interrupts (IM 0/1/2). Verified against [`test_z80_smoke.py`](test_z80_smoke.py). |
| [`dskimage.py`](dskimage.py) | FAT12 reader/writer for MSX `.DSK` images (the real on-disk filesystem — MSX-DOS 1's actual 360K/720K layout). Mounts a `.DSK` file into an in-memory copy; nothing is written back to the original file unless `save_as()` is called explicitly. |
| [`cpm_bdos.py`](cpm_bdos.py) | Loads a `.COM` at 0x0100 (the standard CP/M/MSX-DOS 1 TPA base) and services `CALL 0x0005` (BDOS: console + FCB-based file I/O against a mounted `DskImage`) and the fixed MSX BIOS page-0 jump table (`CALSLT`, `RDSLT`/`WRSLT`, `CHPUT`/`CHGET`/`CHSNS`, VDP helpers, screen-mode init) the way real MSX-DOS 1 does. |
| [`msx_vdp_ports.py`](msx_vdp_ports.py) | The real TMS9918 port-level protocol (ports `0x98`/`0x99`: address/register write-toggle latch, auto-incrementing VRAM pointer) for programs that bit-bang the video chip directly instead of calling BIOS — exactly what MSX Turbo Pascal's CRT unit does. Backed by the `MSXVDP` model already in [`../msxbasic_runtime.py`](../msxbasic_runtime.py). |
| [`run_com.py`](run_com.py) | CLI: mount a `.DSK`, run one `.COM` from it, console I/O to your terminal. |
| [`msx_gui_runner.py`](msx_gui_runner.py) | Tkinter front-end: runs one or more `.COM` files from a disk in a background thread and renders the *actual VRAM contents* live (real TMS9918 Text1/Graphic2 addressing — name table, pattern table, color table), with real keyboard input fed back into the emulated console/BIOS key routines. |
| [`test_z80_smoke.py`](test_z80_smoke.py) | Hand-assembled correctness tests for the CPU core (arithmetic/flags, `CALL`/`RET`, `DJNZ`, `LDIR`, indexed `(IX+d)` addressing, stack ops, conditional jumps). |

## What's on each disk, and what actually runs

- **`COBOL.DSK`** — the Microsoft MS-COBOL 4.66 (1980–1982) compiler/runtime
  system disk (`COBOL.COM` + `COBOL1..4.OVR` overlays). No end-user `.CBL`
  source shipped on this disk — it's the development tool itself.
  **Validated**: boots to the real `Microsoft MS-COBOL / Version 4.66` banner
  and the genuine `*` command prompt, correctly parses/rejects a malformed
  command with `?Command error`, exactly like the original.
- **`dBASE II.dsk`** — the dBASE II CP/M-family interpreter/runtime system
  disk (`DBASE.COM` loader + `DBASEOVR.COM`/`D40.OVL`/`D80.OVL`/`S80.OVL`
  overlays). Also a dev tool disk, no shipped `.DBF` application.
  **Validated**: the small loader stub relocates the interpreter, calls the
  MSX BIOS (`CALSLT`) to probe the machine, then renders the real historic
  splash screen via ADM-3A/H19-style cursor-addressing escape codes over
  plain console output: *"DBASE II — adapted for MSXDOS — by Piet Habich —
  july 1985"*.
- **`VIDEOLOC.DSK`** — an actual end-user application: **"CONTROLE DE VIDEO
  CLUBE"**, a video-rental-store manager (`LOCADORA.COM`, compiled Turbo
  Pascal 3 for MSX-DOS), with a splash-screen loader (`ABRETELA.COM`), a
  Portuguese MSX-DOS 1 shell (`COMANDO.COM`, "DDE-DOS" by Digital Design
  Eletrônica Ltda.), and real business data files (`FITAS.DAT` — the tape
  catalog, `CLIENTES.DAT`/`.NDX` — customers, `DISTRIB.DAT` — distributors).
  **Status**: the CPU/BDOS/BIOS layers correctly run these binaries through
  their startup relocation and VDP hardware setup, and real writes reach
  VRAM through the genuine port protocol — but this suite draws its UI by
  bit-banging the VDP directly (as real Turbo-Pascal-for-MSX software did),
  so **you need `msx_gui_runner.py` running interactively (real keyboard,
  real display refresh) to actually see and use it** — headless/automated
  runs can't demonstrate a program that's waiting on real key input to
  finish drawing its own screen. `COMANDO.COM` also calls at least one
  extended BDOS function (39) beyond standard CP/M 2.2 that isn't
  implemented yet, and some fixed high-memory addresses the LOCADORA suite
  calls appear to belong to this disk's own resident `DDXDOS.SYS` driver,
  which isn't loaded — those calls are safely no-op'd (immediate `RET`)
  rather than left to run into whatever memory happens to be there.

## Usage

Run a compiler/interpreter interactively, console I/O in your terminal:

```
python run_com.py COBOL.DSK COBOL.COM
python run_com.py "dBASE II.dsk" DBASE.COM
```

Run the video-store app with a real display and keyboard:

```
python msx_gui_runner.py VIDEOLOC.DSK ABRETELA.COM LOCADORA.COM
```

(Both `.COM` files run in the same emulated hardware session, one after the
other, so VRAM state set up by the splash screen persists into the main
program — exactly like two programs chained by `AUTOEXEC.BAT` on real
hardware, which is what this disk's own `AUTOEXEC.BAT` does.)

Non-interactive/automated runs (CI, scripting) should pass `--headless` to
`run_com.py` so a blocked keyboard read can't hang the process — real
console reads on Windows (`msvcrt`) talk to the OS console directly and
ignore stdin redirection, so headless mode falls back to plain
piped/redirected stdin instead.

## Why this approach, not a rewrite

`COBOL.COM` and `DBASE.COM` are the *tools themselves* (a compiler and an
interpreter) — there is no "port their behavior to Python" that doesn't
already mean "write a COBOL compiler and a dBASE interpreter from scratch,"
which would not run any of the actual bytes on these disks. Running the real
binary on a real (if software-hosted) Z80 is the only way to convert them
without discarding what's actually there. The same core doubles as an MSX
cartridge-ROM runner: point it at a `.ROM` mapped at `0x4000` with
[`../msxbasic_runtime.py`](../msxbasic_runtime.py)'s VDP/PSG for I/O and it
executes real cartridge code the same way.
