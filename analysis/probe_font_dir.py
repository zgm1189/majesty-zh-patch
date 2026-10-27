#!/usr/bin/env python3
"""Which resource directory does the game actually load fonts from?

The game unpacks three quality packs into
`/sdcard/Android/data/<pkg>/files/{huge,medium,huge_hi}/` with *different*
file names and atlas sizes (huge_hi uses 512x256 with capitalised names).
Previous probes only ever wrote into `huge/`.

This overwrites one already-visible letter per directory with a solid block,
so a single screenshot of the profile list ("PLAYER") reveals the live pack:

    huge/     -> 'P'   blanked
    medium/   -> 'L'   blanked
    huge_hi/  -> 'A'   blanked
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from export_groupbin import parse_container, resolve_geometry  # noqa: E402

ROOT = Path(r"D:\project\逆向\北方的扩张")
# original (never-pushed) fonts from the APK's unpacked resource packs
SRC = ROOT / "extracted" / "_res" / "assets"
OUT = ROOT / "build" / "font_probe"
TARGET = {"huge": 0x50, "medium": 0x4C, "huge_hi": 0x41}  # P / L / A


def records(dat: bytes) -> list[tuple[int, int, int, int, int, int, int]]:
    """(offset, char, x, y, w, h, metric) for each 14-byte record."""
    out = []
    n = (len(dat) - 2) // 14
    for i in range(n):
        o = 2 + i * 14
        r = dat[o : o + 14]
        ch = int.from_bytes(r[0:2], "little")
        out.append((o, ch, int.from_bytes(r[6:8], "little"),
                    int.from_bytes(r[8:10], "little"),
                    int.from_bytes(r[10:12], "little"),
                    int.from_bytes(r[12:14], "little"),
                    int.from_bytes(r[2:4], "little")))
    return out


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for pack, target in TARGET.items():
        src = SRC / pack / "respack"
        dst = OUT / pack
        dst.mkdir(parents=True, exist_ok=True)
        if not src.exists():
            print(f"{pack}: missing source {src}")
            continue
        dats = {p.name.lower(): p for p in src.glob("*.dat")}
        print(f"=== {pack}: blanking '{chr(target)}' (U+{target:04X})")
        for atlas_path in sorted(src.glob("fnt*.group.bin")):
            stem = atlas_path.name.lower().replace(".group.bin", "")
            dat_path = dats.get(stem + ".dat")
            if dat_path is None:
                continue
            dat = dat_path.read_bytes()
            hits = [r for r in records(dat) if r[1] == target]
            if not hits:
                continue
            raw = bytearray(atlas_path.read_bytes())
            grp, blocks = parse_container(bytes(raw))
            boff, bsize = blocks[0]
            hdr, bpp, aw, ah = resolve_geometry(bytes(raw), boff, bsize)
            for _o, ch, x, y, w, h, _m in hits:
                # mis-framed records in these decks can carry absurd widths;
                # ignore anything that cannot be a real glyph box.
                if not (1 <= w <= 64 and 1 <= h <= 64):
                    print(f"  {atlas_path.name}: skipped implausible box {w}x{h}")
                    continue
                if bpp != 4:
                    print(f"  {atlas_path.name}: bpp={bpp}, skipped")
                    continue
                pix = boff + hdr
                for gy in range(h):
                    for gx in range(w):
                        o = pix + ((y + gy) * aw + (x + gx)) * 4
                        if o + 4 <= len(raw):
                            raw[o : o + 4] = bytes((255, 255, 255, 255))
            assert len(raw) == atlas_path.stat().st_size
            (dst / atlas_path.name).write_bytes(bytes(raw))
            print(f"  {atlas_path.name} ({aw}x{ah}) <- {dat_path.name} "
                  f"{len(hits)} box(es): {[(h[2], h[3], h[4], h[5]) for h in hits]}")


if __name__ == "__main__":
    main()
