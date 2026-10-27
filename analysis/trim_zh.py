#!/usr/bin/env python3
"""Drop low-priority (purchase / social) entries so the Chinese text fits the
reduced slot budget after reserving digits and punctuation."""

from __future__ import annotations

import sys
from pathlib import Path

P = Path(r"D:\project\逆向\北方的扩张\analysis\build_zh_ui.py")
DROP = [
    "kdAchSincQ", "kdAwards", "kdLocalRecords", "kdMoreGames", "kdOnline",
    "kdScreenShot", "kdSendSMS", "kdSynchGame", "kdSynchGameQ", "kdTalks",
    "kdTellAFriend", "uiBuyCrystalsQ", "uiBuyCrystalsTitle", "uiBuyCrystalsTxt",
    "uiCheats", "uiGetCheatQ", "uiNotEnoughCrystals",
]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    lines = P.read_text(encoding="utf-8").splitlines(keepends=True)
    kept, dropped = [], []
    for ln in lines:
        hit = next((k for k in DROP if f'"{k}":' in ln), None)
        if hit:
            dropped.append(hit)
            continue
        kept.append(ln)
    P.write_text("".join(kept), encoding="utf-8")
    print(f"dropped {len(dropped)} entries: {dropped}")


if __name__ == "__main__":
    main()
