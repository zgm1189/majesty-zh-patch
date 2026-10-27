#!/usr/bin/env python3
"""Extract Marmalade `.group.bin` textures to PNG.

Container layout (verified against this title's files):

    magic            10 bytes
    name_block_size  uint32 ; name length + 9
    name             ascii
    fixed_suffix     9 bytes
    content_size     uint32
    section_count    uint32
    sections[]       section_magic u32, block_count u32, tag 2 bytes
    blocks[]         size u32 (incl. 8-byte header), checksum u32,
                     image_header (28 bytes here, 32 in some packs), pixels

Format is read from the image header byte at offset 5, which matches the
`useTemplate` declarations:

    0x28 -> 4 bytes/px, bytes R,G,B,A
    0x05 -> 2 bytes/px, big-endian u16, a=v&0xF r=v>>4 g=v>>8 b=v>>12   (4444)
    0x07 -> 2 bytes/px, big-endian u16, a=v&1  r=v>>1 g=v>>6 b=v>>11   (5551)
    0x00 -> 2 bytes/px, same decoder as 5551 (verified on fntW0's glyph atlas)

Dimensions: an exact square when the payload divides evenly, else the width and
height fields in the image header (offsets 16/18 for 16-bit, 18/20 for 32-bit),
else the power-of-two factor pair closest to square.

Bitfield order was established by rendering candidates and scoring corner
transparency plus neighbour smoothness (`analysis/decode_probe.py`).
"""

from __future__ import annotations

import math
import re
import struct
import sys
import zlib
from pathlib import Path

HEADER_LENGTHS = (28, 32, 24, 36, 20)
POW2 = (4096, 2048, 1024, 512, 256, 128, 64, 32, 16)
FORMAT_BPP = {0x28: 4, 0x05: 2, 0x07: 2, 0x00: 4}
# For an unknown code try both widths; 0x00 turns out to be 4 bytes/px here.
BPP_CANDIDATES = {0x28: (4,), 0x05: (2,), 0x07: (2,)}
DEEP_FORMATS = {"2dimage_4444", "2dimage_5551", "2dimage_565"}


def u32(d: bytes, o: int) -> int:
    return int.from_bytes(d[o : o + 4], "little")


def be16(d: bytes, o: int) -> int:
    return (d[o] << 8) | d[o + 1]


def parse_container(d: bytes) -> tuple[str, list[tuple[int, int]]]:
    """Return (group name, [(body_offset, body_size)])."""
    nb = u32(d, 10)
    name = d[14 : 14 + max(0, nb - 9)].decode("ascii", "replace")
    pos = 14 + nb + 4
    secs = u32(d, pos)
    pos += 4
    counts = []
    for _ in range(secs):
        pos += 4
        counts.append(u32(d, pos))
        pos += 6
    blocks = []
    for c in counts:
        for _ in range(c):
            size = u32(d, pos)
            blocks.append((pos + 8, size - 8))
            pos += size
    return name, blocks


def parse_group_text(path: Path) -> list[tuple[str, str]]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    current = "2dimage"
    out: list[tuple[str, str]] = []
    for line in text.splitlines():
        m = re.match(r'\s*useTemplate\s+"image"\s+"([^"]+)"', line)
        if m:
            current = m.group(1)
            continue
        m = re.match(r'\s*"([^"]+)"\s*\{', line)
        if m:
            out.append((m.group(1), current))
    return out


def decode_pixels(raw: bytes, deep: bool, fmt_name: str, w: int, h: int) -> bytearray:
    n = w * h
    rgba = bytearray(n * 4)
    if not deep:
        rgba[: n * 4] = raw[: n * 4]
        return rgba
    lerp5 = 255 / 31
    for i in range(n):
        v = (raw[i * 2] << 8) | raw[i * 2 + 1]
        if fmt_name == "2dimage_4444":
            a = (v & 0xF) * 17
            r = ((v >> 4) & 0xF) * 17
            g = ((v >> 8) & 0xF) * 17
            b = ((v >> 12) & 0xF) * 17
        elif fmt_name == "2dimage_565":
            a = 255
            r = int(((v >> 11) & 0x1F) * lerp5)
            g = int(((v >> 5) & 0x3F) * (255 / 63))
            b = int((v & 0x1F) * lerp5)
        else:  # 5551 and the 0x00 variant
            a = 255 if (v & 1) else 0
            r = int(((v >> 1) & 0x1F) * lerp5)
            g = int(((v >> 6) & 0x1F) * lerp5)
            b = int(((v >> 11) & 0x1F) * lerp5)
        o = i * 4
        rgba[o] = r
        rgba[o + 1] = g
        rgba[o + 2] = b
        rgba[o + 3] = a
    return rgba


def write_png(path: Path, w: int, h: int, rgba: bytearray) -> None:
    raw = b"".join(b"\x00" + bytes(rgba[y * w * 4 : (y + 1) * w * 4]) for y in range(h))

    def chunk(tag: bytes, payload: bytes) -> bytes:
        body = tag + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 6))
    png += chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


def resolve_geometry(d: bytes, boff: int, bsize: int) -> tuple[int, int, int, int] | None:
    """Return (header_len, bpp, w, h) or None."""
    code = d[boff + 5]
    for bpp in BPP_CANDIDATES.get(code, (4, 2)):
        for hdr in HEADER_LENGTHS:
            px = bsize - hdr
            if px <= 0 or px % bpp:
                continue
            count = px // bpp
            side = math.isqrt(count)
            if side * side == count:
                return hdr, bpp, side, side
        # Non-square atlases: pick the power-of-two pair closest to square.
        best = None
        for hdr in HEADER_LENGTHS:
            px = bsize - hdr
            if px <= 0 or px % bpp:
                continue
            count = px // bpp
            for w in POW2:
                if count % w:
                    continue
                h = count // w
                if h not in POW2:
                    continue
                ratio = max(w, h) / min(w, h)
                if best is None or ratio < best[0]:
                    best = (ratio, hdr, w, h)
        if best:
            return best[1], bpp, best[2], best[3]
        for hdr in HEADER_LENGTHS:
            px = bsize - hdr
            if px <= 0 or px % bpp:
                continue
            count = px // bpp
            w = be16(d, boff + (18 if bpp == 4 else 16))
            h = be16(d, boff + (20 if bpp == 4 else 18))
            if w and h and w * h == count:
                return hdr, bpp, w, h
        for hdr in HEADER_LENGTHS:
            px = bsize - hdr
            if px <= 0 or px % bpp:
                continue
            count = px // bpp
            cand = None
            p = 1
            while p * p <= count:
                if count % p == 0:
                    q = count // p
                    ratio = q / p
                    if cand is None or ratio < cand[0]:
                        cand = (ratio, q, p)
                p += 1
            if cand:
                return hdr, bpp, cand[1], cand[2]
    return None


def extract(bin_path: Path, out_root: Path, quiet: bool = False) -> tuple[int, int]:
    d = bin_path.read_bytes()
    name, blocks = parse_container(d)
    resources = parse_group_text(bin_path.with_name(bin_path.name.replace(".group.bin", ".group")))
    ok = bad = 0
    for i, (boff, bsize) in enumerate(blocks):
        declared = resources[i][1] if i < len(resources) else "2dimage"
        resname = resources[i][0] if i < len(resources) else f"block{i}"
        geom = resolve_geometry(d, boff, bsize)
        if geom is None:
            bad += 1
            if not quiet:
                print(f"  [{i}] {resname}: unresolved (body={bsize})")
            continue
        hdr, bpp, w, h = geom
        deep = bpp == 2
        fmt_name = declared if declared in DEEP_FORMATS else "2dimage_5551"
        rgba = decode_pixels(d[boff + hdr : boff + bsize], deep, fmt_name, w, h)
        flat = resname.replace("\\", "/").split("/")[-1]
        write_png(out_root / name / flat, w, h, rgba)
        ok += 1
        if not quiet:
            print(f"  [{i}] {resname:26s} {w}x{h} bpp={bpp}")
    return ok, bad


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    out_root = Path(sys.argv[1])
    src_dir = Path(sys.argv[2])
    total_ok = total_bad = 0
    files = sorted(src_dir.glob("*.group.bin"))
    for f in files:
        ok, bad = extract(f, out_root, quiet=True)
        total_ok += ok
        total_bad += bad
    print(f"{src_dir.name}: groups={len(files)} textures_ok={total_ok} failed={total_bad}")
