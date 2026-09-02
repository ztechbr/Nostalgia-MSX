from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from datetime import date
from decimal import Decimal, InvalidOperation
import struct

HEADER_SIZE = 521
MAX_FIELDS = 32
VERSION = 0x02

@dataclass(slots=True)
class Field:
    name: str
    type: str
    length: int
    decimals: int = 0

    def __post_init__(self):
        self.name = self.name.upper()[:10]
        self.type = self.type.upper()
        if self.type not in {'C','N','L'}:
            raise ValueError(f'Unsupported dBASE II field type: {self.type}')
        if not (1 <= self.length <= 255):
            raise ValueError('field length must be 1..255')
        if self.type == 'L':
            self.length = 1
            self.decimals = 0
        if self.type != 'N':
            self.decimals = 0

class DBase2Table:
    """Read/write native dBASE II DBF files.

    dBASE II uses a fixed 521-byte header: 8-byte file header plus up to
    32 16-byte field descriptors and a terminator at byte 520.
    """
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.fields: list[Field] = []
        self.records: list[dict] = []
        self.deleted: list[bool] = []
        self.last_update = date.today()
        self._load()

    @classmethod
    def create(cls, path: str | Path, fields: list[Field], overwrite: bool = True):
        path = Path(path)
        if path.suffix == '':
            path = path.with_suffix('.DBF')
        if path.exists() and not overwrite:
            raise FileExistsError(path)
        if len(fields) > MAX_FIELDS:
            raise ValueError('dBASE II supports at most 32 fields')
        reclen = 1 + sum(f.length for f in fields)
        if reclen > 1000:
            raise ValueError('dBASE II record length cannot exceed 1000 bytes')
        obj = cls.__new__(cls)
        obj.path = path
        obj.fields = [Field(f.name, f.type, f.length, f.decimals) for f in fields]
        obj.records = []
        obj.deleted = []
        obj.last_update = date.today()
        obj.save()
        return obj

    @property
    def record_length(self) -> int:
        return 1 + sum(f.length for f in self.fields)

    @property
    def count(self) -> int:
        return len(self.records)

    def _load(self):
        raw = self.path.read_bytes()
        if len(raw) < HEADER_SIZE or raw[0] != VERSION:
            raise ValueError(f'Not a dBASE II database: {self.path}')
        nrec = struct.unpack_from('<H', raw, 1)[0]
        yy, mm, dd = raw[3], raw[4], raw[5]
        try:
            self.last_update = date(1900 + yy, mm or 1, dd or 1)
        except ValueError:
            self.last_update = date.today()
        reclen = struct.unpack_from('<H', raw, 6)[0]
        self.fields = []
        pos = 8
        for _ in range(MAX_FIELDS):
            d = raw[pos:pos+16]
            if not d or d[0] in (0, 0x0D):
                break
            name = d[:11].split(b'\0',1)[0].decode('cp437','replace').strip()
            typ = chr(d[11])
            length = d[12]
            decimals = d[15]
            self.fields.append(Field(name, typ, length, decimals))
            pos += 16
        expected = 1 + sum(f.length for f in self.fields)
        if reclen != expected:
            raise ValueError(f'Invalid record length: header={reclen}, fields={expected}')
        self.records, self.deleted = [], []
        pos = HEADER_SIZE
        for _ in range(nrec):
            chunk = raw[pos:pos+reclen]
            if len(chunk) < reclen:
                raise ValueError('Truncated DBF record area')
            self.deleted.append(chunk[0:1] == b'*')
            rec = {}
            cursor = 1
            for f in self.fields:
                cell = chunk[cursor:cursor+f.length]
                cursor += f.length
                rec[f.name] = self._decode(f, cell)
            self.records.append(rec)
            pos += reclen

    @staticmethod
    def _decode(f: Field, b: bytes):
        s = b.decode('cp437','replace')
        if f.type == 'C':
            return s.rstrip()
        if f.type == 'N':
            s = s.strip()
            if not s:
                return 0
            try:
                d = Decimal(s)
                return int(d) if f.decimals == 0 and d == d.to_integral_value() else float(d)
            except InvalidOperation:
                return 0
        if f.type == 'L':
            c = s[:1].upper()
            return c in {'Y','T','1'}
        return s

    @staticmethod
    def _encode(f: Field, v) -> bytes:
        if f.type == 'C':
            s = '' if v is None else str(v)
            return s.encode('cp437','replace')[:f.length].ljust(f.length,b' ')
        if f.type == 'N':
            if v in (None,''):
                s = ''
            elif f.decimals:
                s = f'{float(v):.{f.decimals}f}'
            else:
                s = str(int(float(v)))
            if len(s) > f.length:
                return b'*' * f.length
            return s.rjust(f.length).encode('ascii','replace')
        if f.type == 'L':
            return b'T' if bool(v) else b'F'
        raise ValueError(f.type)

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.last_update = date.today()
        hdr = bytearray(HEADER_SIZE)
        hdr[0] = VERSION
        struct.pack_into('<H', hdr, 1, len(self.records))
        hdr[3] = max(0, min(255, self.last_update.year - 1900))
        hdr[4] = self.last_update.month
        hdr[5] = self.last_update.day
        struct.pack_into('<H', hdr, 6, self.record_length)
        pos = 8
        for f in self.fields:
            name = f.name.encode('ascii','replace')[:10]
            hdr[pos:pos+11] = name.ljust(11,b'\0')
            hdr[pos+11] = ord(f.type)
            hdr[pos+12] = f.length
            hdr[pos+13:pos+15] = b'\0\0'
            hdr[pos+15] = f.decimals
            pos += 16
        hdr[520] = 0x0D if len(self.fields) == 32 else 0x00
        out = bytearray(hdr)
        for rec, deleted in zip(self.records, self.deleted):
            out += b'*' if deleted else b' '
            for f in self.fields:
                out += self._encode(f, rec.get(f.name))
        out += b'\x1a'
        self.path.write_bytes(out)

    def append(self, values: dict | None = None):
        values = {str(k).upper():v for k,v in (values or {}).items()}
        rec = {}
        for f in self.fields:
            rec[f.name] = values.get(f.name, '' if f.type == 'C' else False if f.type == 'L' else 0)
        self.records.append(rec)
        self.deleted.append(False)
        return len(self.records)

    def pack(self):
        kept = [(r,d) for r,d in zip(self.records,self.deleted) if not d]
        self.records = [r for r,_ in kept]
        self.deleted = [False] * len(kept)
        self.save()

    def zap(self):
        self.records.clear(); self.deleted.clear(); self.save()

    def structure(self):
        return [Field(f.name,f.type,f.length,f.decimals) for f in self.fields]
