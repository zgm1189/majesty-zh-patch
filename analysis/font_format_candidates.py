#!/usr/bin/env python3
"""Brute-force the 16-bit pixel layout of a font atlas by rendering glyph 'A'
under every plausible interpretation and laying them out in one sheet."""

from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from export_groupbin import parse_container, resolve_geometry  # noqa: E402

ROOT = Path(r"D:\project\逆向\北方的扩张")
BIN = ROOT / "extracted" / "_res" / "assets" / "huge" / "respack" / "fntm0.group.bin"
OUT = ROOT / "build" / "poc_fonts" / "_fmt_candidates.png"

GW = GH = 10          # glyph 'A' rect
SCALE = 6
COLS = 4


def decode_variant(raw: bytes, w: int, h: int, kind: str, endian: str, swap: bool) -> bytearray:
    out = bytearray(w * h * 4)
    for i in range(w * h):
        b0 = raw[i * 2]
        b1 = raw[i * 2 + 1]
        v = (b0 | (b1 << 8)) if endian == "le" else ((b0 << 8) | b1)
        if kind == "5551":
            a = (v & 1) * 255
            r = ((v >> 1) & 0x1F) * 255 // 31
            g = ((v >> 6) & 0x1F) * 255 // 31
            b = ((v >> 11) & 0x1F) * 255 // 31
        elif kind == "4444":
            a = (v & 0xF) * 17
            r = ((v >> 4) & 0xF) * 17
            g = ((v >> 8) & 0xF) * 17
            b = ((v >> 12) & 0xF) * 17
        elif kind == "565":
            a = 255
            r = ((v >> 11) & 0x1F) * 255 // 31
            g = ((v >> 5) & 0x3F) * 255 // 63
            b = (v & 0x1F) * 255 // 31
        else:  # 1555 / argb
            a = ((v >> 15) & 1) * 255
            r = (v & 0x1F) * 255 // 31
            g = ((v >> 5) & 0x1F) * 255 // 31
            b = ((v >> 10) & 0x1F) * 255 // 31
        if swap:
            r, b = b, r
        o = i * 4
        out[o] = r
        out[o + 1] = g
        out[o + 2] = b
        out[o + 3] = a
    return out


def write_png(path: Path, w: int, h: int, rgba: bytearray) -> None:
    raw = b"".join(b"\x00" + bytes(rgba[y * w * 4 : (y + 1) * w * 4]) for y in range(h))

    def chunk(tag: bytes, payload: bytes) -> bytes:
        body = tag + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 6))
    png += chunk(b"IEND", b"")
    path.write_bytes(png)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raw = BIN.read_bytes()
    name, blocks = parse_container(raw)
    boff, bsize = blocks[0]
    hdr, bpp, aw, ah = resolve_geometry(raw, boff, bsize)
    pix = raw[boff + hdr : boff + bsize]
    print(f"{name}: {aw}x{ah} bpp={bpp} code={raw[boff+5]:#x}")

    # extract the glyph rect as raw 2-byte pixels
    rect = bytearray()
    for y in range(GH):
        for x in range(GW):
            o = (y * aw + x) * 2
            rect += pix[o : o + 2]

    variants = []
    for kind in ("5551", "4444", "565", "1555"):
        for endian in ("le", "be"):
            for swap in (False, True):
                label = f"{kind} {endian} {'BGR' if swap else 'RGB'}"
                variants.append((label, kind, endian, swap))

    cells = []
    for label, kind, endian, swap in variants:
        rgba = decode_variant(rect, GW, GH, kind, endian, swap)
        # composite over white
        for i in range(GW * GH):
            o = i * 4
            a = rgba[o + 3]
            for c in range(3):
                rgba[o + c] = (rgba[o + c] * a + 255 * (255 - a)) // 255
            rgba[o + 3] = 255
        cells.append((label, rgba))

    rows = (len(cells) + COLS - 1) // COLS
    cw, ch = GW * SCALE, GH * SCALE
    gap = 4
    W = COLS * cw + (COLS + 1) * gap
    H = rows * ch + (rows + 1) * gap
    canvas = bytearray(W * H * 4)
    for i in range(W * H):
        canvas[i * 4 : i * 4 + 4] = bytes((30, 30, 30, 255))
    for idx, (label, rgba) in enumerate(cells):
        cx = gap + (idx % COLS) * (cw + gap)
        cy = gap + (idx // COLS) * (ch + gap)
        for yy in range(ch):
            for xx in range(cw):
                s = ((yy // SCALE) * GW + (xx // SCALE)) * 4
                d = ((cy + yy) * W + cx + xx) * 4
                canvas[d : d + 4] = rgba[s : s + 4]
        print(f"  cell {idx:2d} {label}")
    write_png(OUT, W, H, canvas)
    print(f"wrote {OUT.name} ({W}x{H})")


if __name__ == "__main__":
    main()
