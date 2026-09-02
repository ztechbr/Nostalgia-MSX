from __future__ import annotations
import argparse
from pathlib import Path
from .engine import DBaseEngine

def main(argv=None):
    ap=argparse.ArgumentParser(description='Native Python reimplementation of dBASE II 2.4 command environment')
    ap.add_argument('--cwd',default='.',help='Working directory containing DBF/CMD files')
    ap.add_argument('--cmd',help='Execute a .CMD file and exit')
    ap.add_argument('-c','--command',action='append',help='Execute command(s) and exit')
    ns=ap.parse_args(argv); e=DBaseEngine(ns.cwd)
    print('dBASE II Python 2.4 compatible engine')
    print('Native Python implementation, no Z80/MSX emulation')
    if ns.cmd: e.run_cmd(e.resolve(ns.cmd,'.CMD')); return
    if ns.command:
        for c in ns.command:e.execute(c)
        return
    while e.running:
        try: line=input('. '); e.execute(line)
        except (EOFError,KeyboardInterrupt): print(); break
        except Exception as ex: print(ex)
if __name__=='__main__': main()
