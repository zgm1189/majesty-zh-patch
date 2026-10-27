#!/usr/bin/env python3
"""Probe field-order/endianness candidates for Marmalade 16-bit texture formats.

Prints an objective table (corner alpha = should be transparent for UI sprites,
alpha coverage, neighbour smoothness) and renders a contact sheet per case.
"""

from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

ASSETS = Path(r"D:\project\逆向\北方的扩张\extracted\_res\assets\huge\respack")
OUTDIR = Path(r"D:\project\逆向\北方的扩张\analysis\png")

FIELD_BITS = {
    "5551": {"r": 5, "g": 5, "b": 5, "a": 1},
    "4444": {"r": 4, "g": 4, "b": 4, "a": 4},
    "565": {"r": 5, "g": 6, "b": 5},
    "8888": {"r": 8, "g": 8, "b": 8, "a": 8},
}
ORDERS = {
    "5551": [("r", "g", "b", "a"), ("a", "r", "g", "b"), ("b", "g", "r", "a"), ("a", "b", "g", "r")],
    "4444": [("r", "g", "b", "a"), ("a", "r", "g", "b"), ("b", "g", "r", "a"), ("a", "b", "g", "r")],
    "8888": [("r", "g", "b", "a"), ("a", "b", "g", "r"), ("b", "g", "r", "a"), ("a", "r", "g", "b")],
}


def u32(d: bytes, o: int) -> int:
    return int.from_bytes(d[o : o + 4], "little")


def blocks_of(path: Path):
    d = path.read_bytes()
    nb = u32(d, 10)
    pos = 14 + nb + 4
    secs = u32(d, pos)
    pos += 4
    counts = []
    for _ in range(secs):
        pos += 4
        counts.append(u32(d, pos))
        pos += 6
    out = []
    for c in counts:
        for _ in range(c):
            size = u32(d, pos)
            out.append((pos + 8, size - 8))
            pos += size
    return d, out


def decode(raw: bytes, w: int, h: int, kind: str, order: tuple, endian: str) -> bytearray:
    bits = FIELD_BITS[kind]
    rgba = bytearray(w * h * 4)
    if kind == "8888":
        for i in range(w * h):
            vals = dict(zip(order, raw[i * 4 : i * 4 + 4]))
            for k, name in enumerate(("r", "g", "b", "a")):
                rgba[i * 4 + k] = vals.get(name, 0)
        return rgba
    for i in range(w * h):
        b0 = raw[i * 2]
        b1 = raw[i * 2 + 1]
        v = (b0 | (b1 << 8)) if endian == "le" else ((b0 << 8) | b1)
        pos = 0
        vals = {}
        for f in order:
            n = bits[f]
            vals[f] = (v >> pos) & ((1 << n) - 1)
            pos += n
        o = i * 4
        for k, name in enumerate(("r", "g", "b", "a")):
            n = bits.get(name)
            if n is None:
                rgba[o + k] = 255
            else:
                x = vals.get(name, 0)
                rgba[o + k] = x * 255 // ((1 << n) - 1)
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
    path.write_bytes(png)


def stats(rgba: bytearray, w: int, h: int) -> str:
    def a(x, y):
        return rgba[(y * w + x) * 4 + 3]

    corner = [a(x, y) for x in range(4) for y in range(4)]
    corner += [a(w - 1 - x, y) for x in range(4) for y in range(4)]
    corner += [a(x, h - 1 - y) for x in range(4) for y in range(4)]
    corner += [a(w - 1 - x, h - 1 - y) for x in range(4) for y in range(4)]
    corner_mean = sum(corner) / len(corner)
    transparent = sum(1 for i in range(w * h) if rgba[i * 4 + 3] == 0) / (w * h)
    smooth = 0
    for y in range(0, h, 4):
        for x in range(1, w, 4):
            o = (y * w + x) * 4
            smooth += abs(rgba[o] - rgba[o - 4]) + abs(rgba[o + 1] - rgba[o - 3]) + abs(rgba[o + 2] - rgba[o - 2])
    return f"cornerA={corner_mean:6.1f}  transp={transparent * 100:5.1f}%  rough={smooth / (w * h // 16):7.2f}"


def contact(label: str, rgba: bytearray, w: int, h: int, cols: int = 4) -> bytearray:
    gap = 4
    rows = (8 + cols - 1) // cols
    W = cols * w + (cols + 1) * gap
    H = rows * h + (rows + 1) * gap
    canvas = bytearray(W * H * 4)
    for i in range(W * H):
        canvas[i * 4 : i * 4 + 4] = bytes((25, 25, 25, 255))
    return canvas


def run(bin_name: str, block_idx: int, kind: str, cell: int) -> tuple[str, bytearray, int, int]:
    path = ASSETS / bin_name
    d, blocks = blocks_of(path)
    boff, bsize = blocks[block_idx]
    raw_all = d[boff + 28 : boff + bsize]
    bpp = 4 if kind == "8888" else 2
    count = len(raw_all) // bpp
    side = int(round(count**0.5))
    w_all = h_all = side
    print(f"\n### {bin_name} block{block_idx} ({kind})  {w_all}x{h_all}  {len(raw_all)} bytes")
    order_list = ORDERS[kind]
    endians = ("xx",) if kind == "8888" else ("le", "be")
    cells = []
    for endian in endians:
        for order in order_list:
            full = decode(raw_all, w_all, h_all, kind, order, endian)
            # crop to cell x cell (top-left)
            crop = bytearray(cell * cell * 4)
            for y in range(cell):
                src = (y * w_all) * 4
                crop[y * cell * 4 : (y + 1) * cell * 4] = full[src : src + cell * 4]
            tag = f"{endian}:{''.join(order)}"
            print(f"  {tag:12s} {stats(crop, cell, cell)}")
            cells.append((tag, crop))
    gap = 4
    cols = 4
    rows = 2
    W = cols * cell + (cols + 1) * gap
    H = rows * cell + (rows + 1) * gap
    canvas = bytearray(W * H * 4)
    for i in range(W * H):
        canvas[i * 4 : i * 4 + 4] = bytes((25, 25, 25, 255))
    for idx, (tag, crop) in enumerate(cells):
        cx = gap + (idx % cols) * (cell + gap)
        cy = gap + (idx // cols) * (cell + gap)
        for y in range(cell):
            src = y * cell * 4
            dst = ((cy + y) * W + cx) * 4
            canvas[dst : dst + cell * 4] = crop[src : src + cell * 4]
    out = OUTDIR / f"_probe_{bin_name.replace('.group.bin','')}_b{block_idx}_{kind}.png"
    write_png(out, W, H, canvas)
    print(f"  sheet -> {out}  (cells row0=le, row1=be; cols = field order low->high)")
    return tag, canvas, W, H


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    OUTDIR.mkdir(parents=True, exist_ok=True)
    run("anims0.group.bin", 2, "5551", 128)
    run("anims0.group.bin", 1, "4444", 128)
    run("anims0.group.bin", 0, "8888", 128)
