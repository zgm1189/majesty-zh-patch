#!/usr/bin/env python3
"""Reader / writer for this game's Marmalade `.group.bin` font atlas + `.dat` glyph decks.

Container (verified by round-trip on every shipped font):
    ...prologue...            (everything up to the block header)
    u32  block_size           = 8 + 28 + w*h*4
    u32  0x0002B5D5           constant, NOT a checksum
    --- 28 byte image header ---
    +0   u16 0x430C
    +2   u16 0x0024           = 36 (block header 8 + image header 28)
    +4   u32 flags            (0 or 0x2800)
    +8   u32 0x45800000       (4096.0f, constant)
    +12  u32 0x45800000
    +16  u8  16               bpp
    +17  u16 width   (LE)
    +19  u16 height  (LE)
    +21  u8  0
    +22  u8  width // 64
    +23  5 bytes zero
    --- pixels ---            w*h*4 bytes, BGRA/RGBA (alpha in byte 3, white = ff ff ff)

Deck (`.dat`):
    u8   count
    u8   page                 codepoint page: glyph cp = (page << 8) | rec.ch
    records, 14 bytes each:
      +0  u16 ch (LE)
      +2  u8  bearing
      +3  u8  advance
      +4  u16 zero
      +6  u16 x (LE)
      +8  u16 y (LE)
      +10 u16 w (LE)
      +12 u8  h
      +13 u8  0 (0x01/0x10/0x20 appear on a few shipped records)
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from pathlib import Path

BLOCK_CONST = 0x0002B5D5
HEADER_SIZE = 28


def u32(d: bytes, o: int) -> int:
    return int.from_bytes(d[o:o + 4], "little")


def u16(d: bytes, o: int) -> int:
    return int.from_bytes(d[o:o + 2], "little")


def parse_container(d: bytes) -> tuple[str, list[tuple[int, int]]]:
    """Return (group name, [(body_offset, body_size)])."""
    nb = u32(d, 10)
    name = d[14:14 + max(0, nb - 9)].decode("ascii", "replace")
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


@dataclass
class Glyph:
    ch: int
    bearing: int
    advance: int
    pad: int
    x: int
    y: int
    w: int
    h: int
    flag: int = 0

    @property
    def box(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.w, self.h)

    def pack(self) -> bytes:
        return (struct.pack("<H", self.ch & 0xFFFF)
                + bytes((self.bearing & 0xFF, self.advance & 0xFF))
                + struct.pack("<HHHH", self.pad & 0xFFFF, self.x, self.y, self.w)
                + bytes((self.h & 0xFF, self.flag & 0xFF)))


class Atlas:
    """A font texture: prologue bytes, image header, RGBA pixels."""

    def __init__(self, path: Path):
        self.path = path
        raw = path.read_bytes()
        name, blocks = parse_container(raw)
        if len(blocks) != 1:
            raise ValueError(f"{path.name}: expected 1 block, got {len(blocks)}")
        self.name = name
        boff, bsize = blocks[0]
        self.boff = boff
        self.prologue = raw[:boff - 8]          # up to (excluding) block size field
        self.header = raw[boff:boff + HEADER_SIZE]
        self.w = u16(self.header, 17)
        self.h = u16(self.header, 19)
        self.pixels = bytearray(raw[boff + HEADER_SIZE:boff + bsize])
        self.trailer = raw[boff + bsize:]        # 4 zero bytes in every shipped atlas
        if len(self.pixels) != self.w * self.h * 4:
            raise ValueError(f"{path.name}: pixel payload {len(self.pixels)} "
                             f"!= {self.w}x{self.h}x4")

    # ---------------------------------------------------------------- pixels
    def resize(self, w: int, h: int) -> None:
        """Grow the atlas, keeping every existing glyph at its coordinates."""
        if w < self.w or h < self.h:
            raise ValueError("atlas can only grow")
        new = bytearray(w * h * 4)
        for y in range(self.h):
            src = y * self.w * 4
            dst = y * w * 4
            new[dst:dst + self.w * 4] = self.pixels[src:src + self.w * 4]
        self.pixels = new
        self.w, self.h = w, h

    def get(self, x: int, y: int) -> tuple[int, int, int, int]:
        o = (y * self.w + x) * 4
        return tuple(self.pixels[o:o + 4])  # type: ignore[return-value]

    def set_alpha(self, x: int, y: int, a: int) -> None:
        o = (y * self.w + x) * 4
        self.pixels[o:o + 4] = bytes((255, 255, 255, a))

    def clear_box(self, x: int, y: int, w: int, h: int) -> None:
        for gy in range(y, y + h):
            o = (gy * self.w + x) * 4
            self.pixels[o:o + w * 4] = b"\x00" * (w * 4)

    def max_used_y(self, boxes) -> int:
        return max((y + h for _x, y, _w, h in boxes), default=0)

    # ----------------------------------------------------------------- save
    def save(self, path: Path) -> None:
        # The prologue is the loader's directory entry and repeats two values
        # that must track the real texture size:
        #   +28  u16 block offset (unchanged)
        #   +30  u16 width // 64   <- the row stride the loader walks
        # Shipped M0 is 256x256 with 4 here, W0 is 512x256 with 8, so this is
        # definitely width//64.  resize() used to leave it at the old value,
        # which made the engine sample a 1024-wide atlas on a 256-wide stride.
        pro = bytearray(self.prologue)
        if len(pro) >= 32 and u16(pro, 28) == self.boff:
            pro[30:32] = struct.pack("<H", self.w // 64)
        elif (self.w, self.h) != (u16(self.header, 17), u16(self.header, 19)):
            raise ValueError(f"{path.name}: prologue layout not recognised, "
                             f"cannot sync width//64 after resize")

        hdr = bytearray(self.header)
        hdr[17:19] = struct.pack("<H", self.w)
        hdr[19:21] = struct.pack("<H", self.h)
        hdr[22] = self.w // 64
        size = HEADER_SIZE + len(self.pixels) + 8
        out = bytearray(pro)
        out += struct.pack("<II", size, BLOCK_CONST)
        out += bytes(hdr)
        out += self.pixels
        out += self.trailer
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(bytes(out))


def load_deck(path: Path) -> tuple[int, list[Glyph]]:
    """Return (page, glyphs). Bytes after the last whole record are kept in
    `Glyph`-list form via `deck_tail()`; use `read_deck` when rewriting."""
    return read_deck(path)[:2]


def read_deck(path: Path) -> tuple[int, list[Glyph], bytes]:
    d = path.read_bytes()
    count, page = d[0], d[1]
    n = (len(d) - 2) // 14
    out = []
    for i in range(n):
        o = 2 + i * 14
        r = d[o:o + 14]
        out.append(Glyph(ch=u16(r, 0), bearing=r[2], advance=r[3], pad=u16(r, 4),
                         x=u16(r, 6), y=u16(r, 8), w=u16(r, 10), h=r[12], flag=r[13]))
    return page, out, d[2 + n * 14:]


def save_deck(path: Path, page: int, glyphs: list[Glyph], tail: bytes = b"") -> None:
    # The shipped "0" decks carry a 5-byte partial record (the space glyph) after
    # the last whole record; the count byte includes it, so mirror that.
    count = len(glyphs) + (1 if tail else 0)
    if count > 255:
        raise ValueError("deck count must fit in one byte")
    buf = bytearray((count, page))
    for g in glyphs:
        buf += g.pack()
    buf += tail
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(buf))


def free_rows(atlas: Atlas, boxes) -> int:
    """First fully-free row after the last used one."""
    return max((y + h for _x, y, _w, h in boxes), default=0)


def next_pow2_at_least(n: int) -> int:
    p = 64
    while p < n:
        p *= 2
    return p


def atlas_size_for(need_px: int, min_w: int, min_h: int) -> tuple[int, int]:
    """Smallest w x h (multiples of 64, <=2048) that fits need_px more pixels."""
    for w, h in [(1024, 512), (1024, 1024), (2048, 1024), (2048, 2048)]:
        if w >= min_w and h >= min_h and (w * h) - (min_w * min_h) >= need_px:
            return w, h
    raise ValueError("atlas too small")
