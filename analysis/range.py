#!/usr/bin/env python3
"""从 build/_dump/mem.dis 里按地址区间抽取反汇编。

用法: python range.py 0x110088 0x110300 [上下文行数]
地址即镜像偏移（== 运行时 vaddr - base）。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

DIS = Path(r"D:\project\逆向\北方的扩张\build\_dump\mem.dis")
LINE = re.compile(r"^\s*([0-9a-f]+):\s*\t")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    start = int(sys.argv[1], 16)
    end = int(sys.argv[2], 16)
    for raw in DIS.open("r", encoding="utf-8", errors="replace"):
        m = LINE.match(raw)
        if not m:
            continue
        a = int(m.group(1), 16)
        if start <= a < end:
            print(f"0x{a:06x}  {raw.split(chr(9), 1)[1].rstrip() if chr(9) in raw else raw.rstrip()}")


if __name__ == "__main__":
    main()
