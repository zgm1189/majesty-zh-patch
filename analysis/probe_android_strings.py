#!/usr/bin/env python3
"""Inventory user-visible strings in the Android layer (dex + assets XML)."""

from __future__ import annotations

import re
import struct
import sys
from pathlib import Path

ROOT = Path(r"D:\project\逆向\北方的扩张")
EX = ROOT / "extracted"


def uleb128(b: bytes, o: int):
    result = 0
    shift = 0
    while True:
        byte = b[o]
        o += 1
        result |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            break
        shift += 7
    return result, o


def dex_strings(path: Path):
    b = path.read_bytes()
    size = int.from_bytes(b[56:60], "little")
    off = int.from_bytes(b[60:64], "little")
    out = []
    for i in range(size):
        s_off = int.from_bytes(b[off + i * 4 : off + i * 4 + 4], "little")
        if s_off >= len(b):
            continue
        try:
            _, o = uleb128(b, s_off)
            end = b.index(0, o)
        except Exception:
            continue
        out.append(b[o:end].decode("utf-8", "replace"))
    return out


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    total = 0
    for dex in sorted(EX.glob("classes*.dex")):
        strs = dex_strings(dex)
        total += len(strs)
        print(f"=== {dex.name}: {len(strs)} strings, {dex.stat().st_size} bytes")

    # collect all and classify
    all_strs: list[str] = []
    for dex in sorted(EX.glob("classes*.dex")):
        all_strs += dex_strings(dex)

    def wordy(s: str) -> bool:
        if len(s) < 12 or len(s) > 200:
            return False
        if not re.search(r"[A-Za-z]", s):
            return False
        if s.count(" ") < 2:
            return False
        bad = sum(1 for c in s if c in "/;<>()[$")
        return bad == 0

    wordy_strs = sorted({s for s in all_strs if wordy(s)})
    print(f"\n=== all dex strings: {len(all_strs)}, sentence-like: {len(wordy_strs)}")
    for s in wordy_strs[:40]:
        print(f"  {s[:110]}")

    print("\n=== assets/*.xml with visible text ===")
    for xml in sorted(EX.glob("assets/**/*.xml")):
        txt = xml.read_text(encoding="utf-8", errors="replace")
        # strip tags, look for human text
        stripped = re.sub(r"<[^>]+>", " ", txt)
        words = [w for w in stripped.split() if len(w) > 3 and re.search(r"[A-Za-z]", w)]
        if xml.name == "achievements_freemium.xml":
            continue
        print(f"  {xml.relative_to(EX)}: {len(words)} tokens  sample={words[:8]}")


if __name__ == "__main__":
    main()
