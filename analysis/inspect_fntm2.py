#!/usr/bin/env python3
"""Figure out what fntM2 really is: record framing, char codes, geometry."""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(r"D:\project\逆向\北方的扩张\extracted\_res\assets\huge\respack")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for name in ("fntm0.dat", "fntm1.dat", "fntm2.dat"):
        b = (SRC / name).read_bytes()
        print(f"=== {name}: {len(b)} bytes ===")
        print("  head:", b[:56].hex(" "))
        for rec in (12, 14, 16, 18, 20, 22):
            n, rem = divmod(len(b), rec)
            print(f"   rec={rec:2d}: {n:3d} records, remainder {rem}")
        print()

    b = (SRC / "fntm2.dat").read_bytes()
    print("=== fntm2.dat interpretation attempts ===")
    for rec in (12, 14, 16, 18, 20, 22):
        n = len(b) // rec
        print(f"-- rec={rec} ({n} records) --")
        for i in range(min(4, n)):
            chunk = b[i * rec : (i + 1) * rec]
            vals = [int.from_bytes(chunk[j : j + 2], "little") for j in range(0, len(chunk) - 1, 2)]
            print(f"   [{i}] {chunk.hex(' ')}  u16le={vals}")
        print()


if __name__ == "__main__":
    main()
