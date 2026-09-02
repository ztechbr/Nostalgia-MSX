from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import re, shlex, fnmatch, csv, os, shutil
from .dbf import DBase2Table, Field
from .expr import evaluate, Context, ExprError
from .mem import save_mem, load_mem, select_vars
from .index import FunctionalIndex

@dataclass
class WorkArea:
    table: DBase2Table|None=None
    recno: int=1
    indexes: list[FunctionalIndex]=field(default_factory=list)
    locate_expr: str|None=None
    locate_next: int=1
    @property
    def eof(self): return bool(self.table) and self.recno > self.table.count
    @property
    def bof(self): return bool(self.table) and self.recno < 1

class DBaseEngine:
    def __init__(self,cwd: str|Path='.'):
        self.cwd=Path(cwd).resolve(); self.cwd.mkdir(parents=True,exist_ok=True)
        self.areas={'PRIMARY':WorkArea(),'SECONDARY':WorkArea()}; self.selected='PRIMARY'
        self.mem: dict[str,object]={}
        self.settings={
            'BELL':True,'CARRY':False,'COLON':True,'CONFIRM':False,'CONSOLE':True,
            'DELETED':False,'ECHO':False,'ESCAPE':True,'EXACT':False,'SAFETY':True,
            'TALK':True,'PRINT':False,'STEP':False,'INTENSITY':True,'RAW':False,
            'ALTERNATE':False,'ALTERNATE_TO':None,'FILTER':None,'FORMAT':None,
            'HEADING':None,'MARGIN':0,'WIDTH':80,'DECIMALS':2,'FIXED':False,
        }
        self.output=[]; self.running=True; self.last_result=None; self.pending_gets=[]
    @property
    def area(self): return self.areas[self.selected]
    def emit(self,s=''):
        s=str(s); self.output.append(s)
        if self.settings.get('CONSOLE',True): print(s)
        alt=self.settings.get('ALTERNATE_TO')
        if self.settings.get('ALTERNATE') and alt:
            with open(self.resolve(alt),'a',encoding='cp437',errors='replace') as f: f.write(s+'\n')
    def resolve(self,name,ext=None):
        p=Path(str(name).strip('"\''))
        if p.suffix=='' and ext: p=p.with_suffix(ext)
        return p if p.is_absolute() else self.cwd/p
    def _ctx(self,area=None,recno=None,record=None):
        a=area or self.area; t=a.table
        if record is None and t and recno is None: recno=a.recno
        if record is None and t and recno and 1<=recno<=t.count: record=t.records[recno-1]
        fields={}
        if record: fields.update({k.upper():v for k,v in record.items()})
        # expose P./S. aliases for JOIN-style expressions
        for an,prefix in [('PRIMARY','P.'),('SECONDARY','S.')]:
            wa=self.areas[an]
            if wa.table and 1<=wa.recno<=wa.table.count:
                for k,v in wa.table.records[wa.recno-1].items(): fields[prefix+k.upper()]=v
        return Context(fields,self.mem,recno or 0,bool(t and recno and 1<=recno<=t.count and t.deleted[recno-1]),bool(t and recno and recno>t.count),self.cwd,bool(self.settings['EXACT']))
    def eval(self,e,**kw): return evaluate(e,self._ctx(**kw))
    def require(self):
        if not self.area.table: raise RuntimeError('NO DATABASE FILE IN USE')
        return self.area.table
    def _scope(self,spec:str,default='CURRENT'):
        t=self.require(); s=spec.strip(); up=s.upper()
        start=end=None
        if re.search(r'\bALL\b',up): start,end=1,t.count
        else:
            m=re.search(r'\bNEXT\s+(\d+)',up)
            if m: start=self.area.recno; end=min(t.count,start+int(m.group(1))-1)
            else:
                m=re.search(r'\bRECORD\s+(\d+)',up)
                if m: start=end=int(m.group(1))
                elif default=='ALL': start,end=1,t.count
                else: start=end=self.area.recno
        return range(max(1,start),min(t.count,end)+1) if t.count else range(0)
    def _for(self,spec):
        m=re.search(r'\bFOR\s+(.+?)(?=\s+(?:FIELDS?|TO|OFF|SDF|DELIMITED|PLAIN|ASCENDING|DESCENDING)\b|$)',spec,re.I)
        return m.group(1).strip() if m else None
    def _visible(self,i,for_expr=None):
        t=self.require()
        if self.settings['DELETED'] and t.deleted[i-1]: return False
        filt=self.settings.get('FILTER')
        rec=t.records[i-1]
        try:
            if filt and not bool(self.eval(filt,recno=i,record=rec)): return False
            if for_expr and not bool(self.eval(for_expr,recno=i,record=rec)): return False
        except ExprError: return False
        return True
    def _save_refresh(self):
        t=self.require(); t.save()
        for idx in list(self.area.indexes):
            try: FunctionalIndex.build(idx.path,idx.expression,t,lambda i,r:self._ctx(recno=i,record=r))
            except Exception: pass
    def execute(self,line:str):
        raw=line.rstrip(); line=raw.strip()
        if not line: return None
        if self.settings['ECHO']: self.emit('. '+line)
        if line.startswith('*') or line.upper().startswith('NOTE ') or line.upper().startswith('REMARK '): return None
        if line.startswith('@'):
            self.last_result=self.cmd_at(line[1:].strip()); return self.last_result
        if line.startswith('?'):
            exprs=[x.strip() for x in self._split_csv(line[1:])]
            vals=[]
            for e in exprs:
                try: vals.append(self.eval(e))
                except Exception: vals.append(e)
            self.emit(' '.join(str(v) for v in vals)); return vals
        cmd,*rest=line.split(None,1); c=cmd.upper(); arg=rest[0] if rest else ''
        aliases={'GO':'GOTO','ERASE':'DELETEFILE'}
        if c=='DELETE' and arg.upper().startswith('FILE '): c='DELETEFILE'; arg=arg[5:].strip()
        c=aliases.get(c,c)
        meth=getattr(self,'cmd_'+c.lower(),None)
        if not meth: raise RuntimeError('*** UNKNOWN COMMAND')
        self.last_result=meth(arg); return self.last_result
    @staticmethod
    def _split_csv(s):
        out=[]; cur=''; q=None; depth=0
        for ch in s:
            if q:
                cur+=ch
                if ch==q: q=None
            elif ch in "'\"": q=ch; cur+=ch
            elif ch=='(': depth+=1; cur+=ch
            elif ch==')': depth-=1; cur+=ch
            elif ch==',' and depth==0: out.append(cur); cur=''
            else: cur+=ch
        if cur.strip() or not out: out.append(cur)
        return out
    def cmd_use(self,arg):
        if not arg.strip(): self.area.table=None; self.area.indexes=[]; return
        m=re.match(r'([^\s]+)(?:\s+INDEX\s+(.+))?$',arg,re.I); name=m.group(1); idxs=m.group(2) if m else None
        p=self.resolve(name,'.DBF'); self.area.table=DBase2Table(p); self.area.recno=1; self.area.indexes=[]
        if idxs:
            for x in self._split_csv(idxs): self.area.indexes.append(FunctionalIndex.load(self.resolve(x.strip(),'.NDX')))
    def cmd_select(self,arg):
        u=arg.strip().upper()
        if u in ('PRIMARY','1'): self.selected='PRIMARY'
        elif u in ('SECONDARY','2'): self.selected='SECONDARY'
        else: raise RuntimeError('SELECT PRIMARY or SECONDARY')
    def cmd_create(self,arg):
        name=arg.strip() or input('FILENAME: ').strip()
        fields=[]
        self.emit('ENTER RECORD STRUCTURE. Blank field name finishes.')
        while True:
            n=input('FIELD NAME: ').strip()
            if not n: break
            typ=input('TYPE (C/N/L): ').strip().upper() or 'C'
            ln=1 if typ=='L' else int(input('WIDTH: ').strip() or '10')
            dec=int(input('DECIMALS: ').strip() or '0') if typ=='N' else 0
            fields.append(Field(n,typ,ln,dec))
        self.area.table=DBase2Table.create(self.resolve(name,'.DBF'),fields); self.area.recno=1
    def cmd_append(self,arg):
        t=self.require(); u=arg.upper().strip()
        if u=='BLANK': self.area.recno=t.append(); self._save_refresh(); return self.area.recno
        m=re.match(r'FROM\s+([^\s]+)(.*)$',arg,re.I)
        if m:
            src=self.resolve(m.group(1)); tail=m.group(2); forx=self._for(tail)
            if src.suffix.upper()=='.DBF' or (src.suffix=='' and src.with_suffix('.DBF').exists()):
                if src.suffix=='': src=src.with_suffix('.DBF')
                st=DBase2Table(src); n=0
                for i,r in enumerate(st.records,1):
                    if st.deleted[i-1]: continue
                    if forx and not evaluate(forx,Context(r,self.mem,i,False,False,self.cwd,bool(self.settings['EXACT']))): continue
                    t.append(r); n+=1
            else:
                delim='DELIMITED' in tail.upper(); n=0
                for line in src.read_text('cp437',errors='replace').splitlines():
                    vals=next(csv.reader([line])) if delim else [line[pos:pos+f.length].strip() for pos,f in self._field_positions(t)]
                    t.append({f.name:(vals[j] if j<len(vals) else '') for j,f in enumerate(t.fields)}); n+=1
            self._save_refresh(); self.emit(f'{n} RECORDS ADDED'); return n
        # interactive real data entry
        vals={}
        for f in t.fields:
            x=input(f'{f.name}: ')
            if f.type=='N':
                try:x=float(x) if '.' in x else int(x)
                except:x=0
            elif f.type=='L': x=x[:1].upper() in 'YT1'
            vals[f.name]=x
        self.area.recno=t.append(vals); self._save_refresh(); return self.area.recno
    @staticmethod
    def _field_positions(t):
        pos=0
        for f in t.fields: yield pos,f; pos+=f.length
    def _parse_fields(self,arg,t):
        m=re.search(r'\bFIELDS?\s+(.+?)(?=\s+FOR\b|\s+OFF\b|$)',arg,re.I)
        if m: return [x.strip().upper() for x in self._split_csv(m.group(1))]
        # explicit expression list before FOR/FIELDS is hard to distinguish; default all
        return [f.name for f in t.fields]
    def _display_records(self,arg,default):
        t=self.require(); forx=self._for(arg); fields=self._parse_fields(arg,t); rows=[]
        for i in self._scope(arg,default):
            if not self._visible(i,forx): continue
            r=t.records[i-1]; row=[i]+[r.get(f,'') for f in fields]; rows.append(row)
        self.emit('RECNO '+ ' '.join(fields))
        for row in rows: self.emit(str(row[0]).rjust(5)+' '+ ' '.join(str(x) for x in row[1:]))
        return rows
    def cmd_list(self,arg):
        u=arg.upper().strip()
        if u.startswith('FILES'): return self._files(arg)
        if u=='STRUCTURE': return self.cmd_display('STRUCTURE')
        if u=='MEMORY': return self.cmd_display('MEMORY')
        if u=='STATUS': return self.cmd_display('STATUS')
        return self._display_records(arg,'ALL')
    def cmd_display(self,arg):
        u=arg.upper().strip(); t=self.area.table
        if u.startswith('FILES'): return self._files(arg)
        if u=='MEMORY':
            for k,v in self.mem.items(): self.emit(f'{k:10} {type(v).__name__:8} {v}')
            return dict(self.mem)
        if u=='STATUS':
            self.emit(f'SELECTED: {self.selected}')
            for n,a in self.areas.items(): self.emit(f'{n}: {a.table.path if a.table else "<none>"} RECNO {a.recno}')
            for k,v in self.settings.items(): self.emit(f'SET {k} {v}')
            return
        if u=='STRUCTURE':
            t=self.require(); self.emit('FIELD NAME TYPE WIDTH DEC')
            for f in t.fields: self.emit(f'{f.name:10} {f.type} {f.length:5} {f.decimals:3}')
            return t.structure()
        return self._display_records(arg,'CURRENT')
    def _files(self,arg):
        m=re.search(r'LIKE\s+([^\s]+)',arg,re.I); pat=m.group(1) if m else '*'
        xs=sorted(p.name for p in self.cwd.iterdir() if p.is_file() and fnmatch.fnmatch(p.name.upper(),pat.upper()))
        for x in xs:self.emit(x)
        return xs
    def cmd_replace(self,arg):
        t=self.require(); forx=self._for(arg); before=re.split(r'\bFOR\b',arg,flags=re.I)[0]
        # strip scope keywords
        body=re.sub(r'^\s*(ALL|NEXT\s+\d+|RECORD\s+\d+)\s+','',before,flags=re.I)
        pairs=[]
        for part in self._split_csv(body):
            m=re.match(r'([A-Za-z_][\w]*)\s+WITH\s+(.+)$',part.strip(),re.I)
            if not m: raise RuntimeError('SYNTAX ERROR, RE-ENTER')
            pairs.append((m.group(1).upper(),m.group(2).strip()))
        n=0
        for i in self._scope(arg,'CURRENT'):
            if not self._visible(i,forx): continue
            rec=t.records[i-1]
            vals=[(f,self.eval(e,recno=i,record=rec)) for f,e in pairs]
            for f,v in vals: rec[f]=v
            n+=1
        self._save_refresh(); self.emit(f'{n} REPLACEMENT(S)'); return n
    def cmd_delete(self,arg):
        t=self.require(); forx=self._for(arg); n=0
        for i in self._scope(arg,'CURRENT'):
            if self._visible(i,forx): t.deleted[i-1]=True; n+=1
        self._save_refresh(); self.emit(f'{n} DELETION(S)'); return n
    def cmd_deletefile(self,arg):
        p=self.resolve(arg.strip());
        if p.exists(): p.unlink(); return True
        return False
    def cmd_recall(self,arg):
        t=self.require(); forx=self._for(arg); n=0
        for i in self._scope(arg,'CURRENT'):
            if (not forx or bool(self.eval(forx,recno=i,record=t.records[i-1]))) and t.deleted[i-1]: t.deleted[i-1]=False; n+=1
        self._save_refresh(); self.emit(f'{n} RECALL(S)'); return n
    def _edit_record(self, recno=None):
        t=self.require(); i=recno or self.area.recno
        if not (1 <= i <= t.count): raise RuntimeError('RECORD OUT OF RANGE')
        rec=t.records[i-1]
        for f in t.fields:
            old=rec.get(f.name,''); s=input(f'{f.name} [{old}]: ')
            if s=='': continue
            if f.type=='N':
                try: s=float(s) if '.' in s else int(s)
                except: s=0
            elif f.type=='L': s=s[:1].upper() in 'YT1'
            rec[f.name]=s
        self._save_refresh(); return i
    def cmd_edit(self,arg):
        m=re.search(r'(?:RECORD\s+)?(\d+)',arg,re.I); return self._edit_record(int(m.group(1)) if m else None)
    def cmd_change(self,arg): return self.cmd_edit(arg)
    def cmd_browse(self,arg): return self._display_records(arg,'ALL')
    def cmd_insert(self,arg):
        t=self.require(); pos=max(0,min(t.count,self.area.recno-1))
        blank={f.name:('' if f.type=='C' else False if f.type=='L' else 0) for f in t.fields}
        t.records.insert(pos,blank); t.deleted.insert(pos,False); self.area.recno=pos+1; self._save_refresh()
        return self._edit_record(self.area.recno) if arg.upper().strip()!='BLANK' else self.area.recno
    def cmd_pack(self,arg): self.require().pack(); self.area.recno=min(self.area.recno,max(1,self.require().count)); return self.require().count
    def cmd_goto(self,arg):
        t=self.require(); a=arg.strip().upper()
        if a=='TOP': n=1
        elif a=='BOTTOM': n=t.count
        else:
            a=re.sub(r'^RECORD\s+','',a); n=int(self.mem.get(a,a))
        self.area.recno=n; return n
    def cmd_skip(self,arg):
        n=int(arg.strip() or '1'); self.area.recno+=n; return self.area.recno
    def cmd_count(self,arg):
        forx=self._for(arg); n=sum(1 for i in self._scope(arg,'ALL') if self._visible(i,forx))
        m=re.search(r'\bTO\s+(\w+)',arg,re.I)
        if m:self.mem[m.group(1).upper()]=n
        self.emit(f'COUNT = {n}'); return n
    def cmd_sum(self,arg):
        t=self.require(); forx=self._for(arg)
        core=re.split(r'\b(?:ALL|NEXT|RECORD|TO|FOR)\b',arg,flags=re.I)[0].strip()
        exprs=[x.strip() for x in self._split_csv(core) if x.strip()]
        totals=[0.0]*len(exprs)
        for i in self._scope(arg,'ALL'):
            if self._visible(i,forx):
                for j,e in enumerate(exprs): totals[j]+=float(self.eval(e,recno=i,record=t.records[i-1]))
        m=re.search(r'\bTO\s+(.+?)(?=\s+FOR\b|$)',arg,re.I)
        if m:
            names=[x.strip().upper() for x in self._split_csv(m.group(1))]
            for k,v in zip(names,totals): self.mem[k]=v
        self.emit(' '.join(str(int(v) if v.is_integer() else v) for v in totals)); return totals
    def cmd_store(self,arg):
        m=re.match(r'(.+?)\s+TO\s+(\w+)\s*$',arg,re.I)
        if not m: raise RuntimeError('SYNTAX ERROR, RE-ENTER')
        v=self.eval(m.group(1)); self.mem[m.group(2).upper()]=v; self.emit(v); return v
    def cmd_release(self,arg):
        a=arg.strip(); u=a.upper()
        if u=='ALL': self.mem.clear(); return
        m=re.match(r'ALL\s+(LIKE|EXCEPT)\s+(.+)',a,re.I)
        if m:
            mode,pat=m.group(1).upper(),m.group(2).strip(); keep=select_vars(self.mem,like=pat if mode=='LIKE' else None,except_pat=pat if mode=='EXCEPT' else None)
            if mode=='LIKE':
                for k in list(keep): self.mem.pop(k,None)
            else:self.mem=keep
            return
        for k in self._split_csv(a): self.mem.pop(k.strip().upper(),None)
    def cmd_save(self,arg):
        m=re.match(r'TO\s+([^\s]+)(.*)',arg,re.I); 
        if not m: raise RuntimeError('SAVE TO <file>')
        tail=m.group(2); like=exceptp=None
        q=re.search(r'ALL\s+(LIKE|EXCEPT)\s+(.+)',tail,re.I)
        if q:
            if q.group(1).upper()=='LIKE': like=q.group(2).strip()
            else: exceptp=q.group(2).strip()
        return save_mem(self.resolve(m.group(1),'.MEM'),select_vars(self.mem,like,exceptp))
    def cmd_restore(self,arg):
        m=re.match(r'FROM\s+([^\s]+)(?:\s+(ADDITIVE))?',arg,re.I); 
        if not m: raise RuntimeError('RESTORE FROM <file>')
        vals=load_mem(self.resolve(m.group(1),'.MEM'))
        if not m.group(2): self.mem.clear()
        self.mem.update(vals); return vals
    def cmd_index(self,arg):
        m=re.match(r'ON\s+(.+?)\s+TO\s+([^\s]+)$',arg,re.I)
        if not m: raise RuntimeError('INDEX ON <expr> TO <file>')
        t=self.require(); idx=FunctionalIndex.build(self.resolve(m.group(2),'.NDX'),m.group(1).strip(),t,lambda i,r:self._ctx(recno=i,record=r)); self.area.indexes=[idx]; return idx.path
    def cmd_reindex(self,arg):
        t=self.require(); new=[]
        for idx in self.area.indexes: new.append(FunctionalIndex.build(idx.path,idx.expression,t,lambda i,r:self._ctx(recno=i,record=r)))
        self.area.indexes=new
    def cmd_find(self,arg):
        if not self.area.indexes: raise RuntimeError('INDEX FILE CANNOT BE OPENED')
        key=arg.strip().strip('"\'')
        n=self.area.indexes[0].find(key,bool(self.settings['EXACT']))
        self.area.recno=n if n else self.require().count+1; return n
    def cmd_locate(self,arg):
        t=self.require(); forx=self._for(arg)
        if not forx: raise RuntimeError('SYNTAX ERROR, RE-ENTER')
        self.area.locate_expr=forx; self.area.locate_next=1
        return self._continue_locate()
    def _continue_locate(self):
        t=self.require(); e=self.area.locate_expr
        if not e: return None
        for i in range(self.area.locate_next,t.count+1):
            if self._visible(i,e): self.area.recno=i; self.area.locate_next=i+1; self.emit(f'RECORD: {i:05d}'); return i
        self.area.recno=t.count+1; self.emit('END OF LOCATE SCOPE'); return None
    def cmd_continue(self,arg): return self._continue_locate()
    def cmd_sort(self,arg):
        m=re.match(r'ON\s+(.+?)\s+TO\s+([^\s]+)(?:\s+(ASCENDING|DESCENDING))?',arg,re.I)
        if not m: raise RuntimeError('SORT ON <field> TO <file>')
        t=self.require(); expr=m.group(1).strip(); dest=self.resolve(m.group(2),'.DBF'); rev=(m.group(3) or '').upper()=='DESCENDING'
        rows=[(self.eval(expr,recno=i,record=r),r) for i,r in enumerate(t.records,1) if not t.deleted[i-1]]
        rows.sort(key=lambda x:x[0],reverse=rev); nt=DBase2Table.create(dest,t.structure());
        for _,r in rows: nt.append(r)
        nt.save(); self.emit(f'{len(rows)} RECORDS SORTED'); return dest
    def cmd_copy(self,arg):
        t=self.require(); m=re.search(r'\bTO\s+([^\s]+)',arg,re.I)
        if not m: raise RuntimeError('COPY TO <file>')
        dest=m.group(1); forx=self._for(arg); fields=self._parse_fields(arg,t)
        if 'SDF' in arg.upper() or 'DELIMITED' in arg.upper():
            p=self.resolve(dest,'.TXT'); delim='DELIMITED' in arg.upper(); rows=[]
            for i in self._scope(arg,'ALL'):
                if not t.deleted[i-1] and self._visible(i,forx): rows.append([t.records[i-1].get(f,'') for f in fields])
            with open(p,'w',newline='',encoding='cp437',errors='replace') as f:
                if delim: csv.writer(f).writerows(rows)
                else:
                    for row in rows: f.write(''.join(str(v) for v in row)+'\n')
            return p
        fs=[f for f in t.structure() if f.name in fields]; nt=DBase2Table.create(self.resolve(dest,'.DBF'),fs)
        if 'STRUCTURE' not in arg.upper():
            for i in self._scope(arg,'ALL'):
                if not t.deleted[i-1] and self._visible(i,forx): nt.append({f:t.records[i-1].get(f) for f in fields})
        nt.save(); self.emit(f'{nt.count} RECORDS COPIED'); return nt.path
    def cmd_total(self,arg):
        m=re.match(r'TO\s+([^\s]+)\s+ON\s+([^\s]+)(?:\s+FIELDS?\s+(.+))?',arg,re.I)
        if not m: raise RuntimeError('TOTAL TO <file> ON <key> [FIELDS <list>]')
        t=self.require(); key=m.group(2).upper(); sums=[x.strip().upper() for x in self._split_csv(m.group(3) or '') if x.strip()]
        groups={}
        for i,r in enumerate(t.records,1):
            if t.deleted[i-1]: continue
            k=r.get(key)
            if k not in groups:
                groups[k]=dict(r)
            else:
                for f in sums: groups[k][f]=float(groups[k].get(f,0))+float(r.get(f,0))
        nt=DBase2Table.create(self.resolve(m.group(1),'.DBF'),t.structure())
        for r in groups.values(): nt.append(r)
        nt.save(); return nt.path
    def cmd_join(self,arg):
        m=re.match(r'TO\s+([^\s]+)\s+FOR\s+(.+?)(?:\s+FIELDS?\s+(.+))?$',arg,re.I)
        if not m: raise RuntimeError('JOIN TO <file> FOR <expr> [FIELDS ...]')
        pwa,swa=self.areas['PRIMARY'],self.areas['SECONDARY']
        if self.selected!='PRIMARY' or not pwa.table or not swa.table: raise RuntimeError('PRIMARY and SECONDARY databases required')
        allfields=[]
        for f in pwa.table.fields: allfields.append(Field(f.name,f.type,f.length,f.decimals))
        existing={f.name for f in allfields}
        for f in swa.table.fields:
            name=f.name if f.name not in existing else ('S_'+f.name)[:10]; allfields.append(Field(name,f.type,f.length,f.decimals)); existing.add(name)
        nt=DBase2Table.create(self.resolve(m.group(1),'.DBF'),allfields); e=m.group(2)
        oldp,olds=pwa.recno,swa.recno
        for pi,pr in enumerate(pwa.table.records,1):
            if pwa.table.deleted[pi-1]: continue
            pwa.recno=pi
            for si,sr in enumerate(swa.table.records,1):
                if swa.table.deleted[si-1]: continue
                swa.recno=si
                if bool(self.eval(e,area=pwa,recno=pi,record=pr)):
                    row=dict(pr)
                    for k,v in sr.items(): row[k if k not in row else ('S_'+k)[:10]]=v
                    nt.append(row)
        pwa.recno, swa.recno=oldp,olds; nt.save(); return nt.path
    def cmd_update(self,arg):
        m=re.match(r'FROM\s+([^\s]+)\s+ON\s+([^\s]+)(.*)$',arg,re.I)
        if not m: raise RuntimeError('UPDATE FROM <file> ON <key> [ADD ...] [REPLACE ...]')
        t=self.require(); src=DBase2Table(self.resolve(m.group(1),'.DBF')); key=m.group(2).upper(); tail=m.group(3)
        add=[]; repl=[]
        ma=re.search(r'\bADD\s+(.+?)(?=\s+REPLACE\b|$)',tail,re.I)
        if ma: add=[x.strip().upper() for x in self._split_csv(ma.group(1))]
        mr=re.search(r'\bREPLACE\s+(.+)$',tail,re.I)
        if mr: repl=[x.strip().upper() for x in self._split_csv(mr.group(1))]
        lookup={r.get(key):r for i,r in enumerate(src.records,1) if not src.deleted[i-1]}
        n=0
        for i,r in enumerate(t.records,1):
            if t.deleted[i-1]: continue
            other=lookup.get(r.get(key))
            if other is None: continue
            for f in add: r[f]=float(r.get(f,0))+float(other.get(f,0))
            for f in repl: r[f]=other.get(f,r.get(f))
            n+=1
        self._save_refresh(); return n
    def cmd_modify(self,arg):
        u=arg.upper().strip()
        if u.startswith('STRUCTURE'):
            t=self.require(); self.emit('MODIFY STRUCTURE requires creating a replacement structure interactively.')
            fields=[]
            for f in t.fields:
                name=input(f'FIELD [{f.name}]: ').strip() or f.name
                typ=input(f'TYPE [{f.type}]: ').strip().upper() or f.type
                ln=1 if typ=='L' else int(input(f'WIDTH [{f.length}]: ').strip() or f.length)
                dec=int(input(f'DECIMALS [{f.decimals}]: ').strip() or f.decimals) if typ=='N' else 0
                fields.append(Field(name,typ,ln,dec))
            tmp=t.path.with_suffix('.TMP'); nt=DBase2Table.create(tmp,fields)
            for r,d in zip(t.records,t.deleted): nt.append(r); nt.deleted[-1]=d
            nt.save(); tmp.replace(t.path); self.area.table=DBase2Table(t.path); return
        raise RuntimeError('MODIFY STRUCTURE supported')
    def cmd_report(self,arg):
        # Functional report output over selected records. FRM binary layout is not used by the Python runtime.
        return self._display_records(arg,'ALL')
    def cmd_set(self,arg):
        a=arg.strip(); m=re.match(r'(\w+)\s*(.*)',a); key=m.group(1).upper(); rest=m.group(2).strip()
        if key=='FILTER': self.settings['FILTER']=re.sub(r'^TO\s+','',rest,flags=re.I) or None; return
        if key in ('ALTERNATE','FORMAT','HEADING') and rest.upper().startswith('TO '): self.settings[key+'_TO' if key=='ALTERNATE' else key]=rest[3:].strip().strip('"\''); return
        if rest.upper() in ('ON','OFF'): self.settings[key]=rest.upper()=='ON'; return self.settings[key]
        if rest.upper().startswith('TO '): rest=rest[3:].strip()
        if key in ('WIDTH','MARGIN','DECIMALS'): self.settings[key]=int(rest); return
        self.settings[key]=rest
    def cmd_at(self,arg):
        m=re.match(r'(\d+)\s*,\s*(\d+)\s+SAY\s+(.+)$',arg,re.I)
        if not m: raise RuntimeError('@ row,col SAY <expr> [GET <var>]')
        row,col=int(m.group(1)),int(m.group(2)); tail=m.group(3)
        gm=re.search(r'\s+GET\s+(\w+)(?:\s+PICTURE\s+(.+))?$',tail,re.I)
        if gm:
            var=gm.group(1).upper(); say=tail[:gm.start()].strip(); picture=gm.group(2)
            self.pending_gets.append((row,col,var,picture))
        else: say=tail
        try: val=self.eval(say)
        except Exception: val=say.strip('"\'')
        # ANSI cursor positioning provides a real text terminal equivalent.
        if self.settings.get('CONSOLE',True): print(f'\033[{row+1};{col+1}H{val}',end='')
        return val
    def cmd_read(self,arg):
        for row,col,var,picture in self.pending_gets:
            old=self.mem.get(var,'')
            prompt=f'\n{var} [{old}]: '
            s=input(prompt)
            if s=='': continue
            if isinstance(old,bool): self.mem[var]=s[:1].upper() in 'YT1'
            elif isinstance(old,(int,float)):
                try:self.mem[var]=float(s) if '.' in s else int(s)
                except:self.mem[var]=old
            else:self.mem[var]=s
        self.pending_gets.clear()
        return None
    def cmd_accept(self,arg):
        m=re.match(r'''(?:(['"])(.*?)\1\s*)?TO\s+(\w+)''',arg,re.I)
        if not m: raise RuntimeError('ACCEPT [prompt] TO <memvar>')
        v=input((m.group(2) or '')+(': ' if m.group(2) else '')); self.mem[m.group(3).upper()]=v; return v
    def cmd_input(self,arg):
        m=re.match(r'''(?:(['"])(.*?)\1\s*)?TO\s+(\w+)''',arg,re.I)
        if not m: raise RuntimeError('INPUT [prompt] TO <memvar>')
        s=input((m.group(2) or '')+(': ' if m.group(2) else ''))
        try:v=self.eval(s)
        except:v=s
        self.mem[m.group(3).upper()]=v; return v
    def cmd_wait(self,arg): input(arg.strip().strip('"\'') or 'Press RETURN to continue...'); return
    def cmd_clear(self,arg): self.emit('\033[2J\033[H')
    def cmd_eject(self,arg): self.emit('\f')
    def cmd_reset(self,arg): self.__init__(self.cwd)
    def cmd_rename(self,arg):
        m=re.match(r'([^\s]+)\s+TO\s+([^\s]+)',arg,re.I); os.rename(self.resolve(m.group(1)),self.resolve(m.group(2)))
    def cmd_quit(self,arg): self.running=False
    def cmd_cancel(self,arg): self.running=False
    def cmd_help(self,arg):
        topic=arg.strip().upper(); self.emit('dBASE II Python port. Commands: USE CREATE APPEND LIST DISPLAY REPLACE DELETE RECALL PACK GOTO SKIP COUNT SUM STORE RELEASE SAVE RESTORE INDEX REINDEX FIND LOCATE CONTINUE SORT COPY TOTAL JOIN SET SELECT DO IF/CASE via .CMD, ACCEPT INPUT WAIT RENAME QUIT')
    def cmd_do(self,arg):
        name=arg.strip().split()[0]; return self.run_cmd(self.resolve(name,'.CMD'))
    def run_cmd(self,path: str|Path):
        p=Path(path); lines=p.read_text('cp437',errors='replace').splitlines(); return ScriptRunner(self).run(lines)

class ScriptRunner:
    """Executes dBASE II .CMD control flow, not a screen simulation."""
    def __init__(self,engine): self.e=engine
    def run(self,lines):
        i=0; ret=None
        while i < len(lines) and self.e.running:
            raw=lines[i].strip(); up=raw.upper()
            if not raw or raw.startswith('*') or up.startswith('NOTE ') or up.startswith('REMARK '): i+=1; continue
            if up=='TEXT':
                end=i+1
                while end < len(lines) and lines[end].strip().upper()!='ENDTEXT':
                    self.e.emit(lines[end]); end+=1
                if end>=len(lines): raise RuntimeError('ENDTEXT missing')
                i=end+1; continue
            if up.startswith('IF '):
                cond=bool(self.e.eval(raw[3:])); else_i,end_i=self._find_if(lines,i)
                block=lines[i+1:(else_i if else_i is not None else end_i)] if cond else (lines[else_i+1:end_i] if else_i is not None else [])
                ret=self.run(block); i=end_i+1; continue
            if up.startswith('DO WHILE '):
                end=self._find_end(lines,i,'DO WHILE','ENDDO'); guard=0
                while bool(self.e.eval(raw[9:])) and self.e.running:
                    ret=self.run(lines[i+1:end]); guard+=1
                    if guard>100000: raise RuntimeError('Loop limit exceeded')
                i=end+1; continue
            if up=='DO CASE':
                end=self._find_end(lines,i,'DO CASE','ENDCASE'); clauses=[]; start=i+1; marker=None
                j=i+1
                while j<end:
                    u=lines[j].strip().upper()
                    if u.startswith('CASE ') or u=='OTHERWISE':
                        if marker is not None: clauses.append((marker,start,j))
                        marker=lines[j].strip(); start=j+1
                    j+=1
                if marker is not None: clauses.append((marker,start,end))
                for mark,a,b in clauses:
                    if mark.upper()=='OTHERWISE' or bool(self.e.eval(mark[5:])):
                        ret=self.run(lines[a:b]); break
                i=end+1; continue
            if up in ('RETURN','EXIT'):
                return ret
            self.e.execute(raw); i+=1
        return ret
    def _find_if(self,lines,i):
        depth=0; else_i=None
        for j in range(i+1,len(lines)):
            u=lines[j].strip().upper()
            if u.startswith('IF '): depth+=1
            elif u=='ENDIF':
                if depth==0:return else_i,j
                depth-=1
            elif u=='ELSE' and depth==0: else_i=j
        raise RuntimeError('ENDIF missing')
    def _find_end(self,lines,i,startkw,endkw):
        depth=0
        for j in range(i+1,len(lines)):
            u=lines[j].strip().upper()
            if u.startswith(startkw): depth+=1
            elif u==endkw:
                if depth==0:return j
                depth-=1
        raise RuntimeError(f'{endkw} missing')
