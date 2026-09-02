#!/usr/bin/env python3
"""Run a real .COM program straight off an MSX .DSK image, on the z80.py
CPU core + cpm_bdos.py BDOS/BIOS layer.

This executes the ORIGINAL Z80 machine code from the disk image -- COBOL.COM,
DBASE.COM, LOCADORA.COM, COMANDO.COM, ... -- unmodified. Nothing about the
program's logic is reimplemented in Python; only the CPU and the MSX-DOS 1
system-call surface it expects are.

Usage:
    python run_com.py "COBOL.DSK" COBOL.COM
    python run_com.py "dBASE II.dsk" DBASE.COM
    python run_com.py VIDEOLOC.DSK COMANDO.COM --tail "LOCADORA"
    python run_com.py VIDEOLOC.DSK LOCADORA.COM -b VIDEOLOC.DSK
"""
from __future__ import annotations

import argparse
import sys

from dskimage import DskImage
from cpm_bdos import CpmHost, CpmError, Terminal


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dsk", help="path to the .DSK image to mount as drive A:")
    ap.add_argument("com", help="name of the .COM file on that disk to run")
    ap.add_argument("-b", "--drive-b", help="optional second .DSK to mount as drive B:")
    ap.add_argument("--tail", default="", help="command-tail text passed to the program")
    ap.add_argument("--trace", action="store_true", help="trace every BDOS call to stderr")
    ap.add_argument("--headless", action="store_true",
                     help="non-interactive: never block on real keyboard input (for automated/unattended runs)")
    ap.add_argument("--max-steps", type=int, default=200_000_000, help="safety limit on executed instructions")
    ap.add_argument("--save-as", help="if the run should persist disk changes, save drive A to this new path")
    args = ap.parse_args()

    drive_a = DskImage.load(args.dsk)
    drives = {"A": drive_a}
    if args.drive_b:
        drives["B"] = DskImage.load(args.drive_b)

    if not drive_a.exists(args.com):
        print(f"'{args.com}' not found on {args.dsk}. Files on disk:", file=sys.stderr)
        for e in drive_a.list_dir():
            print(f"  {e['name']:14s} {e['size']:7d} bytes", file=sys.stderr)
        return 2

    host = CpmHost(drives, terminal=Terminal(interactive=not args.headless), trace=args.trace)
    code = drive_a.read_file(args.com)
    host.load_com(code)
    host.set_command_tail(args.tail)

    print(f"[run_com] executing real {args.com} ({len(code)} bytes) from {args.dsk}", file=sys.stderr)
    try:
        rc = host.run(max_steps=args.max_steps)
    except CpmError as e:
        print(f"\n[run_com] stopped: {e}", file=sys.stderr)
        rc = 1
    except KeyboardInterrupt:
        print("\n[run_com] interrupted", file=sys.stderr)
        rc = 130

    if args.save_as:
        drive_a.save_as(args.save_as)
        print(f"[run_com] drive A changes saved to {args.save_as}", file=sys.stderr)

    return rc


if __name__ == "__main__":
    raise SystemExit(main())
