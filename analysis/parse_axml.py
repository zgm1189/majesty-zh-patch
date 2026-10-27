#!/usr/bin/env python3
"""Minimal Android binary XML (AXML) reader, used to read AndroidManifest.xml."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(r"D:\project\逆向\北方的扩张")
MANIFEST = ROOT / "extracted" / "AndroidManifest.xml"

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


def u16(b: bytes, o: int) -> int:
    return int.from_bytes(b[o : o + 2], "little")


def u32(b: bytes, o: int) -> int:
    return int.from_bytes(b[o : o + 4], "little")


def read_string_pool(b: bytes, off: int):
    header_size = u16(b, off + 2)
    count = u32(b, off + 8)
    flags = u32(b, off + 16)
    strings_start = u32(b, off + 20)
    utf8 = bool(flags & 0x100)
    offsets = [u32(b, off + header_size + i * 4) for i in range(count)]
    base = off + strings_start
    out: list[str] = []
    for o in offsets:
        p = base + o
        if utf8:
            n = b[p]
            p += 1
            if n & 0x80:
                n = ((n & 0x7F) << 8) | b[p]
                p += 1
            n2 = b[p]
            p += 1
            if n2 & 0x80:
                n2 = ((n2 & 0x7F) << 8) | b[p]
                p += 1
            out.append(b[p : p + n2].decode("utf-8", "replace"))
        else:
            n = u16(b, p)
            p += 2
            if n & 0x8000:
                n = ((n & 0x7FFF) << 16) | u16(b, p)
                p += 2
            out.append(b[p : p + n * 2].decode("utf-16-le", "replace"))
    return out, off + u32(b, off + 4)


def walk(b: bytes, off: int, strings: list[str]):
    while off + 8 <= len(b):
        typ = u16(b, off)
        size = u32(b, off + 4)
        if size <= 0:
            break
        if typ == 0x0102:  # START_ELEMENT
            name = u32(b, off + 20)
            attr_start = u16(b, off + 24)
            attr_size = u16(b, off + 26)
            attr_count = u16(b, off + 28)
            attrs: dict[str, object] = {}
            for i in range(attr_count):
                a = off + 16 + attr_start + i * attr_size
                an = u32(b, a + 4)
                dtype = b[a + 15]
                data = u32(b, a + 16)
                aname = strings[an] if an < len(strings) else f"attr#{an}"
                if dtype == 0x03:
                    attrs[aname] = strings[data] if data < len(strings) else f"str#{data}"
                elif dtype in (0x10, 0x11, 0x12):
                    attrs[aname] = data if dtype != 0x12 else bool(data)
                else:
                    attrs[aname] = f"{TYPE_NAMES.get(dtype, hex(dtype))}:{data:#x}"
            yield strings[name] if name < len(strings) else f"el#{name}", attrs
        off += size


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    b = MANIFEST.read_bytes()
    strings, nxt = read_string_pool(b, 8)
    print(f"string pool: {len(strings)} strings")
    interesting = {"manifest", "uses-sdk", "application", "uses-permission", "activity"}
    for el, attrs in walk(b, nxt, strings):
        if el in interesting:
            keys = {k.split(":")[-1] if ":" in k else k: v for k, v in attrs.items()}
            print(f"<{el}>  {keys}")


if __name__ == "__main__":
    main()
