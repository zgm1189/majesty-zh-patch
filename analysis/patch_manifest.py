#!/usr/bin/env python3
"""Patch AndroidManifest.xml in place: bump versionCode / versionName.

Both fields are edited without changing any structure or length:

  * versionName lives in the AXML string pool -> same-length swap, so every
    offset in the pool stays valid.
  * versionCode is an INT_DEC attribute -> its 4-byte payload is rewritten.

That keeps the file byte-length identical, which means no offset fixups are
needed anywhere (attribute tables, resource map, string offsets).

Usage:
    patch_manifest.py <in.xml> <out.xml> --code 10599 --name 1.5.99
"""

from __future__ import annotations

import sys
from pathlib import Path

TYPE_NAMES = {
    0x01: "REFERENCE",
    0x02: "ATTRIBUTE",
    0x03: "STRING",
    0x04: "FLOAT",
    0x05: "DIMENSION",
    0x10: "INT_DEC",
    0x11: "INT_HEX",
    0x12: "INT_BOOLEAN",
}


def u16(b, o):
    return int.from_bytes(b[o:o + 2], "little")


def u32(b, o):
    return int.from_bytes(b[o:o + 4], "little")


class StringPool:
    """Reads the AXML string pool and can rewrite a same-length entry."""

    def __init__(self, buf: bytearray, off: int):
        self.buf = buf
        self.off = off
        self.header_size = u16(buf, off + 2)
        self.count = u32(buf, off + 8)
        self.flags = u32(buf, off + 16)
        self.strings_start = u32(buf, off + 20)
        self.utf8 = bool(self.flags & 0x100)
        self.offsets = [u32(buf, off + self.header_size + i * 4) for i in range(self.count)]
        self.base = off + self.strings_start

    def payload(self, idx: int) -> tuple[int, int, str]:
        """Return (payload_file_off, payload_byte_len, encoding)."""
        p = self.base + self.offsets[idx]
        if self.utf8:
            p += 1
            if self.buf[p - 1] & 0x80:
                p += 1
            n = self.buf[p]
            p += 1
            if n & 0x80:
                n = ((n & 0x7F) << 8) | self.buf[p]
                p += 1
            return p, n, "utf-8"
        p += 2  # u16 char count
        n = u16(self.buf, p - 2)
        if n & 0x8000:
            n = ((n & 0x7FFF) << 16) | u16(self.buf, p)
            p += 2
        return p, n * 2, "utf-16-le"

    def get(self, idx: int) -> str:
        p, n, enc = self.payload(idx)
        return bytes(self.buf[p:p + n]).decode(enc, "replace")

    def replace(self, idx: int, new: str) -> bool:
        p, n, enc = self.payload(idx)
        raw = new.encode(enc)
        if len(raw) != n:
            raise ValueError(f"length mismatch for string #{idx}: {len(raw)} != {n}")
        self.buf[p:p + n] = raw
        return True


def iter_elements(buf, off: int, strings: StringPool):
    while off + 8 <= len(buf):
        typ = u16(buf, off)
        size = u32(buf, off + 4)
        if size <= 0:
            break
        if typ == 0x0102:  # RES_XML_START_ELEMENT
            name_idx = u32(buf, off + 20)
            attr_start = u16(buf, off + 24)
            attr_size = u16(buf, off + 26)
            attr_count = u16(buf, off + 28)
            yield off, name_idx, attr_start, attr_size, attr_count
        off += size


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = sys.argv[1:]
    if len(args) < 2:
        print(__doc__)
        raise SystemExit(2)
    src, dst = Path(args[0]), Path(args[1])
    code = name = None
    for i, a in enumerate(args):
        if a == "--code":
            code = int(args[i + 1])
        elif a == "--name":
            name = args[i + 1]

    buf = bytearray(src.read_bytes())
    orig_len = len(buf)
    strings = StringPool(buf, 8)
    print(f"string pool: {strings.count} entries, utf8={strings.utf8}")

    # Walk to <manifest> and resolve both attributes by name, so we never
    # guess which pool entry is the version string.
    manifest_off = None
    for off, name_idx, attr_start, attr_size, attr_count in iter_elements(buf, 8, strings):
        if strings.get(name_idx) == "manifest":
            manifest_off = (off, attr_start, attr_size, attr_count)
            break
    if manifest_off is None:
        raise SystemExit("<manifest> element not found")

    off, attr_start, attr_size, attr_count = manifest_off
    name_idx_attr = code_attr = None
    for k in range(attr_count):
        a = off + 16 + attr_start + k * attr_size
        aname = strings.get(u32(buf, a + 4))
        if aname == "versionCode":
            code_attr = a
        elif aname == "versionName":
            name_idx_attr = u32(buf, a + 16)

    # ---- versionName: same-length string swap -------------------------
    if name is not None:
        if name_idx_attr is None:
            raise SystemExit("versionName attribute not found")
        old = strings.get(name_idx_attr)
        if len(name) != len(old):
            raise SystemExit(f"versionName length must stay {len(old)} (got {len(name)})")
        strings.replace(name_idx_attr, name)
        print(f"versionName: {old!r} -> {name!r}  (string #{name_idx_attr}, in-place)")

    # ---- versionCode: INT_DEC payload ---------------------------------
    if code is not None:
        if code_attr is None or buf[code_attr + 15] != 0x10:
            raise SystemExit("versionCode INT_DEC attribute not found")
        old = u32(buf, code_attr + 16)
        buf[code_attr + 16:code_attr + 20] = code.to_bytes(4, "little")
        print(f"versionCode: {old} -> {code}  (payload @0x{code_attr + 16:x})")

    assert len(buf) == orig_len, "byte length changed -- aborting"
    dst.write_bytes(bytes(buf))
    print(f"wrote {dst} ({len(buf)} bytes, length unchanged)")


if __name__ == "__main__":
    main()
