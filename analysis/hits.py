#!/usr/bin/env python3
"""解析 zhout.txt 的 HIT 块，按「结构特征」给候选打分。

用法: python hits.py [要匹配的整数值...]
默认匹配 1209,1250,16,21,2,113
"""
from __future__ import annotations

import re
import struct
import sys
from pathlib import Path

OUT = Path(r"D:\project\逆向\北方的扩张\build\zhout.txt")
HEX = re.compile(r"^(0x[0-9a-f]+) ([0-9a-f]{32})")
HIT = re.compile(r"^HIT (0x[0-9a-f]+)")


def blocks():
    cur = None
    mem = {}
    for line in OUT.open(encoding="utf-8", errors="replace"):
        line = line.rstrip("\n")
        m = HIT.match(line)
        if m:
            if cur:
                yield cur, mem
            cur, mem = m.group(1), {}
            continue
        m = HEX.match(line)
        if m and cur:
            a = int(m.group(1), 16)
            raw = bytes.fromhex(m.group(2))
            mem[a] = raw
    if cur:
        yield cur, mem


def flat(mem):
    if not mem:
        return None, b""
    lo = min(mem)
    hi = max(mem) + 16
    buf = bytearray(hi - lo)
    for a, raw in mem.items():
        buf[a - lo:a - lo + len(raw)] = raw
    return lo, bytes(buf)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    want = [int(x) for x in sys.argv[1:]] or [1209, 1250, 16, 21, 2, 113]
    rows = []
    for addr, mem in blocks():
        lo, buf = flat(mem)
        if not buf:
            continue
        hits = {}
        for w in want:
            pos = []
            for i in range(0, len(buf) - 3, 4):
                if struct.unpack_from("<i", buf, i)[0] == w:
                    pos.append(lo + i)
            hits[w] = pos
        score = sum(1 for w in want if hits[w])
        rows.append((score, addr, lo, buf, hits))
    rows.sort(reverse=True, key=lambda r: r[0])
    for score, addr, lo, buf, hits in rows[:8]:
        print(f"\n===== HIT {addr} score {score}/{len(want)} base {hex(lo)} =====")
        for w in want:
            ps = hits[w]
            if ps:
                print(f"  {w}: " + ", ".join(hex(p) for p in ps[:6]) + (f" (+{len(ps)-6})" if len(ps) > 6 else ""))
        for i in range(0, len(buf), 16):
            chunk = buf[i:i + 16]
            hexs = " ".join(f"{b:02x}" for b in chunk).ljust(47)
            asc = "".join(chr(b) if 0x20 <= b < 0x7f else "." for b in chunk)
            print(f"  {lo+i:#x}  {hexs}  {asc}")


if __name__ == "__main__":
    main()
