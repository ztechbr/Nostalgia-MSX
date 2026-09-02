#!/usr/bin/env python3
"""MSXDOS2.SYS 2.40 inspired behavioral reimplementation in Python.

Based on observable behavior/strings from NYYRIKKI's MSXDOS2.SYS 2.40.
This is NOT a binary-compatible replacement for an MSX Z80 machine. It is a
portable host-side model of the boot manager, drive selection, batch startup,
critical-error recovery and a small COMMAND2-like shell.
"""
from __future__ import annotations

import argparse
import os
import shlex
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Optional

VERSION = "2.40-py"
SOURCE_COMPAT = "MSXDOS2.SYS 2.40 (NYYRIKKI)"


class DOS2Error(Exception):
    pass


class DriveError(DOS2Error):
    pass


@dataclass
class VirtualDrive:
    letter: str
    root: Path

    def __post_init__(self) -> None:
        self.letter = self.letter.upper().rstrip(":")
        if len(self.letter) != 1 or not self.letter.isalpha():
            raise ValueError(f"Invalid drive: {self.letter}")
        self.root = self.root.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve(self, dos_path: str = "") -> Path:
        p = dos_path.replace("\\", "/").lstrip("/")
        candidate = (self.root / p).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise DriveError("Path escapes drive root") from exc
        return candidate


@dataclass
class MSXDOS2System:
    drives: Dict[str, VirtualDrive]
    current_drive: str = "A"
    cwd: Dict[str, str] = field(default_factory=dict)
    env: Dict[str, str] = field(default_factory=lambda: dict(os.environ))
    running: bool = True

    def __post_init__(self) -> None:
        self.drives = {k.upper().rstrip(":"): v for k, v in self.drives.items()}
        self.current_drive = self.current_drive.upper().rstrip(":")
        for d in self.drives:
            self.cwd.setdefault(d, "")
        if self.current_drive not in self.drives:
            raise DriveError(f"Boot drive {self.current_drive}: is not mapped")

    @property
    def drive(self) -> VirtualDrive:
        return self.drives[self.current_drive]

    def parse_path(self, text: str) -> tuple[VirtualDrive, str]:
        text = text.strip().strip('"')
        drive_letter = self.current_drive
        rest = text
        if len(text) >= 2 and text[1] == ":":
            drive_letter = text[0].upper()
            rest = text[2:]
        if drive_letter not in self.drives:
            raise DriveError(f"Drive {drive_letter}: not ready")
        base = "" if rest.startswith(("/", "\\")) else self.cwd.get(drive_letter, "")
        rel = str(Path(base.replace("\\", "/")) / rest.replace("\\", "/")) if rest else base
        rel = rel.replace("\\", "/")
        return self.drives[drive_letter], rel

    def dos_name(self, path: Path, drive: Optional[str] = None) -> str:
        d = (drive or self.current_drive).upper()
        root = self.drives[d].root
        rel = path.resolve().relative_to(root).as_posix().replace("/", "\\")
        return f"{d}:\\{rel}" if rel else f"{d}:\\"

    def boot(self, basic: bool = False) -> int:
        print(f"MSX-DOS 2 Python compatibility layer {VERSION}")
        print(f"Behavioral source: {SOURCE_COMPAT}")
        if basic:
            return self.enter_basic(autoexec=True)

        command = self.find_on_drives("COMMAND2.COM")
        if command is None:
            command = self.recover_command2()
            if command is None:
                print("Not enough memory, system halted" if not self.drives else
                      "Failed to load COMMAND2.COM from available drives")
                return 1

        # Normal boot executes AUTOEXEC.BAT when present. REBOOT.BAT is exposed
        # through the REBOOT shell command to model the original recovery path.
        autoexec = self.drive.resolve("AUTOEXEC.BAT")
        if autoexec.exists():
            self.execute_batch(autoexec, [f"{self.current_drive}:"])
        self.shell()
        return 0

    def find_on_drives(self, filename: str) -> Optional[Path]:
        order = [self.current_drive] + [d for d in sorted(self.drives) if d != self.current_drive]
        for d in order:
            p = self.drives[d].resolve(filename)
            if p.is_file():
                self.current_drive = d
                return p
        return None

    def recover_command2(self) -> Optional[Path]:
        print(f"Failed to load COMMAND2.COM from drive {self.current_drive}:")
        if not sys.stdin.isatty():
            return self.find_on_drives("COMMAND2.COM")
        while True:
            answer = input("Input alternative boot drive (A-Z, B=MSX BASIC, Enter=abort): ").strip().upper()
            if not answer:
                return None
            if answer == "B" and "B" not in self.drives:
                self.enter_basic(autoexec=False)
                return None
            d = answer[0]
            if d in self.drives:
                p = self.drives[d].resolve("COMMAND2.COM")
                if p.is_file():
                    self.current_drive = d
                    return p
                print(f"Failed to load COMMAND2.COM from drive {d}:")
            else:
                print(f"Drive {d}: not ready")

    def critical_error(self, operation: str, target: str, *, allow_ignore: bool = False) -> str:
        options = "Abort, Retry or Ignore (A/R/I)? " if allow_ignore else "Abort or Retry (A/R)? "
        while True:
            if not sys.stdin.isatty():
                return "A"
            ans = input(f"*** Error {operation} {target}\n{options}").strip().upper()[:1]
            valid = {"A", "R", "I"} if allow_ignore else {"A", "R"}
            if ans in valid:
                return ans

    def execute_batch(self, path: Path, args: Iterable[str] = ()) -> None:
        try:
            lines = path.read_text(encoding="latin-1").splitlines()
        except OSError:
            action = self.critical_error("reading", self.dos_name(path))
            if action == "R":
                return self.execute_batch(path, args)
            return
        argv = list(args)
        for raw in lines:
            line = raw.strip()
            if not line or line.upper().startswith("REM ") or line.startswith("::"):
                continue
            for i, arg in enumerate(argv, 1):
                line = line.replace(f"%{i}", arg)
            if line.startswith("@"): line = line[1:]
            print(f"> {line}")
            self.execute_command(line)
            if not self.running:
                break

    def prompt(self) -> str:
        rel = self.cwd.get(self.current_drive, "").replace("/", "\\")
        return f"{self.current_drive}:\\{rel}>" if rel else f"{self.current_drive}:\\>"

    def shell(self) -> None:
        while self.running:
            try:
                line = input(self.prompt()).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if line:
                self.execute_command(line)

    def execute_command(self, line: str) -> None:
        if len(line) == 2 and line[1] == ":" and line[0].upper() in self.drives:
            self.current_drive = line[0].upper(); return
        try:
            parts = shlex.split(line, posix=False)
        except ValueError as exc:
            print(f"Syntax error: {exc}"); return
        if not parts: return
        cmd = parts[0].strip('"').upper()
        args = [x.strip('"') for x in parts[1:]]
        dispatch = {
            "VER": self.cmd_ver, "DIR": self.cmd_dir, "TYPE": self.cmd_type,
            "CD": self.cmd_cd, "CHDIR": self.cmd_cd, "COPY": self.cmd_copy,
            "DEL": self.cmd_del, "ERASE": self.cmd_del, "REN": self.cmd_ren,
            "RENAME": self.cmd_ren, "MD": self.cmd_md, "MKDIR": self.cmd_md,
            "RD": self.cmd_rd, "RMDIR": self.cmd_rd, "ECHO": self.cmd_echo,
            "SET": self.cmd_set, "CLS": self.cmd_cls, "PATH": self.cmd_path,
            "BASIC": self.cmd_basic, "REBOOT": self.cmd_reboot,
            "EXIT": self.cmd_exit, "HELP": self.cmd_help,
        }
        fn = dispatch.get(cmd)
        if fn:
            try: fn(args)
            except (OSError, DOS2Error) as exc: print(f"*** {exc}")
            return
        # BAT file execution
        candidate = cmd if cmd.endswith(".BAT") else cmd + ".BAT"
        try:
            drive, rel = self.parse_path(candidate)
            p = drive.resolve(rel)
            if p.is_file():
                self.execute_batch(p, args); return
        except DOS2Error:
            pass
        print(f"*** Unrecognized command: {parts[0]}")

    def cmd_ver(self, _): print(f"MSX-DOS 2 compatible Python shell {VERSION}")

    def cmd_dir(self, args):
        drive, rel = self.parse_path(args[0] if args else "")
        p = drive.resolve(rel)
        if p.is_file(): entries = [p]
        elif p.is_dir(): entries = sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.upper()))
        else: print("File not found"); return
        print(f"Directory of {self.dos_name(p if p.is_dir() else p.parent, drive.letter)}")
        total = 0
        for e in entries:
            if e.is_dir(): print(f"<DIR>          {e.name}")
            else:
                size = e.stat().st_size; total += size
                print(f"{size:12d}  {e.name}")
        print(f"{total} bytes")

    def cmd_type(self, args):
        if not args: print("Required parameter missing"); return
        drive, rel = self.parse_path(args[0]); p = drive.resolve(rel)
        try: print(p.read_text(encoding="latin-1"), end="" if p.read_bytes().endswith(b"\n") else "\n")
        except OSError as exc: raise DriveError(f"Error reading {args[0]}: {exc}")

    def cmd_cd(self, args):
        if not args:
            print(self.dos_name(self.drive.resolve(self.cwd[self.current_drive]))); return
        drive, rel = self.parse_path(args[0]); p = drive.resolve(rel)
        if not p.is_dir(): raise DriveError("Directory not found")
        self.cwd[drive.letter] = p.relative_to(drive.root).as_posix()
        if len(args[0]) >= 2 and args[0][1] == ":": self.current_drive = drive.letter

    def cmd_copy(self, args):
        if len(args) < 2: print("Required parameter missing"); return
        sd, sr = self.parse_path(args[0]); dd, dr = self.parse_path(args[1])
        src, dst = sd.resolve(sr), dd.resolve(dr)
        if dst.is_dir(): dst = dst / src.name
        try:
            dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src, dst); print("1 file copied")
        except OSError as exc: raise DriveError(f"Error writing {args[1]}: {exc}")

    def cmd_del(self, args):
        if not args: print("Required parameter missing"); return
        d, r = self.parse_path(args[0]); p = d.resolve(r)
        if not p.is_file(): print("File not found"); return
        p.unlink()

    def cmd_ren(self, args):
        if len(args) < 2: print("Required parameter missing"); return
        d, r = self.parse_path(args[0]); src = d.resolve(r); dst = src.with_name(args[1])
        src.rename(dst)

    def cmd_md(self, args):
        if not args: print("Required parameter missing"); return
        d, r = self.parse_path(args[0]); d.resolve(r).mkdir(parents=True, exist_ok=False)

    def cmd_rd(self, args):
        if not args: print("Required parameter missing"); return
        d, r = self.parse_path(args[0]); d.resolve(r).rmdir()

    def cmd_echo(self, args): print(" ".join(args))

    def cmd_set(self, args):
        if not args:
            for k in sorted(self.env): print(f"{k}={self.env[k]}")
            return
        text = " ".join(args)
        if "=" not in text: print(self.env.get(text, "")); return
        k, v = text.split("=", 1); self.env[k] = v

    def cmd_path(self, args):
        if args: self.env["PATH"] = " ".join(args)
        else: print(f"PATH={self.env.get('PATH','')}")

    def cmd_cls(self, _): print("\033[2J\033[H", end="")
    def cmd_basic(self, _): self.enter_basic(autoexec=False)

    def cmd_reboot(self, _):
        p = self.drive.resolve("REBOOT.BAT")
        if p.exists(): self.execute_batch(p, [f"{self.current_drive}:"])
        else: print("REBOOT.BAT not found")

    def cmd_exit(self, _): self.running = False

    def cmd_help(self, _):
        print("Commands: VER DIR TYPE CD COPY DEL REN MD RD ECHO SET PATH CLS BASIC REBOOT EXIT HELP")
        print("Drive switching: A:  B:  ...")

    def enter_basic(self, autoexec: bool) -> int:
        print("MSX BASIC compatibility entry requested.")
        bas = self.drive.resolve("AUTOEXEC.BAS")
        if autoexec and bas.exists():
            print(f"AUTOEXEC.BAS detected: {self.dos_name(bas)}")
            print("Execution requires an MSX BASIC interpreter/emulator and is not interpreted by this DOS layer.")
        return 0


def parse_drive(spec: str) -> tuple[str, Path]:
    if "=" not in spec:
        raise argparse.ArgumentTypeError("drive mapping must be LETTER=PATH, e.g. A=./diskA")
    letter, path = spec.split("=", 1)
    letter = letter.upper().rstrip(":")
    if len(letter) != 1 or not letter.isalpha():
        raise argparse.ArgumentTypeError("invalid drive letter")
    return letter, Path(path)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Behavioral Python reimplementation of MSXDOS2.SYS 2.40")
    ap.add_argument("--drive", action="append", default=[], type=parse_drive,
                    help="Map MSX drive to host directory, e.g. --drive A=./diskA")
    ap.add_argument("--boot", default="A", help="Boot drive letter (default A)")
    ap.add_argument("--basic", action="store_true", help="Boot directly to BASIC compatibility entry")
    ap.add_argument("--version", action="store_true")
    ns = ap.parse_args(argv)
    if ns.version:
        print(VERSION); return 0
    mappings = ns.drive or [("A", Path("./diskA"))]
    drives = {letter: VirtualDrive(letter, path) for letter, path in mappings}
    system = MSXDOS2System(drives=drives, current_drive=ns.boot)
    return system.boot(basic=ns.basic)


if __name__ == "__main__":
    raise SystemExit(main())
