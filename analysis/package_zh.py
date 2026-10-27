#!/usr/bin/env python3
"""把中文译文写进 translate.dat，并把改好的字体塞回 APK 的资源包。

流程
  1. translate.dat：把 `*_en` 条目的值替换成中文（语言按钮 lang_en 显示“中文”）
  2. respack.zr / respack000.zr：替换 fnt*.dat / fnt*.group.bin，追加新的字形表
  3. 重新打包 APK（保留各条目的压缩方式）
"""

from __future__ import annotations

import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(r"D:\project\逆向\北方的扩张")
TRANS = ROOT / "extracted" / "assets" / "translate.dat"
FONT_OUT = ROOT / "build" / "zh_font"
WORK = ROOT / "build" / "zh_apk"
SRC_APK = ROOT / "com.herocraft.game.majesty_ne.apk"
PACKS = ["huge", "huge_hi", "medium"]


def parse_translate(d: bytes) -> list[str]:
    recs, i = [], 0
    while i + 2 <= len(d):
        n = int.from_bytes(d[i:i + 2], "big")
        i += 2
        if i + n > len(d):
            break
        recs.append(d[i:i + n].decode("utf-8", "replace"))
        i += n
    return recs


def build_translate() -> tuple[Path, int, list[str]]:
    from zh_strings import ZH

    recs = parse_translate(TRANS.read_bytes())
    out, hit, missing = [], 0, set(ZH)
    for r in recs:
        key, sep, _val = r.partition(": ")
        if sep:
            if key == "lang_en":
                out.append(f"{key}: 中文")
                hit += 1
                continue
            if key.endswith("_en") and key[:-3] in ZH:
                out.append(f"{key}: {ZH[key[:-3]]}")
                missing.discard(key[:-3])
                hit += 1
                continue
        out.append(r)
    buf = bytearray()
    for r in out:
        raw = r.encode("utf-8")
        buf += len(raw).to_bytes(2, "big") + raw
    path = FONT_OUT / "assets" / "translate.dat"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(buf))
    print(f"translate.dat: {hit} 条已汉化 -> {path} ({len(buf)} bytes)")
    if missing:
        print(f"  ! 这些键在 translate.dat 里找不到: {sorted(missing)}")
    return path, hit, sorted(missing)


def patched_font_files(pack: str) -> dict[str, Path]:
    """basename(lower) -> patched file"""
    src = FONT_OUT / pack
    if not src.exists():
        return {}
    return {p.name.lower(): p for p in src.iterdir() if p.is_file()}


def rewrite_respack(archive: Path, fonts: dict[str, Path], out: Path) -> tuple[int, int]:
    replaced = added = 0
    with zipfile.ZipFile(archive) as zin, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        seen = set()
        for item in zin.infolist():
            name = item.filename
            key = name.rsplit("/", 1)[-1].lower()
            if key in fonts:
                data = fonts[key].read_bytes()
                zout.writestr(name, data, compress_type=item.compress_type or zipfile.ZIP_DEFLATED)
                seen.add(key)
                replaced += 1
            else:
                zout.writestr(item, zin.read(name))
        # 新增的字形表（fntM3.dat 之类的额外分册）
        for key, p in fonts.items():
            if key in seen:
                continue
            if not key.startswith("fnt") or not key.endswith((".dat", ".dti")):
                continue
            zout.writestr(p.name, p.read_bytes(), zipfile.ZIP_DEFLATED)
            added += 1
    return replaced, added


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    translate_path, _hit, _missing = build_translate()

    WORK.mkdir(parents=True, exist_ok=True)
    # 先把新的资源包写出来
    new_archives: dict[str, Path] = {}
    for pack in PACKS:
        fonts = patched_font_files(pack)
        if not fonts:
            print(f"{pack}: 没有构建产物，跳过")
            continue
        for arc_name in ("respack.zr", "respack000.zr"):
            src = ROOT / "extracted" / "assets" / pack / arc_name
            if not src.exists():
                print(f"  ! 缺少 {src}")
                continue
            dst = WORK / f"{pack}_{arc_name}"
            rep, add = rewrite_respack(src, fonts, dst)
            new_archives[f"assets/{pack}/{arc_name}"] = dst
            print(f"{pack}/{arc_name}: 替换 {rep} 个，新增 {add} 个 -> {dst.stat().st_size/1e6:.1f} MB")

    # ---- 打 APK ----
    out_apk = ROOT / "build" / "majesty_zh_cn.apk"
    drop = {"assets/translate.dat"} | set(new_archives)
    with zipfile.ZipFile(SRC_APK) as zin, zipfile.ZipFile(out_apk, "w") as zout:
        for item in zin.infolist():
            if item.filename.startswith("META-INF/"):
                continue
            if item.filename in drop:
                continue
            zout.writestr(item, zin.read(item.filename))
        zout.writestr("assets/translate.dat", translate_path.read_bytes(), zipfile.ZIP_DEFLATED)
        for name, path in new_archives.items():
            zout.writestr(name, path.read_bytes(), zipfile.ZIP_DEFLATED)
    print(f"APK -> {out_apk} ({out_apk.stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
