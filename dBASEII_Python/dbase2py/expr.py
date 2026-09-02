from __future__ import annotations
import re, math
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime

TOKEN_RE = re.compile(r'''\s*(
    \.AND\.|\.OR\.|\.NOT\.|\.T\.|\.F\.|>=|<=|<>|!=|==|=|\#|>|<|\+|-|\*|/|\$|\(|\)|,|
    '(?:[^']|'')*'|"(?:[^"]|"")*"|
    \d+(?:\.\d+)?|
    [A-Za-z_][A-Za-z0-9_.]*|
    @|!|\?
)''', re.I|re.X)

class ExprError(ValueError): pass

@dataclass
class Context:
    fields: dict
    mem: dict
    recno: int = 0
    deleted: bool = False
    eof: bool = False
    cwd: Path = Path('.')
    exact: bool = False

class Parser:
    def __init__(self, text: str, ctx: Context):
        self.text=text.strip(); self.ctx=ctx
        self.toks=[m.group(1) for m in TOKEN_RE.finditer(self.text)]
        compact=''.join(self.text.split())
        found=''.join(t.replace(' ','') for t in self.toks)
        if compact and not self.toks:
            raise ExprError(f'Cannot parse expression: {text}')
        self.i=0
    def peek(self): return self.toks[self.i] if self.i < len(self.toks) else None
    def pop(self):
        t=self.peek()
        if t is not None: self.i+=1
        return t
    def accept(self,*vals):
        p=self.peek()
        if p is not None and p.upper() in {v.upper() for v in vals}:
            self.i+=1; return p
        return None
    def parse(self):
        v=self.or_expr()
        if self.peek() is not None: raise ExprError(f'Unexpected token {self.peek()}')
        return v
    def or_expr(self):
        v=self.and_expr()
        while self.accept('.OR.'):
            v=bool(v) or bool(self.and_expr())
        return v
    def and_expr(self):
        v=self.not_expr()
        while self.accept('.AND.'):
            v=bool(v) and bool(self.not_expr())
        return v
    def not_expr(self):
        if self.accept('.NOT.'):
            return not bool(self.not_expr())
        return self.compare()
    def compare(self):
        a=self.add()
        op=self.accept('=','==','<>','!=','#','>','<','>=','<=','$')
        if not op: return a
        b=self.add()
        if op == '$': return str(a) in str(b)
        if isinstance(a,str) and isinstance(b,str) and op in ('=','==','<>','!=','#') and not self.ctx.exact:
            n=min(len(a),len(b)); eq=a[:n].upper()==b[:n].upper()
        else:
            try: eq=a==b
            except Exception: eq=False
        if op in ('=','=='): return eq
        if op in ('<>','!=','#'): return not eq
        try:
            if op=='>': return a>b
            if op=='<': return a<b
            if op=='>=': return a>=b
            if op=='<=': return a<=b
        except TypeError:
            sa,sb=str(a),str(b)
            return {'>':sa>sb,'<':sa<sb,'>=':sa>=sb,'<=':sa<=sb}[op]
    def add(self):
        v=self.mul()
        while True:
            op=self.accept('+','-')
            if not op: break
            r=self.mul()
            if op=='+':
                v=(str(v)+str(r)) if isinstance(v,str) or isinstance(r,str) else v+r
            else: v=float(v)-float(r)
        return v
    def mul(self):
        v=self.unary()
        while True:
            op=self.accept('*','/')
            if not op: break
            r=self.unary(); v=float(v)*float(r) if op=='*' else float(v)/float(r)
        return int(v) if isinstance(v,float) and v.is_integer() else v
    def unary(self):
        if self.accept('-'): return -float(self.unary())
        if self.accept('+'): return +float(self.unary())
        if self.accept('!'):
            if self.accept('('):
                v=self.or_expr(); self.accept(')'); return str(v).upper()
            return str(self.unary()).upper()
        return self.primary()
    def primary(self):
        t=self.pop()
        if t is None: raise ExprError('Unexpected end of expression')
        if t=='(':
            v=self.or_expr()
            if not self.accept(')'): raise ExprError('Missing )')
            return v
        if t[0:1] in ('\'', '"'):
            return t[1:-1].replace(t[0]*2,t[0])
        if re.fullmatch(r'\d+(?:\.\d+)?',t): return float(t) if '.' in t else int(t)
        u=t.upper()
        if u=='.T.': return True
        if u=='.F.': return False
        if u=='#': return self.ctx.recno
        if u=='*': return self.ctx.deleted
        # function or variable
        if self.peek()=='(':
            self.pop(); args=[]
            if self.peek()!=')':
                while True:
                    args.append(self.or_expr())
                    if not self.accept(','): break
            if not self.accept(')'): raise ExprError('Missing )')
            return self.call(u,args)
        if u=='EOF': return self.ctx.eof
        if u in self.ctx.fields: return self.ctx.fields[u]
        if u.startswith('P.') or u.startswith('S.'):
            return self.ctx.fields.get(u)
        if u in self.ctx.mem: return self.ctx.mem[u]
        raise ExprError(f'Undefined: {t}')
    def call(self,n,args):
        if n=='CHR': return chr(int(args[0]) & 0xff)
        if n=='DATE': return datetime.now().strftime('%m/%d/%y')
        if n=='INT': return math.floor(float(args[0]))
        if n=='LEN': return len(str(args[0]))
        if n=='RANK': return ord(str(args[0])[:1]) if str(args[0]) else 0
        if n=='STR':
            val=float(args[0]); width=int(args[1]) if len(args)>1 else 10; dec=int(args[2]) if len(args)>2 else 0
            return (f'{val:.{dec}f}' if dec else str(int(val))).rjust(width)
        if n=='VAL':
            s=str(args[0]).strip()
            try: return float(s) if '.' in s else int(s)
            except: return 0
        if n=='TRIM': return str(args[0]).rstrip()
        if n=='TYPE':
            v=args[0]
            return 'L' if isinstance(v,bool) else 'N' if isinstance(v,(int,float)) else 'C' if isinstance(v,str) else 'U'
        if n=='FILE':
            p=self.ctx.cwd / str(args[0])
            return p.exists() or p.with_suffix('.DBF').exists()
        if n=='AT' or n=='@':
            a,b=str(args[0]),str(args[1]); x=b.find(a); return x+1 if x>=0 else 0
        if n=='$':
            s=str(args[0]); start=max(1,int(args[1])); ln=int(args[2]); return s[start-1:start-1+ln]
        if n=='TEST':
            return 1
        raise ExprError(f'Unknown function {n}')

def evaluate(text: str, ctx: Context):
    return Parser(text,ctx).parse()
