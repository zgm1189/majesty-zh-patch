#!/usr/bin/env python3
"""端到端自检：直接从打好的 APK 里取出字体与语言表，按游戏的方式渲染预览。

用法: python verify_apk.py [pack]
"""

from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

ROOT = Path(r"D:\project\逆向\北方的扩张")
APK = ROOT / "build" / "majesty_zh_cn.apk"
OUT = ROOT / "build" / "_verify"


def extract(pack: str = "huge") -> Path:
    dst = OUT / pack
    dst.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(APK) as apk:
        raw = apk.read(f"assets/{pack}/respack.zr")
    n = 0
    with zipfile.ZipFile(io.BytesIO(raw)) as res:
        for item in res.infolist():
            name = item.filename.rsplit("/", 1)[-1]
            low = name.lower()
            if low.startswith("fnt") and low.endswith((".dat", ".dti", ".group.bin")):
                (dst / name).write_bytes(res.read(item.filename))
                n += 1
    print(f"{pack}: 从 APK 取出 {n} 个字体文件 -> {dst}")
    return dst


def translate_check() -> None:
    with zipfile.ZipFile(APK) as apk:
        d = apk.read("assets/translate.dat")
    recs, i = {}, 0
    while i + 2 <= len(d):
        ln = int.from_bytes(d[i:i + 2], "big")
        i += 2
        if i + ln > len(d):
            break
        s = d[i:i + ln].decode("utf-8", "replace")
        i += ln
        k, sep, v = s.partition(": ")
        if sep:
            recs[k] = v
    print(f"translate.dat: {len(recs)} 条")
    for k in ("lang_en", "kdSaveQ_en", "kdStart_en", "sTaskL14_en", "acName0_en"):
        if k in recs:
            print(f"  {k} = {recs[k]}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    pack = sys.argv[1] if len(sys.argv) > 1 else "huge"
    translate_check()
    extract(pack)
    sys.path.insert(0, str(Path(__file__).parent))
    import preview_font
    preview_font.Font = _rebase(preview_font.Font, OUT / pack)
    preview_font.render(pack)


def _rebase(cls, base: Path):
    """让预览器改读 APK 里取出的字体目录。"""
    orig = cls.__init__

    def init(self, pack_dir, fam):
        orig(self, base, fam)

    cls.__init__ = init
    return cls


if __name__ == "__main__":
    main()
