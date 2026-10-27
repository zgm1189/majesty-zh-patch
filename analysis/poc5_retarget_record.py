#!/usr/bin/env python3
"""PoC 5: rewrite an EXISTING record's character code (no size change).

Appending a record failed, so test whether the engine looks glyphs up by
character code: retarget the record of an unused ASCII char ('X') to U+4E2D and
draw the Chinese glyph in that slot. If "TEST中" renders, code lookup works and
all 233 existing slots can be repurposed for Chinese.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from export_groupbin import parse_container, resolve_geometry  # noqa: E402

ROOT = Path(r"D:\project\逆向\北方的扩张")
SRC = ROOT / "extracted" / "_res" / "assets" / "huge" / "respack"
OUT = ROOT / "build" / "poc_fonts" / "huge"

VICTIM = "X"          # ASCII char whose slot we repurpose
NEW_CHAR = 0x4E2D     # 中

PS_TEMPLATE = """
Add-Type -AssemblyName System.Drawing
$bmp = New-Object System.Drawing.Bitmap({W}, {H})
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.Clear([System.Drawing.Color]::Black)
$g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::SingleBitPerPixelGridFit
$font = New-Object System.Drawing.Font('SimSun', {SIZE}, [System.Drawing.FontStyle]::Regular, [System.Drawing.GraphicsUnit]::Pixel)
$g.DrawString([char]{CODE}, $font, [System.Drawing.Brushes]::White, -1, -1)
$g.Dispose()
for ($y = 0; $y -lt {H}; $y++) {{
  $line = ''
  for ($x = 0; $x -lt {W}; $x++) {{ $line += $(if ($bmp.GetPixel($x, $y).R -gt 100) {{ '#' }} else {{ '.' }}) }}
  Write-Output $line
}}
$bmp.Dispose()
"""


def render(code: int, w: int, h: int) -> list[str]:
    size = max(6, min(w, h) + 2)
    script = PS_TEMPLATE.format(W=w, H=h, SIZE=size, CODE=code)
    r = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    lines = [ln.strip() for ln in r.stdout.splitlines() if ln.strip() and set(ln.strip()) <= {"#", "."}]
    if not lines and r.stderr:
        print(f"    stderr: {r.stderr.strip()[:200]}")
    return lines[-h:] if len(lines) >= h else lines


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    OUT.mkdir(parents=True, exist_ok=True)

    # --- 1) retarget the record in place ---
    dat = bytearray((SRC / "fntm0.dat").read_bytes())
    n = (len(dat) - 2) // 14
    rect = None
    for i in range(n):
        o = 2 + i * 14
        if int.from_bytes(dat[o : o + 2], "little") == ord(VICTIM):
            dat[o : o + 2] = NEW_CHAR.to_bytes(2, "little")
            x = int.from_bytes(dat[o + 4 : o + 6], "little") + int.from_bytes(dat[o + 6 : o + 8], "little")
            y = int.from_bytes(dat[o + 8 : o + 10], "little")
            w = int.from_bytes(dat[o + 10 : o + 12], "little")
            h = int.from_bytes(dat[o + 12 : o + 14], "little")
            rect = (x, y, w, h)
            print(f"dat: '{VICTIM}' record at index {i} retargeted to U+{NEW_CHAR:04X}, rect={rect}")
            break
    if rect is None:
        print("victim not found")
        return
    (OUT / "fntm0.dat").write_bytes(bytes(dat))

    # --- 2) draw the Chinese glyph in that slot ---
    raw = bytearray((SRC / "fntm0.group.bin").read_bytes())
    name, blocks = parse_container(bytes(raw))
    boff, bsize = blocks[0]
    hdr, bpp, aw, ah = resolve_geometry(bytes(raw), boff, bsize)
    x, y, w, h = rect
    dots = render(NEW_CHAR, w, h)
    print(f"atlas {aw}x{ah} bpp={bpp}: drawing at ({x},{y}) size {w}x{h}")
    for ln in dots:
        print(f"    {ln}")
    pix = boff + hdr
    for gy in range(h):
        row = dots[gy] if gy < len(dots) else "." * w
        for gx in range(w):
            on = gx < len(row) and row[gx] == "#"
            o = pix + ((y + gy) * aw + (x + gx)) * 4
            raw[o : o + 4] = bytes((255, 255, 255, 255)) if on else bytes((0, 0, 0, 0))
    (OUT / "fntm0.group.bin").write_bytes(bytes(raw))
    (OUT / "fntm0.group").write_bytes((SRC / "fntm0.group").read_bytes())
    print("wrote fntm0.group.bin + fntm0.dat")


if __name__ == "__main__":
    main()
