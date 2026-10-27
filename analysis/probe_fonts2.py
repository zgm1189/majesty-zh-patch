#!/usr/bin/env python3
"""Scan every Marmalade font descriptor for its character-code space.

Answers the localisation question: does the engine's bitmap font address
characters beyond Latin-1 (i.e. is Cyrillic present, which would prove a
Unicode-sized code space that Chinese could also occupy)?
"""

from __future__ import annotations

import sys
from pathlib import Path

FNT_DIR = Path(r"D:\project\逆向\北方的扩张\extracted\_res\assets\huge\respack")


def best_sequence(b: bytes):
    """Try to recover the ascending character-code table for several record strides."""
    candidates = []
    for step in range(8, 40):
        for start in range(0, 6):
            codes = []
            o = start
            while o + 1 < len(b):
                codes.append(b[o] | (b[o + 1] << 8))
                o += step
            if len(codes) < 8:
                continue
            printable = sum(1 for c in codes if 0x20 <= c < 0x7F)
            unique = len(set(codes))
            score = printable / len(codes) + (unique / len(codes)) * 0.2
            candidates.append((score, step, start, codes))
    candidates.sort(reverse=True)
    return candidates[0] if candidates else None


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    files = sorted(
        p for p in FNT_DIR.glob("fnt*") if p.suffix in (".dat", ".dti")
    )
    for p in files:
        b = p.read_bytes()
        res = best_sequence(b)
        if not res:
            print(f"{p.name:24s} size={len(b):6d}  (no sequence found)")
            continue
        score, step, start, codes = res
        # keep the plausible prefix
        good = [c for c in codes if 0x20 <= c < 0x3000]
        lo, hi = min(good), max(good)
        beyond_latin1 = sorted({c for c in codes if c > 0xFF and c < 0x3000})
        cyr = [c for c in beyond_latin1 if 0x400 <= c <= 0x4FF]
        print(
            f"{p.name:24s} size={len(b):6d} stride={step:2d} start={start} n={len(codes):3d} "
            f"range=0x{lo:04x}-0x{hi:04x}"
        )
        printable = "".join(chr(c) if 32 <= c < 127 else "." for c in codes[:64])
        print(f"    ascii : {printable}")
        if beyond_latin1:
            print(f"    >0xFF : {[hex(c) for c in beyond_latin1[:16]]}")
        if cyr:
            print(f"    CYRILLIC HITS: {len(cyr)}  {[hex(c) for c in cyr[:16]]}")


if __name__ == "__main__":
    main()
