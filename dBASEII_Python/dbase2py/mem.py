from __future__ import annotations
from pathlib import Path
import struct, fnmatch

TYPE_CHAR=0xC3; TYPE_NUM=0xCE; TYPE_LOG=0xCC

def save_mem(path: str|Path, variables: dict[str,object]):
    path=Path(path)
    if path.suffix=='': path=path.with_suffix('.MEM')
    out=bytearray()
    for name,val in variables.items():
        h=bytearray(19)
        b=name.upper().encode('ascii','replace')[:10]
        h[:11]=b.ljust(11,b'\0')
        if isinstance(val,bool):
            h[11]=TYPE_LOG; h[12]=17; h[15]=1
            payload=bytearray(17); payload[-1]=1 if val else 0
        elif isinstance(val,(int,float)):
            s=str(val).encode('ascii'); h[11]=TYPE_NUM; h[12]=min(255,len(s)); h[15]=18; h[16]=6
            payload=s
        else:
            s=str(val).encode('cp437','replace'); h[11]=TYPE_CHAR; h[12]=min(255,len(s)); h[15]=min(255,len(s))
            payload=s
        out+=h+payload
    out+=b'\x1a'
    path.write_bytes(out)
    return path

def load_mem(path: str|Path) -> dict[str,object]:
    path=Path(path)
    if path.suffix=='': path=path.with_suffix('.MEM')
    raw=path.read_bytes(); pos=0; out={}
    while pos < len(raw) and raw[pos]!=0x1a:
        if pos+19>len(raw): break
        h=raw[pos:pos+19]; pos+=19
        name=h[:11].split(b'\0',1)[0].decode('ascii','replace').upper()
        typ=h[11]; ln=h[12]
        if typ==TYPE_LOG:
            payload=raw[pos:pos+17]; pos+=17; val=bool(payload[-1]) if payload else False
        else:
            payload=raw[pos:pos+ln]; pos+=ln
            s=payload.decode('cp437','replace').strip('\0 ')
            if typ==TYPE_NUM:
                try: val=float(s) if '.' in s else int(s)
                except: val=0
            else: val=s
        if name: out[name]=val
    return out

def select_vars(variables: dict, like: str|None=None, except_pat: str|None=None):
    if like: return {k:v for k,v in variables.items() if fnmatch.fnmatchcase(k.upper(),like.upper())}
    if except_pat: return {k:v for k,v in variables.items() if not fnmatch.fnmatchcase(k.upper(),except_pat.upper())}
    return dict(variables)
