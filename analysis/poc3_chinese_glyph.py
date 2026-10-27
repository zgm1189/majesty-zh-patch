#!/usr/bin/env python3
"""PoC 3: replace one ASCII glyph with a real Chinese character.

The profile screen currently renders the literal text "TESTM", so swapping the
glyph for 'M' with a rendered Chinese glyph should show up immediately as
"TEST<chinese>". Everything else (metrics, layout, the .dat table) is untouched.
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

TARGET_CHAR = "M"
CN_CHAR = "\u6d4b"  # 测

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


def render_dots(ch: str, w: int, h: int) -> list[str]:
    size = max(6, min(w, h) + 2)
    script = PS_TEMPLATE.format(W=w, H=h, SIZE=size, CODE=ord(ch))
    r = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    lines = [ln.strip() for ln in r.stdout.splitlines() if ln.strip() and set(ln.strip()) <= {"#", "."}]
    if not lines and r.stderr:
        print(f"    renderer stderr: {r.stderr.strip()[:200]}")
    return lines[-h:] if len(lines) >= h else lines


def patch(bin_name: str, dat_name: str) -> bool:
    raw = bytearray((SRC / bin_name).read_bytes())
    name, blocks = parse_container(bytes(raw))
    boff, bsize = blocks[0]
    hdr, bpp, aw, ah = resolve_geometry(bytes(raw), boff, bsize)
    dat = (SRC / dat_name).read_bytes()
    n = (len(dat) - 2) // 14
    rect = None
    for i in range(n):
        o = 2 + i * 14
        rec = dat[o : o + 14]
        if int.from_bytes(rec[0:2], "little") == ord(TARGET_CHAR):
            x = int.from_bytes(rec[4:6], "little") + int.from_bytes(rec[6:8], "little")
            y = int.from_bytes(rec[8:10], "little")
            w = int.from_bytes(rec[10:12], "little")
            h = int.from_bytes(rec[12:14], "little")
            rect = (x, y, w, h)
            break
    print(f"  {bin_name}: atlas {aw}x{ah} bpp={bpp} hdr={hdr}  '{TARGET_CHAR}' at {rect}")
    if rect is None or bpp != 4:
        print("    skipped (no rect or not 32-bit)")
        return False
    x, y, w, h = rect
    dots = render_dots(CN_CHAR, w, h)
    print(f"    rendered {CN_CHAR} as {w}x{h}:")
    for ln in dots:
        print(f"      {ln}")

    pix = boff + hdr
    for gy in range(h):
        row = dots[gy] if gy < len(dots) else "." * w
        for gx in range(w):
            on = gx < len(row) and row[gx] == "#"
            o = pix + ((y + gy) * aw + (x + gx)) * 4
            if on:
                raw[o : o + 4] = bytes((255, 255, 255, 255))
            else:
                raw[o : o + 4] = bytes((0, 0, 0, 0))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / bin_name).write_bytes(bytes(raw))
    # copy sibling files untouched so the device folder stays consistent
    for sib in (".group", ".dat"):
        p = SRC / bin_name.replace(".group.bin", sib)
        if p.exists():
            (OUT / p.name).write_bytes(p.read_bytes())
    print(f"    wrote {OUT / bin_name}")
    return True


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ok = 0
    for bin_name, dat_name in (("fntm0.group.bin", "fntm0.dat"), ("fntw0.group.bin", "fntw0.dat"),
                               ("fnta0.group.bin", "fnta0.dat")):
        try:
            if patch(bin_name, dat_name):
                ok += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  {bin_name}: FAILED {exc}")
    print(f"patched {ok} fonts")
