#!/usr/bin/env python3
"""Probe localisation feasibility: text encoding in translate.dat and the
character-code space of the Marmalade bitmap fonts."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(r"D:\project\逆向\北方的扩张")
DAT = ROOT / "extracted" / "assets" / "translate.dat"
FNT_DIR = ROOT / "extracted" / "_res" / "assets" / "huge" / "respack"


def probe_text() -> None:
    d = DAT.read_bytes()
    print("=== translate.dat records (non-ASCII languages) ===")
    i = 0
    shown = 0
    langs = (b"_ru", b"_pl", b"_de", b"_fr", b"_es", b"_it", b"_pt")
    while i < len(d) - 2 and shown < 8:
        ln = int.from_bytes(d[i : i + 2], "big")
        i += 2
        rec = d[i : i + ln]
        i += ln
        if not rec:
            continue
        head = rec.split(b":")[0]
        if any(head.endswith(l) for l in langs):
            print(f"--- {head.decode('ascii', 'replace')}  len={ln}")
            print(f"    raw: {rec[:80].hex(' ')}")
            for enc in ("utf-8", "utf-16-le", "cp1251", "latin-1"):
                try:
                    print(f"    {enc:10s}: {rec[:56].decode(enc)!r}")
                except Exception as exc:
                    print(f"    {enc:10s}: <{type(exc).__name__}>")
            shown += 1


def probe_fonts() -> None:
    print()
    print("=== font descriptors: character codes ===")
    for path in sorted(FNT_DIR.glob("fnt*.dat")) + sorted(FNT_DIR.glob("fnt*.dti")):
        b = path.read_bytes()
        codes = []
        o = 2
        while o + 1 < len(b):
            v = b[o] | (b[o + 1] << 8)
            codes.append(v)
            o += 14
        printable = "".join(chr(c) if 32 <= c < 127 else "?" for c in codes)
        nonascii = [c for c in codes if c > 127]
        print(f"{path.name:24s} size={len(b):6d} entries={len(codes):3d} max=0x{max(codes):04x}")
        print(f"    chars : {printable[:70]}")
        print(f"    >0x7f : {[hex(c) for c in nonascii[:12]]}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    probe_text()
    probe_fonts()
