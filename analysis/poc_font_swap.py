#!/usr/bin/env python3
"""PoC 1: recolour the glyph textures in place and prove the game loads font
files from its external data dir (files/huge/) rather than from the APK.

Magenta (RGB 255,0,255) with the original alpha preserved, so the glyph shapes
stay readable but every rendered character should turn magenta.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from export_groupbin import parse_container, resolve_geometry  # noqa: E402

ROOT = Path(r"D:\project\逆向\北方的扩张")
SRC = ROOT / "extracted" / "_res" / "assets" / "huge" / "respack"
OUT = ROOT / "build" / "poc_fonts" / "huge"


def patch_8888(d: bytearray, off: int, n: int) -> None:
    for i in range(n):
        o = off + i * 4
        d[o] = 255      # R
        d[o + 1] = 0    # G
        d[o + 2] = 255  # B
        # alpha untouched -> shapes preserved


def patch_5551(d: bytearray, off: int, n: int) -> None:
    for i in range(n):
        o = off + i * 2
        v = (d[o] << 8) | d[o + 1]          # big-endian, as in the decoder
        a = v & 1
        new = a | (31 << 1) | (0 << 6) | (31 << 11)
        d[o] = (new >> 8) & 0xFF
        d[o + 1] = new & 0xFF


def patch_4444(d: bytearray, off: int, n: int) -> None:
    for i in range(n):
        o = off + i * 2
        v = (d[o] << 8) | d[o + 1]
        a = v & 0xF
        new = a | (15 << 4) | (0 << 8) | (15 << 12)
        d[o] = (new >> 8) & 0xFF
        d[o + 1] = new & 0xFF


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    OUT.mkdir(parents=True, exist_ok=True)
    total = 0
    for bin_path in sorted(SRC.glob("fnt*.group.bin")):
        raw = bin_path.read_bytes()
        name, blocks = parse_container(raw)
        d = bytearray(raw)
        patched = 0
        for boff, bsize in blocks:
            geom = resolve_geometry(bytes(raw), boff, bsize)
            if geom is None:
                print(f"  {bin_path.name}: unresolved block, skipped")
                continue
            hdr, bpp, w, h = geom
            off = boff + hdr
            n = w * h
            code = raw[boff + 5]
            if code == 0x28:
                patch_8888(d, off, n)
            elif code == 0x07 or code == 0x00:
                patch_5551(d, off, n)
            elif code == 0x05:
                patch_4444(d, off, n)
            else:
                print(f"  {bin_path.name}: unknown code {code:#x}")
                continue
            patched += 1
            print(f"  {bin_path.name}: {name} block {w}x{h} bpp={bpp} code={code:#x} -> magenta")
        if patched:
            (OUT / bin_path.name).write_bytes(bytes(d))
            # keep the sibling .group / .dat untouched but copy them for convenience
            for sib in (".group", ".dat"):
                p = bin_path.with_name(bin_path.name.replace(".group.bin", sib))
                if p.exists():
                    (OUT / p.name).write_bytes(p.read_bytes())
            total += 1
    print(f"patched {total} font binaries -> {OUT}")


if __name__ == "__main__":
    main()
