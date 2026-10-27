#!/usr/bin/env python3
"""Build a minimal Chinese PoC translate.dat for the localisation test.

Patches a handful of main-menu strings in every language so the test is
independent of the device language, and keeps one English control string
(`kdCancel` -> `CancelOK`) so a blank/garbled result can be attributed to
glyph coverage rather than to the patch not taking effect.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(r"D:\project\逆向\北方的扩张")
SRC = ROOT / "extracted" / "assets" / "translate.dat"
OUT = ROOT / "build" / "assets" / "translate.dat"

POC = {
    # The opening story screen: definitely rendered from translate.dat.
    "sGameIntro": "陛下，这是中文化的第一次测试。汉字、标点，以及数字 123 与符号！如果这行字正常显示，说明游戏字体支持中文。",
    # Menu-button keys patched in the first pass (kept; they are icon-backed in
    # this build so they are not visible on the main menu).
    # Rendered on the profile screen after the update dialog is dismissed.
    # Control: Latin replacement - if THIS shows and the Chinese goes blank,
    # the patch works and the font simply has no CJK glyphs.
    "kdCreateProfile": "TEST中",
    "kdPlay": "开始游戏",
    "kdCampaign": "战役",
    "kdSkirmish": "遭遇战",
    "kdOptions": "选项",
    "kdExit": "退出",
    "kdMainMenu": "主菜单",
    "kdBack": "返回",
    "kCancel": "CancelOK",  # control: still Latin, proves the patch applied
}


def parse(data: bytes) -> list[str]:
    out: list[str] = []
    i = 0
    while i < len(data):
        ln = int.from_bytes(data[i : i + 2], "big")
        i += 2
        out.append(data[i : i + ln].decode("utf-8"))
        i += ln
    return out


def serialise(records: list[str]) -> bytes:
    parts = []
    for text in records:
        raw = text.encode("utf-8")
        if len(raw) > 0xFFFF:
            raise ValueError(f"record too long: {len(raw)}")
        parts.append(len(raw).to_bytes(2, "big"))
        parts.append(raw)
    return b"".join(parts)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    data = SRC.read_bytes()
    records = parse(data)
    print(f"parsed {len(records)} records from {len(data)} bytes")

    patched_records: list[str] = []
    hits: dict[str, int] = {}
    for rec in records:
        if ": " in rec:
            key, _ = rec.split(": ", 1)
            base = re.sub(r"_[a-z]{2}$", "", key)
            if base in POC:
                rec = f"{key}: {POC[base]}"
                hits[base] = hits.get(base, 0) + 1
        patched_records.append(rec)

    buf = serialise(patched_records)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(buf)

    print(f"patched strings: {hits}")
    print(f"wrote {OUT}  ({len(buf)} bytes, original {len(data)})")
    back = parse(buf)
    print(f"round-trip ok = {back == patched_records}  (records={len(back)})")
    for base, sample in list(POC.items())[:8]:
        found = [r for r in back if r.startswith(base + "_en:")]
        if found:
            print(f"  {found[0]}")


if __name__ == "__main__":
    main()
