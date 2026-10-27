#!/usr/bin/env python3
"""Probe A: can translate.dat be hot-swapped through the game's data dir?

The game extracts respack.zr into
`/sdcard/Android/data/<pkg>/files/huge/` and loads fonts from there, but
translate.dat is not extracted -- the APK copy may be the only one it reads.

This script writes a probe translate.dat whose visible UI strings are mutated
with an unmistakable ASCII marker, so one screenshot tells us whether pushing
the file (no APK rebuild) takes effect.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(r"D:\project\逆向\北方的扩张")
SRC = ROOT / "extracted" / "assets" / "translate.dat"
OUT = ROOT / "build" / "probe_ta" / "translate.dat"

MARK = "ZZQ1"

# Any UI label reachable from the main menu; ASCII only so the original font
# renders it fine -- if these show up, translate.dat is being read.
def wanted(key: str) -> bool:
    return key == "lang_en" or (
        key.endswith("_en")
        and (key.startswith("kd") or key.startswith("kO")
             or key.startswith("ui") or key.startswith("msg"))
    )


def parse(d: bytes) -> list[str]:
    recs, i = [], 0
    while i + 2 <= len(d):
        n = int.from_bytes(d[i : i + 2], "big")
        i += 2
        recs.append(d[i : i + n].decode("utf-8"))
        i += n
    return recs


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    recs = parse(SRC.read_bytes())
    print(f"records in: {len(recs)}")

    hit = 0
    out_recs = []
    for r in recs:
        if ": " in r:
            key, value = r.split(": ", 1)
            if wanted(key):
                out_recs.append(f"{key}: {MARK}")
                hit += 1
                continue
        out_recs.append(r)

    buf = bytearray()
    for r in out_recs:
        raw = r.encode("utf-8")
        buf += len(raw).to_bytes(2, "big") + raw

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(bytes(buf))
    print(f"patched {hit} records -> {OUT} ({len(buf)} bytes)")


if __name__ == "__main__":
    main()
