#!/usr/bin/env bash
# 编译 libzhfont.so（完整版 / 纯翻译版）并打成 APK。
#
# 用法：
#   bash tools/build.sh so            # 只编译两个 so
#   bash tools/build.sh apk           # 编译 + 打包 + 签名，两个 APK 一起出
#   bash tools/build.sh apk lite      # 只出纯翻译版
#   bash tools/build.sh apk full      # 只出完整版
#
# 依赖（按需改下面这几个变量）：
#   NDK      NDK 根目录，需要 clang + llvm-readelf
#   BT       Android build-tools，需要 zipalign + apksigner
#   TEMPLATE 已注入加载器的模板 APK（见 docs/构建说明.md）
#   KEYSTORE 签名库，alias poc / 口令 android
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

NDK="${NDK:-D:/flutter/androidsdk/ndk/27.0.12077973/toolchains/llvm/prebuilt/windows-x86_64/bin}"
BT="${BT:-D:/flutter/androidsdk/build-tools/36.0.0}"
TEMPLATE="${TEMPLATE:-$ROOT/build/majesty_zh.apk}"
KEYSTORE="${KEYSTORE:-$ROOT/build/poc.keystore}"
KS_PASS="${KS_PASS:-android}"
KS_ALIAS="${KS_ALIAS:-poc}"
OUT="$ROOT/build/out"

CC="$NDK/clang.exe"
READELF="$NDK/llvm-readelf.exe"
CFLAGS=(--target=aarch64-linux-android26 -O2 -fPIC -shared -I"$ROOT/src")

# 字体子集编译成 .o（objcopy -I binary），只需做一次
ensure_ttf_obj() {
    local o="$ROOT/build/so/zhfont_ttf.o"
    if [ -f "$o" ]; then return; fi
    echo "==> 编译字体子集对象"
    mkdir -p "$ROOT/build/so"
    ( cd "$ROOT/build/so" && \
      cp "$ROOT/assets/zhfont_subset.ttf" . && \
      "$NDK/llvm-objcopy.exe" -I binary -O elf64-littleaarch64 -B aarch64 \
          zhfont_subset.ttf zhfont_ttf.o )
}

build_so() {
    local cheat="$1" out="$2"
    echo "==> 编译 libzhfont.so  (ZF_CHEAT=$cheat)"
    "$CC" "${CFLAGS[@]}" -DZF_CHEAT="$cheat" \
        -o "$out" "$ROOT/src/zhfont.c" "$ROOT/build/so/zhfont_ttf.o" \
        -ldl -llog -lm
    # 铁律：除了 libc/libdl 的标准符号，不能留任何 UND
    local bad
    bad="$("$READELF" --dyn-syms "$out" | grep ' UND ' | grep -v '@LIBC' | grep -v NOTYPE || true)"
    if [ -n "$bad" ]; then
        echo "[x] $out 有未定义符号："; echo "$bad"; exit 1
    fi
    echo "    $(basename "$out"): $(stat -c %s "$out" 2>/dev/null || wc -c < "$out") bytes，UND 干净"
}

sign_apk() {
    local unsigned="$1" aligned="$2" signed="$3"
    "$BT/zipalign.exe" -p -f 4 "$unsigned" "$aligned"
    rm -f "$signed" "$signed.idsig"
    "$BT/apksigner.bat" sign \
        --ks "$KEYSTORE" --ks-pass "pass:$KS_PASS" \
        --ks-key-alias "$KS_ALIAS" --key-pass "pass:$KS_PASS" \
        --v1-signing-enabled true --v2-signing-enabled true \
        --out "$signed" "$aligned"
    echo "    已签名: $signed"
}

do_so() {
    ensure_ttf_obj
    mkdir -p "$ROOT/build/so"
    build_so 1 "$ROOT/build/so/libzhfont_full.so"
    build_so 0 "$ROOT/build/so/libzhfont_lite.so"
}

do_apk() {
    local which="${1:-both}"
    if [ ! -f "$TEMPLATE" ]; then
        echo "[x] 模板 APK 不存在: $TEMPLATE"
        echo "    把已注入加载器的 APK 放到这个位置，或用 TEMPLATE=... 指定"
        exit 1
    fi
    do_so
    mkdir -p "$OUT"

    if [ "$which" = "both" ] || [ "$which" = "full" ]; then
        echo "==> 打包 完整版"
        python "$ROOT/tools/pack_apk.py" --template "$TEMPLATE" \
            --so "$ROOT/build/so/libzhfont_full.so" \
            --out "$OUT/unsigned_full.apk"
        sign_apk "$OUT/unsigned_full.apk" "$OUT/aligned_full.apk" \
                 "$OUT/北方的扩张_完整版.apk"
    fi

    if [ "$which" = "both" ] || [ "$which" = "lite" ]; then
        echo "==> 打包 纯翻译版"
        python "$ROOT/tools/pack_apk.py" --template "$TEMPLATE" \
            --so "$ROOT/build/so/libzhfont_lite.so" \
            --out "$OUT/unsigned_lite.apk"
        sign_apk "$OUT/unsigned_lite.apk" "$OUT/aligned_lite.apk" \
                 "$OUT/北方的扩张_纯翻译版.apk"
    fi

    echo
    ls -lh "$OUT"/*.apk
}

case "${1:-apk}" in
    so)  do_so ;;
    apk) do_apk "${2:-both}" ;;
    *)   echo "用法: bash tools/build.sh [so|apk] [full|lite]"; exit 1 ;;
esac
