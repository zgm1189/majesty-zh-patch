#!/usr/bin/env python3
"""把一个 libzhfont.so 打进 APK，产出未签名包。

模板 APK 必须是「已经注入过加载器」的那个：
  lib/arm64-v8a/libs3e_android.so 的 .init_array 里多了一项，
  它会 dlopen("libzhfont.so")，所以只要替换 libzhfont.so 就能换功能。

用法：
  python tools/pack_apk.py --template <模板.apk> --so <libzhfont.so> --out <输出.apk>

脚本做的事：
  1. 逐条复制模板里的所有条目（保持各自原来的压缩方式，
     resources.arsc 必须是 STORED，否则 Android 11+ 直接装不上）
  2. 丢掉 META-INF/*（旧签名留着会让 apksigner 报错）
  3. 用新的 libzhfont.so 覆盖 lib/arm64-v8a/libzhfont.so
  4. 自检：确认 so 在、translate.dat 在、resources.arsc 仍为 STORED
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

SO_ENTRY = "lib/arm64-v8a/libzhfont.so"
DAT_ENTRY = "assets/translate.dat"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", required=True, type=Path, help="已注入加载器的模板 APK")
    ap.add_argument("--so", required=True, type=Path, help="要打进去的 libzhfont.so")
    ap.add_argument("--out", required=True, type=Path, help="输出的未签名 APK")
    args = ap.parse_args()

    if not args.template.is_file():
        print(f"[x] 模板不存在: {args.template}")
        return 1
    if not args.so.is_file():
        print(f"[x] so 不存在: {args.so}")
        return 1

    so_bytes = args.so.read_bytes()
    print(f"libzhfont.so : {len(so_bytes):,} bytes  ({args.so.name})")

    dropped = 0
    replaced = 0
    kept = 0
    with zipfile.ZipFile(args.template) as zin, zipfile.ZipFile(args.out, "w") as zout:
        for item in zin.infolist():
            name = item.filename
            if name.startswith("META-INF/"):
                dropped += 1
                continue
            if name == SO_ENTRY:
                zout.writestr(name, so_bytes, zipfile.ZIP_DEFLATED)
                replaced += 1
                continue
            # 原样搬运：compress_type 跟着 info 走，STORED 的条目不会被改成压缩
            zout.writestr(item, zin.read(name))
            kept += 1

        if replaced == 0:
            print(f"[!] 模板里没有 {SO_ENTRY}，改为新增条目")
            zout.writestr(SO_ENTRY, so_bytes, zipfile.ZIP_DEFLATED)

    print(f"entries kept={kept}  dropped(META-INF)={dropped}  so_replaced={replaced}")
    print(f"wrote {args.out}  ({args.out.stat().st_size:,} bytes)")

    # ---- 自检 ----
    ok = True
    with zipfile.ZipFile(args.out) as z:
        names = set(z.namelist())
        for need in (SO_ENTRY, DAT_ENTRY, "resources.arsc", "classes.dex"):
            if need not in names:
                print(f"[x] 缺少 {need}")
                ok = False
        info = z.getinfo("resources.arsc")
        if info.compress_type != zipfile.ZIP_STORED:
            print("[x] resources.arsc 不是 STORED，Android 11+ 会装不上")
            ok = False
        else:
            print("resources.arsc : STORED ✓")
        if SO_ENTRY in names:
            print(f"{SO_ENTRY}: {z.getinfo(SO_ENTRY).file_size:,} bytes ✓")
        print(f"total entries  : {len(names)}")

    if not ok:
        print("[x] 自检失败")
        return 2
    print("[ok] 打包完成，接着跑 zipalign + apksigner")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
