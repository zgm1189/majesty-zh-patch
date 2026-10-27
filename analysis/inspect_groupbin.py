#!/usr/bin/env python3
"""Inspect Marmalade `.group.bin` container structure.

Layout (community reverse engineering, matches this game's files):

    magic            10 bytes
    name_block_size  uint32   ; name length + 9
    name             ascii    ; name_block_size - 9 bytes
    fixed_suffix     9 bytes  ; 00 00 00 00 00 77 21 3c dc
    content_size     uint32   ; bytes after the 33-byte header
    section_count    uint32
    sections[]       section_magic u32, block_count u32, tag 2 bytes
    blocks[]         size u32 (incl. header), checksum u32, content
"""

from __future__ import annotations

import sys
from pathlib import Path


def u32(d: bytes, o: int) -> int:
    return int.from_bytes(d[o : o + 4], "little")


def inspect(path: Path, verbose: bool = False) -> None:
    d = path.read_bytes()
    print(f"=== {path.name}  size={len(d)}")
    print(f"  magic      : {d[0:10].hex(' ')}")
    nb = u32(d, 10)
    name = d[14 : 14 + max(0, nb - 9)]
    print(f"  nameBlock  : {nb}  name={name!r}  suffix={d[14 + max(0, nb - 9):14 + nb].hex(' ')}")
    pos = 14 + nb
    content = u32(d, pos)
    pos += 4
    print(f"  contentSize: {content}  headerEnd={pos}  fileHeaderDelta={len(d) - content}")
    secs = u32(d, pos)
    pos += 4
    print(f"  sections   : {secs}")
    for i in range(secs):
        if pos + 10 > len(d):
            print("   (truncated section headers)")
            break
        smagic = u32(d, pos)
        nblocks = u32(d, pos + 4)
        tag = d[pos + 8 : pos + 10]
        pos += 10
        print(
            f"   section[{i}] magic=0x{smagic:08x} blocks={nblocks} tag={tag.hex(' ')}"
        )
    print(f"  blocks start @ {pos}")
    idx = 0
    while pos + 8 <= len(d):
        size = u32(d, pos)
        cksum = u32(d, pos + 4)
        if size < 8 or pos + size > len(d):
            print(f"   block[{idx}] @{pos} size={size} INVALID -> stop")
            break
        if verbose and (idx < 20 or idx % 25 == 0):
            body = d[pos + 8 : pos + 8 + 32]
            printable = "".join(chr(b) if 32 <= b < 127 else "." for b in body)
            print(
                f"   block[{idx}] @{pos} size={size} cksum=0x{cksum:08x} head={body.hex(' ')} |{printable}|"
            )
        pos += size
        idx += 1
    print(f"  total blocks={idx}  end={pos}/{len(d)}")


if __name__ == "__main__":
    args = sys.argv[1:]
    verbose = "--v" in args
    files = [a for a in args if a != "--v"]
    for f in files:
        inspect(Path(f), verbose)
