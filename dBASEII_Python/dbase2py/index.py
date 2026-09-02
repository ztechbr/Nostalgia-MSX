from __future__ import annotations
from pathlib import Path
import json
from .expr import evaluate, Context

class FunctionalIndex:
    """Actual persistent index used by the Python port.

    The original dBASE II NDX B+tree binary representation is platform-specific.
    This port keeps the same user-visible INDEX/FIND semantics and persists a
    deterministic index next to the requested .NDX path in UTF-8 JSON.
    DBF data itself remains native dBASE II.
    """
    def __init__(self,path: str|Path, expression: str, entries=None):
        self.path=Path(path); self.expression=expression
        self.entries=entries or []
    @classmethod
    def build(cls,path,expression,table,ctx_factory):
        p=Path(path)
        if p.suffix=='': p=p.with_suffix('.NDX')
        entries=[]
        for i,rec in enumerate(table.records,1):
            if table.deleted[i-1]: continue
            key=evaluate(expression,ctx_factory(i,rec))
            entries.append((str(key),i,key))
        entries.sort(key=lambda x:(x[2],x[1]))
        idx=cls(p,expression,[(k,r) for k,r,_ in entries]); idx.save(); return idx
    def save(self):
        self.path.write_text(json.dumps({'format':'dbase2py-index-v1','expression':self.expression,'entries':self.entries},ensure_ascii=False),encoding='utf8')
    @classmethod
    def load(cls,path):
        p=Path(path)
        if p.suffix=='': p=p.with_suffix('.NDX')
        obj=json.loads(p.read_text(encoding='utf8'))
        return cls(p,obj['expression'],[(str(k),int(r)) for k,r in obj['entries']])
    def find(self,key,exact=False):
        s=str(key)
        for k,r in self.entries:
            if (k==s) if exact else k.upper().startswith(s.upper()): return r
        return None
