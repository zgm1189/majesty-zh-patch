#!/usr/bin/env python3
"""Decisive test: is the Cyrillic value in fntM2 record 0 the character that
selects that slot?  Set kOk_en to U+0442 and see if the OK button renders the
marker we painted at fntM2 rect[0]."""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(r"D:\project\逆向\北方的扩张\build\zh_ui\assets\translate.dat")
OUT = Path(r"D:\project\逆向\北方的扩张\build\assets\translate.dat")
TARGET = "kdTask_en"
NEW = "\u0442"  # 'т' — the value decoded from fntM2 record 0


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    d = SRC.read_bytes()
    recs, i = [], 0
    while i < len(d):
        n = int.from_bytes(d[i : i + 2], "big")
        i += 2
        recs.append(d[i : i + n].decode("utf-8"))
        i += n
    hit = 0
    out = []
    for r in recs:
        key, sep, _val = r.partition(": ")
        if key == TARGET and sep:
            print(f"  {r!r}  ->  {key}: {NEW!r}")
            r = f"{key}: {NEW}"
            hit += 1
        out.append(r)
    print(f"patched {hit} record(s)")

    buf = bytearray()
    for r in out:
        b = r.encode("utf-8")
        buf += len(b).to_bytes(2, "big") + b
    OUT.write_bytes(bytes(buf))
    print(f"wrote {OUT} ({len(buf)} bytes)")


if __name__ == "__main__":
    main()
