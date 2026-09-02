"""FAT12 .DSK image reader/writer for MSX-DOS floppy images.

Mounts a real MSX .DSK file (360K/720K FAT12, MSX-DOS 1 layout) so a
BDOS emulation can open/read/write/create files against it exactly like
MSX-DOS did on real hardware -- this is the actual historic filesystem,
not a re-derived one.

Safety: the on-disk .DSK file is loaded into an in-memory bytearray copy.
Nothing is written back to the original file unless `save_as()` is called
explicitly, so mounting COBOL.DSK/DBASE.DSK/VIDEOLOC.DSK for execution
never mutates the preserved original images.
"""
from __future__ import annotations

import struct
from pathlib import Path
from typing import Optional

DIR_ENTRY_SIZE = 32
FAT12_EOF = 0xFFF
FAT12_FREE = 0x000
FAT12_BAD = 0xFF7


class DskError(Exception):
    pass


class DskImage:
    def __init__(self, data: bytes):
        self.data = bytearray(data)
        self._parse_boot()

    @classmethod
    def load(cls, path: str) -> "DskImage":
        return cls(Path(path).read_bytes())

    @classmethod
    def blank(cls, kb: int = 720) -> "DskImage":
        """Create a fresh formatted 360K/720K MSX-DOS FAT12 image."""
        if kb == 720:
            spc, spf, root_entries, total_sectors, spt, heads = 2, 3, 112, 1440, 9, 2
        elif kb == 360:
            spc, spf, root_entries, total_sectors, spt, heads = 2, 2, 112, 720, 9, 2
        else:
            raise DskError("kb must be 360 or 720")
        data = bytearray(total_sectors * 512)
        boot = bytearray(512)
        boot[0:2] = b"\xeb\xfe"
        struct.pack_into("<H", boot, 0x0b, 512)
        boot[0x0d] = spc
        struct.pack_into("<H", boot, 0x0e, 1)
        boot[0x10] = 2
        struct.pack_into("<H", boot, 0x11, root_entries)
        struct.pack_into("<H", boot, 0x13, total_sectors)
        boot[0x15] = 0xF9 if kb == 720 else 0xF8
        struct.pack_into("<H", boot, 0x16, spf)
        struct.pack_into("<H", boot, 0x18, spt)
        struct.pack_into("<H", boot, 0x1a, heads)
        data[0:512] = boot
        fat_start = 512
        data[fat_start] = boot[0x15]
        data[fat_start + 1] = 0xFF
        data[fat_start + 2] = 0xFF
        img = cls(bytes(data))
        return img

    def _parse_boot(self) -> None:
        d = self.data
        self.bps = struct.unpack_from("<H", d, 0x0b)[0] or 512
        self.spc = d[0x0d] or 2
        self.reserved = struct.unpack_from("<H", d, 0x0e)[0] or 1
        self.nfats = d[0x10] or 2
        self.root_entries = struct.unpack_from("<H", d, 0x11)[0] or 112
        self.total_sectors = struct.unpack_from("<H", d, 0x13)[0]
        self.media = d[0x15]
        self.spf = struct.unpack_from("<H", d, 0x16)[0] or 3
        self.spt = struct.unpack_from("<H", d, 0x18)[0] or 9
        self.heads = struct.unpack_from("<H", d, 0x1a)[0] or 2

        self.fat_start = self.reserved * self.bps
        self.fat_size = self.spf * self.bps
        self.root_start = self.fat_start + self.nfats * self.fat_size
        self.root_size = self.root_entries * DIR_ENTRY_SIZE
        self.data_start = self.root_start + self.root_size
        self.cluster_size = self.spc * self.bps
        self.max_clusters = (len(self.data) - self.data_start) // self.cluster_size + 2

    # ---- FAT12 chain helpers -------------------------------------------
    def _fat_get(self, cl: int, fat_idx: int = 0) -> int:
        base = self.fat_start + fat_idx * self.fat_size
        off = base + cl + cl // 2
        if cl % 2 == 0:
            return self.data[off] | ((self.data[off + 1] & 0x0F) << 8)
        return (self.data[off] >> 4) | (self.data[off + 1] << 4)

    def _fat_set(self, cl: int, value: int) -> None:
        for fat_idx in range(self.nfats):
            base = self.fat_start + fat_idx * self.fat_size
            off = base + cl + cl // 2
            if cl % 2 == 0:
                lo = value & 0xFF
                hi_existing = self.data[off + 1] & 0xF0
                self.data[off] = lo
                self.data[off + 1] = hi_existing | ((value >> 8) & 0x0F)
            else:
                lo_existing = self.data[off] & 0x0F
                self.data[off] = lo_existing | ((value & 0x0F) << 4)
                self.data[off + 1] = (value >> 4) & 0xFF

    def _chain(self, start: int) -> list[int]:
        chain = []
        cl = start
        seen = set()
        while 2 <= cl < FAT12_BAD and cl not in seen:
            seen.add(cl)
            chain.append(cl)
            cl = self._fat_get(cl)
        return chain

    def _alloc_cluster(self) -> int:
        for cl in range(2, self.max_clusters):
            if self._fat_get(cl) == FAT12_FREE:
                self._fat_set(cl, FAT12_EOF)
                return cl
        raise DskError("disk full")

    def _cluster_offset(self, cl: int) -> int:
        return self.data_start + (cl - 2) * self.cluster_size

    # ---- directory --------------------------------------------------
    @staticmethod
    def _fmt_name(name83: bytes, ext: bytes) -> str:
        n = name83.decode("ascii", "replace").rstrip()
        e = ext.decode("ascii", "replace").rstrip()
        return f"{n}.{e}" if e else n

    @staticmethod
    def _to_83(name: str) -> tuple[bytes, bytes]:
        name = name.upper()
        if "." in name:
            base, ext = name.split(".", 1)
        else:
            base, ext = name, ""
        base = (base[:8]).ljust(8)
        ext = (ext[:3]).ljust(3)
        return base.encode("ascii", "replace"), ext.encode("ascii", "replace")

    def list_dir(self) -> list[dict]:
        out = []
        for off in range(self.root_start, self.root_start + self.root_size, DIR_ENTRY_SIZE):
            b = self.data[off]
            if b == 0x00:
                break
            if b == 0xE5:
                continue
            attr = self.data[off + 11]
            if attr & 0x08:
                continue
            e = bytes(self.data[off:off + DIR_ENTRY_SIZE])
            out.append(self._entry_info(off, e))
        return out

    def _entry_info(self, off: int, e: bytes) -> dict:
        name = self._fmt_name(e[0:8], e[8:11])
        start_cl = struct.unpack_from("<H", e, 26)[0]
        size = struct.unpack_from("<I", e, 28)[0]
        return dict(offset=off, name=name, attr=e[11], start_cl=start_cl, size=size)

    def _find_entry_offset(self, name: str) -> Optional[int]:
        base, ext = self._to_83(name)
        for off in range(self.root_start, self.root_start + self.root_size, DIR_ENTRY_SIZE):
            b = self.data[off]
            if b == 0x00:
                break
            if b == 0xE5:
                continue
            if bytes(self.data[off:off + 8]) == base and bytes(self.data[off + 8:off + 11]) == ext:
                return off
        return None

    def _find_free_dir_slot(self) -> int:
        for off in range(self.root_start, self.root_start + self.root_size, DIR_ENTRY_SIZE):
            b = self.data[off]
            if b == 0x00 or b == 0xE5:
                return off
        raise DskError("root directory full")

    # ---- file-level API (used by BDOS) -----------------------------------
    def exists(self, name: str) -> bool:
        return self._find_entry_offset(name) is not None

    def read_file(self, name: str) -> bytes:
        off = self._find_entry_offset(name)
        if off is None:
            raise FileNotFoundError(name)
        e = bytes(self.data[off:off + DIR_ENTRY_SIZE])
        info = self._entry_info(off, e)
        buf = bytearray()
        for cl in self._chain(info["start_cl"]):
            co = self._cluster_offset(cl)
            buf += self.data[co:co + self.cluster_size]
        return bytes(buf[:info["size"]])

    def file_size(self, name: str) -> int:
        off = self._find_entry_offset(name)
        if off is None:
            raise FileNotFoundError(name)
        return struct.unpack_from("<I", self.data, off + 28)[0]

    def create_file(self, name: str) -> None:
        off = self._find_entry_offset(name)
        if off is None:
            off = self._find_free_dir_slot()
        base, ext = self._to_83(name)
        entry = bytearray(DIR_ENTRY_SIZE)
        entry[0:8] = base
        entry[8:11] = ext
        entry[11] = 0x20  # archive
        struct.pack_into("<H", entry, 26, 0)
        struct.pack_into("<I", entry, 28, 0)
        self.data[off:off + DIR_ENTRY_SIZE] = entry
        # free any previously-assigned clusters if overwriting
        old = self._entry_info(off, bytes(entry))

    def delete_file(self, name: str) -> bool:
        off = self._find_entry_offset(name)
        if off is None:
            return False
        e = bytes(self.data[off:off + DIR_ENTRY_SIZE])
        info = self._entry_info(off, e)
        for cl in self._chain(info["start_cl"]):
            self._fat_set(cl, FAT12_FREE)
        self.data[off] = 0xE5
        return True

    def write_file(self, name: str, content: bytes) -> None:
        """Full sequential (re)write of a file's contents."""
        off = self._find_entry_offset(name)
        if off is None:
            self.create_file(name)
            off = self._find_entry_offset(name)
        e = bytes(self.data[off:off + DIR_ENTRY_SIZE])
        info = self._entry_info(off, e)
        for cl in self._chain(info["start_cl"]):
            self._fat_set(cl, FAT12_FREE)

        chain: list[int] = []
        needed_clusters = max(1, (len(content) + self.cluster_size - 1) // self.cluster_size) if content else 0
        for _ in range(needed_clusters):
            chain.append(self._alloc_cluster())
        for i, cl in enumerate(chain):
            if i + 1 < len(chain):
                self._fat_set(cl, chain[i + 1])
            else:
                self._fat_set(cl, FAT12_EOF)
            co = self._cluster_offset(cl)
            chunk = content[i * self.cluster_size:(i + 1) * self.cluster_size]
            self.data[co:co + len(chunk)] = chunk
            if len(chunk) < self.cluster_size:
                self.data[co + len(chunk):co + self.cluster_size] = b"\x00" * (self.cluster_size - len(chunk))

        start_cl = chain[0] if chain else 0
        struct.pack_into("<H", self.data, off + 26, start_cl)
        struct.pack_into("<I", self.data, off + 28, len(content))

    def write_at(self, name: str, offset: int, chunk: bytes) -> None:
        """Random-access write used for BDOS random write; grows the file
        and zero-pads any gap, like real FAT does."""
        try:
            cur = bytearray(self.read_file(name))
        except FileNotFoundError:
            self.create_file(name)
            cur = bytearray()
        if len(cur) < offset:
            cur += b"\x00" * (offset - len(cur))
        end = offset + len(chunk)
        if len(cur) < end:
            cur += b"\x00" * (end - len(cur))
        cur[offset:end] = chunk
        self.write_file(name, bytes(cur))

    def save_as(self, path: str) -> None:
        Path(path).write_bytes(bytes(self.data))
