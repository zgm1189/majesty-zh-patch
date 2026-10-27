#!/usr/bin/env python3
"""PoC 4: append a brand new glyph record (U+4E2D) instead of overwriting one.

This is the capacity test: if the engine accepts an extra .dat record plus a new
glyph drawn in the atlas' blank area, then a full Chinese font (1000+ glyphs)
is feasible. If it rejects the record, we are limited to the existing 233 slots.
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

NEW_CHAR = 0x4E2D          # 中
GW = GH = 16               # new glyph box
NEW_X, NEW_Y = 0, 64       # blank atlas area (existing glyphs end around y=35)

PS_TEMPLATE = """
Add-Type -AssemblyName System.Drawing
$bmp = New-Object System.Drawing.Bitmap({W}, {H})
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.Clear([System.Drawing.Color]::Black)
$g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::SingleBitPerPixelGridFit
$font = New-Object System.Drawing.Font('SimSun', {SIZE}, [System.Drawing.FontStyle]::Regular, [System.Drawing.GraphicsUnit]::Pixel)
$g.DrawString([char]{CODE}, $font, [System.Drawing.Brushes]::White, -1, -2)
$g.Dispose()
for ($y = 0; $y -lt {H}; $y++) {{
  $line = ''
  for ($x = 0; $x -lt {W}; $x++) {{ $line += $(if ($bmp.GetPixel($x, $y).R -gt 100) {{ '#' }} else {{ '.' }}) }}
  Write-Output $line
}}
$bmp.Dispose()
"""


def render(code: int, w: int, h: int) -> list[str]:
    size = max(6, min(w, h) + 1)
    script = PS_TEMPLATE.format(W=w, H=h, SIZE=size, CODE=code)
    r = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    lines = [ln.strip() for ln in r.stdout.splitlines() if ln.strip() and set(ln.strip()) <= {"#", "."}]
    if not lines and r.stderr:
        print(f"    renderer stderr: {r.stderr.strip()[:200]}")
    return lines[-h:] if len(lines) >= h else lines


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    OUT.mkdir(parents=True, exist_ok=True)

    # ---------- 1) append the .dat record ----------
    datp = SRC / "fntm0.dat"
    dat = bytearray(datp.read_bytes())
    head = int.from_bytes(dat[0:2], "little")
    n = (len(dat) - 2) // 14
    metric = None
    for i in range(n):
        o = 2 + i * 14
        if int.from_bytes(dat[o : o + 2], "little") == ord("A"):
            metric = bytes(dat[o + 2 : o + 4])
            break
    if metric is None:
        metric = b"\x03\x09"
    rec = bytearray()
    rec += NEW_CHAR.to_bytes(2, "little")
    rec += metric
    rec += (NEW_X >> 16).to_bytes(2, "little")
    rec += (NEW_X & 0xFFFF).to_bytes(2, "little")
    rec += NEW_Y.to_bytes(2, "little")
    rec += GW.to_bytes(2, "little")
    rec += GH.to_bytes(2, "little")
    dat += rec
    dat[0:2] = ((head + 1) & 0xFFFF).to_bytes(2, "little")
    (OUT / "fntm0.dat").write_bytes(bytes(dat))
    print(f"dat   : {len(datp.read_bytes())} -> {len(dat)} bytes   head {head} -> {head + 1}")

    # ---------- 2) draw the glyph in the atlas ----------
    raw = bytearray((SRC / "fntm0.group.bin").read_bytes())
    name, blocks = parse_container(bytes(raw))
    boff, bsize = blocks[0]
    hdr, bpp, aw, ah = resolve_geometry(bytes(raw), boff, bsize)
    dots = render(NEW_CHAR, GW, GH)
    print(f"atlas : {aw}x{ah} bpp={bpp} hdr={hdr}; drawing U+{NEW_CHAR:04X} {GW}x{GH} at ({NEW_X},{NEW_Y})")
    for ln in dots:
        print(f"    {ln}")
    pix = boff + hdr
    for gy in range(GH):
        row = dots[gy] if gy < len(dots) else "." * GW
        for gx in range(GW):
            on = gx < len(row) and row[gx] == "#"
            o = pix + ((NEW_Y + gy) * aw + (NEW_X + gx)) * 4
            raw[o : o + 4] = bytes((255, 255, 255, 255)) if on else bytes((0, 0, 0, 0))
    (OUT / "fntm0.group.bin").write_bytes(bytes(raw))
    (OUT / "fntm0.group").write_bytes((SRC / "fntm0.group").read_bytes())
    print(f"wrote {OUT / 'fntm0.group.bin'} and {OUT / 'fntm0.dat'}")


if __name__ == "__main__":
    main()
