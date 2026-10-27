#!/usr/bin/env python3
"""从 mem.bin 抽取 ASCII 字符串（带偏移），可选按区间过滤/正则匹配。

用法:
  python strs.py                        # 全部，偏移 + 字符串
  python strs.py --re hero              # 正则过滤（不区分大小写）
  python strs.py --range 0x445000 0x450000
  python strs.py --min 4
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

MEM = Path(r"D:\project\逆向\北方的扩张\build\_dump\mem.bin")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--re", default=None)
    ap.add_argument("--range", nargs=2, default=None)
    ap.add_argument("--min", type=int, default=4)
    ap.add_argument("--maxlen", type=int, default=160)
    a = ap.parse_args()

    d = MEM.read_bytes()
    lo, hi = 0, len(d)
    if a.range:
        lo, hi = int(a.range[0], 16), int(a.range[1], 16)
    pat = re.compile(a.re, re.I) if a.re else None
    cur = bytearray()
    start = 0
    for i in range(lo, hi):
        b = d[i]
        if 0x20 <= b < 0x7F:
            if not cur:
                start = i
            cur.append(b)
        else:
            if len(cur) >= a.min:
                s = cur.decode("ascii")
                if pat is None or pat.search(s):
                    print(f"0x{start:06x}  {s[:a.maxlen]}")
            cur.clear()
    if len(cur) >= a.min:
        s = cur.decode("ascii")
        if pat is None or pat.search(s):
            print(f"0x{start:06x}  {s[:a.maxlen]}")


if __name__ == "__main__":
    main()
