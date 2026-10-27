#!/usr/bin/env python3
"""Capacity probe v3: cover *every* font family, test both mechanisms at once.

Findings so far:
  * the game loads fonts from files/huge/ and atlas edits take effect
  * dropping the 5-byte partial record at the end of fntM0/fntW0/fntA0
    destroys letter spacing (it is the header of the space glyph, U+0020)
  * labels drawn with M/W/A glyphs work, but the profile screen's
    "create profile" label clearly uses another family

So this pass patches every fntX0.group.bin / fntX0.dat pair found in the pack:

  * U+6587 (文) replaces an unused record in place (retarget, no size change)
  * U+4E2D (中) is appended as a brand new record for the M/W/A families
    (conservative: original bytes kept, head incremented)
  * U+005A (Z) is painted as a solid block -- control that our glyph box is
    the one being sampled

Probe labels read "中文Z", so a screenshot shows exactly which mechanisms work.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from export_groupbin import parse_container, resolve_geometry  # noqa: E402

ROOT = Path(r"D:\project\逆向\北方的扩张")
# original (never-pushed) fonts from each quality pack the game unpacks
SRC_ROOT = ROOT / "extracted" / "_res" / "assets"
TRANS = ROOT / "extracted" / "assets" / "translate.dat"
OUT = ROOT / "build" / "probe_cap"
PACKS = ["huge", "medium", "huge_hi"]

APPEND_CH = 0x4E2D     # 中
RETARGET_CH = 0x6587   # 文
CONTROL_CH = 0x005A    # Z
APPEND_FAMILIES = {"M", "W", "A"}
# candidates for the record we are allowed to repurpose, least-used first
VICTIMS = [0x00AC, 0x007E, 0x005E, 0x0060, 0x007B, 0x007D, 0x007C, 0x005C]
GW = GH = 16

PS_TEMPLATE = """
Add-Type -AssemblyName System.Drawing
$bmp = New-Object System.Drawing.Bitmap({W}, {H})
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.Clear([System.Drawing.Color]::Black)
$g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::SingleBitPerPixelGridFit
$font = New-Object System.Drawing.Font('SimSun', {SIZE}, [System.Drawing.FontStyle]::Regular, [System.Drawing.GraphicsUnit]::Pixel)
$g.DrawString([char]{CODE}, $font, [System.Drawing.Brushes]::White, {OX}, {OY})
$g.Dispose()
for ($y = 0; $y -lt {H}; $y++) {{
  $line = ''
  for ($x = 0; $x -lt {W}; $x++) {{ $line += $(if ($bmp.GetPixel($x, $y).R -gt 100) {{ '#' }} else {{ '.' }}) }}
  Write-Output $line
}}
$bmp.Dispose()
"""


def render(code: int, w: int, h: int) -> list[str]:
    script = PS_TEMPLATE.format(W=w, H=h, SIZE=max(8, h), CODE=code, OX=-1, OY=-1)
    r = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    lines = [ln.strip() for ln in r.stdout.splitlines()
             if ln.strip() and set(ln.strip()) <= {"#", "."}]
    return lines[-h:] if len(lines) >= h else lines


def read_deck(b: bytes):
    out = []
    for i in range((len(b) - 2) // 14):
        o = 2 + i * 14
        r = b[o : o + 14]
        ch = int.from_bytes(r[0:2], "little")
        x = int.from_bytes(r[6:8], "little")
        y = int.from_bytes(r[8:10], "little")
        w = int.from_bytes(r[10:12], "little")
        h = int.from_bytes(r[12:14], "little")
        if 1 <= w <= 64 and 1 <= h <= 64:
            out.append((o, ch, x, y, w, h))
    return out


def overlaps(a, b) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return not (ax + aw <= bx or bx + bw <= ax or ay + ah <= by or by + bh <= ay)


def find_blank(atlas, boff, hdr, aw, ah, w, h, avoid):
    pix = boff + hdr
    for y in range(ah - h, -1, -1):
        for x in range(aw - w, -1, -1):
            cand = (x, y, w, h)
            if any(overlaps(cand, r) for r in avoid):
                continue
            clear = True
            for gy in range(h):
                row = pix + ((y + gy) * aw + x) * 4
                for gx in range(w):
                    if atlas[row + gx * 4 + 3] != 0:
                        clear = False
                        break
                if not clear:
                    break
            if clear:
                return x, y
    return None


def paint(atlas, boff, hdr, aw, box, dots):
    x, y, w, h = box
    pix = boff + hdr
    for gy in range(h):
        row = dots[gy] if gy < len(dots) else "." * w
        for gx in range(w):
            on = gx < len(row) and row[gx] == "#"
            o = pix + ((y + gy) * aw + (x + gx)) * 4
            if o + 4 <= len(atlas):
                atlas[o : o + 4] = bytes((255, 255, 255, 255)) if on else bytes((0, 0, 0, 0))


def solid(atlas, boff, hdr, aw, box):
    x, y, w, h = box
    pix = boff + hdr
    for gy in range(h):
        for gx in range(w):
            o = pix + ((y + gy) * aw + (x + gx)) * 4
            if o + 4 <= len(atlas):
                atlas[o : o + 4] = bytes((255, 255, 255, 255))


def make_record(code, box):
    x, y, w, h = box
    metric = ((w - 1) << 8) | 3
    return (code.to_bytes(2, "little") + metric.to_bytes(2, "little") + b"\x00\x00"
            + x.to_bytes(2, "little") + y.to_bytes(2, "little")
            + w.to_bytes(2, "little") + h.to_bytes(2, "little"))


def process_pack(pack: str, dots_append, dots_retarget) -> None:
    """Patch every font pair of one quality pack."""
    src = SRC_ROOT / pack / "respack"
    out = OUT / pack
    if not src.exists():
        print(f"=== {pack}: no unpacked pack")
        return
    out.mkdir(parents=True, exist_ok=True)
    print(f"=== {pack}")
    dats = {p.name.lower(): p for p in src.glob("*.dat")}
    for atlas_path in sorted(src.glob("fnt*.group.bin")):
        stem = atlas_path.name.lower().replace(".group.bin", "")
        dat_path = dats.get(stem + ".dat")
        if dat_path is None:
            continue
        fam = stem[3].upper() if len(stem) > 3 else "?"
        raw = bytearray(atlas_path.read_bytes())
        grp, blocks = parse_container(bytes(raw))
        boff, bsize = blocks[0]
        geom = resolve_geometry(bytes(raw), boff, bsize)
        if geom is None:
            print(f"  {atlas_path.name}: geometry unresolved")
            continue
        hdr, bpp, aw, ah = geom
        if bpp != 4:
            print(f"  {atlas_path.name}: bpp={bpp}, skipped")
            continue

        # Every deck of the family shares one atlas; a character can be defined
        # in several decks (e.g. 'Z' exists in both fntM0 and fntM1) and the
        # later deck wins, so all of them must be considered.
        decks: dict[str, tuple[Path, int, int, list]] = {}
        avoid = []
        for suffix in ("0", "1", "2"):
            p = src / f"fnt{fam}{suffix}.dat"
            if not p.exists():
                continue
            b = p.read_bytes()
            head = int.from_bytes(b[0:2], "little")
            n = (len(b) - 2) // 14
            recs = read_deck(b)
            decks[suffix] = (p, head, n, recs)
            avoid += [(x, y, w, h) for _o, _c, x, y, w, h in recs]
        if not decks:
            continue
        retarget_xy = find_blank(raw, boff, hdr, aw, ah, GW, GH, avoid)
        if retarget_xy is None:
            print(f"  {atlas_path.name}: no blank space")
            continue
        retarget_box = (*retarget_xy, GW, GH)
        append_box = None
        if fam in APPEND_FAMILIES:
            append_xy = find_blank(raw, boff, hdr, aw, ah, GW, GH,
                                   avoid + [retarget_box])
            if append_xy:
                append_box = (*append_xy, GW, GH)

        paint(raw, boff, hdr, aw, retarget_box, dots_retarget)
        if append_box:
            paint(raw, boff, hdr, aw, append_box, dots_append)
        zboxes = []
        for _p, _h, _n, recs in decks.values():
            zboxes += [(x, y, w, h) for _o, c, x, y, w, h in recs if c == CONTROL_CH]
        for zb in zboxes:
            solid(raw, boff, hdr, aw, zb)
        assert len(raw) == atlas_path.stat().st_size
        (out / atlas_path.name).write_bytes(bytes(raw))

        for suffix, (p, head, n, recs) in decks.items():
            data = bytearray(p.read_bytes())
            note = [f"{aw}x{ah}", f"retarget@{retarget_xy}", f"Z blocks={len(zboxes)}"]
            if abs(head - n) > 2:
                note.append(f"header/layout mismatch head={head} recs={n}: record edits skipped")
            else:
                for victim in VICTIMS:
                    found = False
                    for o, c, *_ in recs:
                        if c == victim:
                            data[o : o + 14] = make_record(RETARGET_CH, retarget_box)
                            note.append(f"retarget U+{victim:04X}->U+{RETARGET_CH:04X}")
                            found = True
                            break
                    if found:
                        break
                if append_box is not None:
                    # fntM0/fntW0/fntA0 end with a 5-byte partial record (the
                    # space glyph). Pad it out to a full record first, otherwise
                    # the appended record shifts everything and glyphs break.
                    tail = (len(data) - 2) % 14
                    if tail:
                        data += b"\x00" * (14 - tail)
                        note.append(f"completed {tail}B partial record")
                    data += make_record(APPEND_CH, append_box)
                    data[0:2] = (head + 1).to_bytes(2, "little")
                    note.append(f"appended U+{APPEND_CH:04X} {head}->{head+1}")
            (out / p.name).write_bytes(bytes(data))
            print(f"  {p.name} ({atlas_path.name}): " + "; ".join(note))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    (OUT / "assets").mkdir(parents=True, exist_ok=True)

    dots_append = render(APPEND_CH, GW, GH)
    dots_retarget = render(RETARGET_CH, GW, GH)

    for pack in PACKS:
        process_pack(pack, dots_append, dots_retarget)

    # ---- translate.dat ----
    d = TRANS.read_bytes()
    recs, i = [], 0
    while i < len(d):
        ln = int.from_bytes(d[i : i + 2], "big")
        i += 2
        recs.append(d[i : i + ln].decode("utf-8"))
        i += ln
    PROBE = "中文Z"
    KEYS = {r.split(": ", 1)[0] for r in recs if ": " in r and (
        r.split(": ", 1)[0].startswith("lang_")
        or (r.split(": ", 1)[0].endswith("_en")
            and r.split(": ", 1)[0].startswith(("kd", "kO", "ui", "msg"))))}
    out_recs, hit = [], 0
    for r in recs:
        if ": " in r and r.split(": ", 1)[0] in KEYS:
            out_recs.append(f"{r.split(': ', 1)[0]}: {PROBE}")
            hit += 1
        else:
            out_recs.append(r)
    buf = bytearray()
    for r in out_recs:
        raw = r.encode("utf-8")
        buf += len(raw).to_bytes(2, "big") + raw
    (OUT / "assets" / "translate.dat").write_bytes(bytes(buf))
    print(f"translate.dat: {hit} labels -> {PROBE!r}")


if __name__ == "__main__":
    main()
