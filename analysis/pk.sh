#!/bin/bash
# 用法: ./pk.sh "命令" [等待秒] [截图名]
# 推送命令 → 等待 → 截图 → 回读输出
cd "$(dirname "$0")/.." || exit 1
PKG=com.herocraft.game.majesty_ne
CMD="$1"
WAIT="${2:-3}"
SHOT="${3:-_pk}"

DIR=/storage/emulated/0/Android/data/$PKG/files
printf '%s\n' "$CMD" > build/zhcmd.txt
MSYS_NO_PATHCONV=1 adb push build/zhcmd.txt $DIR/zhcmd.txt >/dev/null 2>&1 || { echo "PUSH FAIL"; exit 1; }
sleep "$WAIT"
adb exec-out screencap -p > "build/$SHOT.png" 2>/dev/null
MSYS_NO_PATHCONV=1 adb pull $DIR/zhout.txt build/zhout.txt >/dev/null 2>&1
echo "=== CMD: $CMD ==="
tail -40 build/zhout.txt
