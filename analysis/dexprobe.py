#!/usr/bin/env python3
"""Minimal DEX reader: locate a string's id index, then find every code site
that references it via const-string / const-string/jumbo, and resolve those
sites back to their declaring class + method.

Used to pinpoint channel-SDK code paths without apktool.
"""
import struct
import sys
from pathlib import Path


def uleb128(buf, off):
    result = 0
    shift = 0
    while True:
        b = buf[off]
        off += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            return result, off
        shift += 7


def read_string(buf, off):
    n, off = uleb128(buf, off)
    end = buf.index(b"\x00", off)
    return buf[off:end].decode("utf-8", "replace"), n


class Dex:
    def __init__(self, path):
        self.buf = Path(path).read_bytes()
        b = self.buf
        (self.string_ids_size,) = struct.unpack_from("<I", b, 0x38)
        (self.string_ids_off,) = struct.unpack_from("<I", b, 0x3C)
        (self.type_ids_size,) = struct.unpack_from("<I", b, 0x40)
        (self.type_ids_off,) = struct.unpack_from("<I", b, 0x44)
        (self.proto_ids_size,) = struct.unpack_from("<I", b, 0x48)
        (self.proto_ids_off,) = struct.unpack_from("<I", b, 0x4C)
        (self.method_ids_size,) = struct.unpack_from("<I", b, 0x58)
        (self.method_ids_off,) = struct.unpack_from("<I", b, 0x5C)
        (self.class_defs_size,) = struct.unpack_from("<I", b, 0x60)
        (self.class_defs_off,) = struct.unpack_from("<I", b, 0x64)
        self._strings = None

    # ---- string table -------------------------------------------------
    def string_data_off(self, idx):
        return struct.unpack_from("<I", self.buf, self.string_ids_off + idx * 4)[0]

    def string(self, idx):
        if self._strings is None:
            self._strings = {}
        if idx not in self._strings:
            self._strings[idx] = read_string(self.buf, self.string_data_off(idx))[0]
        return self._strings[idx]

    def find_string_index(self, text):
        """Locate a string by matching its bytes, then resolving to an index."""
        raw = text.encode("utf-8")
        # string_data is uleb128(len) + bytes + NUL; scan for the payload
        hits = []
        start = 0
        while True:
            i = self.buf.find(raw, start)
            if i < 0:
                break
            hits.append(i)
            start = i + 1
        out = []
        # DEX prefixes each string with its UTF-16 code-unit count, not its
        # UTF-8 byte length, so compare against the decoded character count.
        nchars = len(raw.decode("utf-8", "replace"))
        for file_off in hits:
            data_off = None
            # back up over the uleb128 length prefix
            for back in range(1, 4):
                cand = file_off - back
                try:
                    ln, after = uleb128(self.buf, cand)
                except Exception:
                    continue
                if after == file_off and ln == nchars:
                    data_off = cand
                    break
            if data_off is None:
                continue
            if data_off not in self._off2idx():
                continue
            out.append(self._off2idx()[data_off])
        return out

    def _off2idx(self):
        if getattr(self, "_o2i", None) is None:
            self._o2i = {
                self.string_data_off(i): i for i in range(self.string_ids_size)
            }
        return self._o2i

    # ---- type / method names -----------------------------------------
    def type_name(self, idx):
        if idx == 0xFFFFFFFF:
            return "?"
        desc_idx = struct.unpack_from("<I", self.buf, self.type_ids_off + idx * 4)[0]
        return self.string(desc_idx)

    def method_name(self, idx):
        if idx == 0xFFFFFFFF:
            return "?"
        cls_idx, proto_idx, name_idx = struct.unpack_from(
            "<HHI", self.buf, self.method_ids_off + idx * 8
        )
        return self.type_name(cls_idx), self.string(name_idx)

    # ---- code scanning -----------------------------------------------
    def find_const_string_sites(self, str_idx):
        """Return file offsets of const-string instructions loading str_idx."""
        sites = []
        pat = struct.pack("<I", str_idx)
        # const-string (0x1a) uses a 16-bit index, jumbo (0x1b) a 32-bit one
        needle16 = struct.pack("<H", str_idx & 0xFFFF)
        i = 0
        n = len(self.buf)
        while True:
            i = self.buf.find(needle16, i)
            if i < 0:
                break
            # instruction is 4 bytes: op | vAA | string@
            op_off = i - 2
            if op_off >= 0 and self.buf[op_off] == 0x1A:
                sites.append(op_off)
            i += 1
        i = 0
        while True:
            i = self.buf.find(pat, i)
            if i < 0:
                break
            op_off = i - 2
            if op_off >= 0 and self.buf[op_off] == 0x1B:
                sites.append(op_off)
            i += 1
        return sorted(set(sites))

    def code_items(self):
        """Yield (code_off, insns_off, insns_size, class_desc, method_name)."""
        for c in range(self.class_defs_size):
            base = self.class_defs_off + c * 32
            class_idx = struct.unpack_from("<I", self.buf, base)[0]
            class_data_off = struct.unpack_from("<I", self.buf, base + 24)[0]
            class_desc = self.type_name(class_idx)
            if class_data_off == 0:
                continue
            off = class_data_off
            sf, off = uleb128(self.buf, off)
            inf, off = uleb128(self.buf, off)
            dm, off = uleb128(self.buf, off)
            vm, off = uleb128(self.buf, off)
            for _ in range(sf):
                _, off = uleb128(self.buf, off)
                _, off = uleb128(self.buf, off)
            for _ in range(inf):
                _, off = uleb128(self.buf, off)
                _, off = uleb128(self.buf, off)
            for count in (dm, vm):
                midx = 0
                for _ in range(count):
                    diff, off = uleb128(self.buf, off)
                    midx += diff
                    _, off = uleb128(self.buf, off)
                    code_off, off = uleb128(self.buf, off)
                    if code_off == 0:
                        continue
                    (insns_size,) = struct.unpack_from("<I", self.buf, code_off + 12)
                    insns_off = code_off + 16
                    yield insns_off, insns_size, class_desc, midx

    def resolve_site(self, site_off):
        for insns_off, insns_size, class_desc, midx in self.code_items():
            end = insns_off + insns_size * 2
            if insns_off <= site_off < end:
                try:
                    _, mname = self.method_name(midx)
                except Exception:
                    mname = "?"
                return class_desc, mname, (site_off - insns_off) // 2
        return None, None, None


def main():
    if len(sys.argv) < 3:
        print("usage: dexprobe.py <dex> <text> [<dex2> ...]")
        raise SystemExit(2)
    targets = sys.argv[1:]
    # first arg may be a dex, rest are strings
    for path in targets:
        if not path.lower().endswith(".dex"):
            continue
        d = Dex(path)
        print(f"### {path}: {d.string_ids_size} strings, {d.class_defs_size} classes")
        for text in targets:
            if text.lower().endswith(".dex"):
                continue
            idxs = d.find_string_index(text)
            print(f"  [{text!r}] -> string idx {idxs}")
            for si in idxs:
                sites = d.find_const_string_sites(si)
                print(f"     const-string sites: {len(sites)}")
                for s in sites[:20]:
                    cls, m, pc = d.resolve_site(s)
                    print(f"       @0x{s:x}  pc={pc}  {cls}->{m}")


if __name__ == "__main__":
    main()
