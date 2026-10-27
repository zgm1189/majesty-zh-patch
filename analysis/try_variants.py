#!/usr/bin/env python3
"""Render candidate decodings of one 5551 block into a single comparison sheet."""

from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

BIN = Path(
    r"D:\project\逆向\北方的扩张\extracted\_res\assets\huge\respack\anims0.group.bin"
)
OUT = Path(r"D:\project\逆向\北方的扩张\analysis\png\_variants_anims0_b2.png")


def u32(d: bytes, o: int) -> int:
    return int.from_bytes(d[o : o + 4], "little")


def payloads(d: bytes):
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
    return out


def scale5(x: int) -> int:
    return x * 255 // 31


def scale4(x: int) -> int:
    return x * 17


def var_r_low(v: int):
    return scale5(v & 0x1F), scale5((v >> 5) & 0x1F), scale5((v >> 10) & 0x1F), 255 if (v >> 15) & 1 else 0


def var_a_low(v: int):
    return scale5((v >> 1) & 0x1F), scale5((v >> 6) & 0x1F), scale5((v >> 11) & 0x1F), 255 if v & 1 else 0


def var_r_high(v: int):
    return scale5((v >> 11) & 0x1F), scale5((v >> 6) & 0x1F), scale5((v >> 1) & 0x1F), 255 if v & 1 else 0


def var_b_low(v: int):
    return scale5((v >> 10) & 0x1F), scale5((v >> 5) & 0x1F), scale5(v & 0x1F), 255 if (v >> 15) & 1 else 0


def var_565_low(v: int):
    return scale5(v & 0x1F), ((v >> 5) & 0x3F) * 255 // 63, scale5((v >> 11) & 0x1F), 255


VARIANTS = {
    "1 r_low (LE, r=lsb)": (var_r_low, "le"),
    "2 a_low (LE, a=lsb)": (var_a_low, "le"),
    "3 r_high (LE, r=msb)": (var_r_high, "le"),
    "4 b_low (LE, b=lsb)": (var_b_low, "le"),
    "5 r_low (BE bytes)": (var_r_low, "be"),
    "6 a_low (BE bytes)": (var_a_low, "be"),
    "7 565 low (LE)": (var_565_low, "le"),
    "8 565 high (LE)": (var_565_low, "be"),
}

CELL = 128
GAP = 6
COLS = 4


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


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    d = BIN.read_bytes()
    blocks = payloads(d)
    boff, bsize = blocks[2]
    raw = d[boff + 28 : boff + bsize]
    count = len(raw) // 2
    side = int(round(count**0.5))
    print(f"block2 pixels={len(raw)} bytes -> {count} px -> {side}x{side}")
    w = h = side

    rows = (len(VARIANTS) + COLS - 1) // COLS
    W = COLS * CELL + (COLS + 1) * GAP
    H = rows * CELL + (rows + 1) * GAP
    canvas = bytearray(W * H * 4)
    for i in range(W * H):
        canvas[i * 4 : i * 4 + 4] = bytes((30, 30, 30, 255))

    for idx, (label, (fn, endian)) in enumerate(VARIANTS.items()):
        cx = GAP + (idx % COLS) * (CELL + GAP)
        cy = GAP + (idx // COLS) * (CELL + GAP)
        for y in range(h):
            for x in range(w):
                i = y * w + x
                a = raw[i * 2]
                b = raw[i * 2 + 1]
                v = a | (b << 8) if endian == "le" else (a << 8) | b
                r, g, bl, al = fn(v)
                o = ((cy + y) * W + cx + x) * 4
                canvas[o] = r
                canvas[o + 1] = g
                canvas[o + 2] = bl
                canvas[o + 3] = al
        print(f"  cell {idx}: {label}")

    write_png(OUT, W, H, canvas)
    print(f"wrote {OUT}  ({W}x{H})")


if __name__ == "__main__":
    main()
