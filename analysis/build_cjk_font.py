#!/usr/bin/env python3
"""Add real Chinese glyphs to the game's bitmap fonts.

Design notes (see gxfont.py for the file formats):

* The game's font is a texture atlas plus several glyph "decks".  A deck stores
  `ch` values that are combined with the deck's page byte, `cp = (page << 8) | ch`,
  and the runtime searches the decks for the codepoint it just decoded from the
  UTF-8 string.  Nothing is remapped: a Chinese character keeps its real
  codepoint (U+4E00..U+9FFF), so `translate.dat` holds plain UTF-8 Chinese.
* Each deck's count byte is one byte wide, so a deck tops out at 255 records.
  The shipped decks 0 and 1 carry page 0, so `cp = ch` and any BMP codepoint can
  be stored there; they are filled first -- most frequent characters first --
  and only the overflow goes into freshly added decks.
* `fnt<fam>2.dat` ships with page 4 (the Cyrillic bucket), so a CJK record put
  there would be indexed as `0x04xx` and never found.  Those decks are skipped.
* `fntM3.dti` is *not* a glyph deck (its records do not line up with the
  14-byte layout -- the "bearing" bytes read as -1/-2/0/1), so `.dti` files are
  left untouched and new decks are always written as `.dat`.
* Glyph boxes are bottom-aligned: the renderer draws the box so its last row
  lands on the baseline (`dst_y = baseline + 1 - h`), and every shipped glyph
  keeps one blank row at the top and one at the bottom.  Therefore every new
  glyph is given the *same* box height (the ideographic em square + 2 padding
  rows) and the ink is placed at its natural offset inside that box -- otherwise
  short characters such as 一 / 二 / 人 would drop onto the baseline.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
from gxfont import Atlas, Glyph, read_deck, save_deck  # noqa: E402

ROOT = Path(r"D:\project\逆向\北方的扩张")
SRC_ROOT = ROOT / "extracted" / "_res" / "assets"
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\Deng.ttf",
]
PAD_TOP = 1
PAD_BOTTOM = 1

# A deck's leading byte is the record count.  Filling it to 255 makes the whole
# deck behave as "invalid" in this engine (ASCII glyphs stop resolving), so cap
# every deck one short of that and spill the rest into extra decks.
MAX_DECK = 254
EM_SAMPLE = "国田回目日"          # characters that fill the ideographic square

# ranges that are laid out on a full-width grid
_WIDE_RANGES = (
    (0x2E80, 0x303F),   # CJK radicals, punctuation (、。〈〉《》「」…)
    (0x3041, 0x33FF),   # kana, CJK compatibility
    (0x3400, 0x4DBF),   # ext-A
    (0x4E00, 0x9FFF),   # main CJK block
    (0xF900, 0xFAFF),   # compatibility ideographs
    (0xFE30, 0xFE4F),   # CJK compatibility forms
    (0xFF01, 0xFF60),   # fullwidth forms （），！？
    (0xFFE0, 0xFFE6),
)


def is_wide(ch: str) -> bool:
    cp = ord(ch)
    return any(a <= cp <= b for a, b in _WIDE_RANGES)


# --------------------------------------------------------------------- fonts
_font_cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def get_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            key = (path, size)
            if key not in _font_cache:
                _font_cache[key] = ImageFont.truetype(path, size)
            return _font_cache[key]
    raise FileNotFoundError("no CJK font found")


_em_cache: dict[int, tuple[int, int]] = {}


def em_box(size: int) -> tuple[int, int]:
    """Vertical extent of the ideographic em square, relative to the text origin."""
    if size in _em_cache:
        return _em_cache[size]
    f = get_font(size)
    tops, bots = [], []
    for ch in EM_SAMPLE:
        b = f.getbbox(ch)
        if b:
            tops.append(b[1])
            bots.append(b[3])
    res = (min(tops), max(bots)) if tops else (0, size)
    _em_cache[size] = res
    return res


def pick_size(target_h: int) -> int:
    """Pixel size whose em square is closest to `target_h` rows tall."""
    best = (max(6, target_h), 10 ** 6)
    for size in (target_h, target_h + 1, target_h - 1, target_h + 2, target_h - 2):
        if size < 6:
            continue
        top, bot = em_box(size)
        d = abs((bot - top) - target_h)
        if d < best[1]:
            best = (size, d)
    return best[0]


_mask_cache: dict[tuple[str, int], tuple[bytes, int, int, int]] = {}


def render_mask(ch: str, size: int) -> tuple[bytes, int, int, int]:
    """Ink mask of one character.

    Returns (grayscale bytes, w, h, top) where `top` is the ink top measured from
    the top of the ideographic em square (may be slightly negative).
    """
    key = (ch, size)
    if key in _mask_cache:
        return _mask_cache[key]
    font = get_font(size)
    ox = oy = size * 2 + 4
    img = Image.new("L", (size * 4 + 8, size * 4 + 8), 0)
    ImageDraw.Draw(img).text((ox, oy), ch, fill=255, font=font)
    bbox = img.getbbox()
    if bbox is None:
        _mask_cache[key] = (b"", 0, 0, 0)
        return _mask_cache[key]
    crop = img.crop(bbox)
    w, h = crop.size
    top = bbox[1] - (oy + em_box(size)[0])
    _mask_cache[key] = (crop.tobytes(), w, h, top)
    return _mask_cache[key]


# --------------------------------------------------------------------- decks
def family_files(pack_dir: Path, fam: str) -> tuple[Path | None, dict[int, Path]]:
    """Locate the atlas and the numbered `.dat` decks of one family.

    `.dti` files are deliberately ignored: they do not parse as 14-byte glyph
    decks, so they must not be rewritten.
    """
    atlas = None
    decks: dict[int, Path] = {}
    for p in pack_dir.iterdir():
        low = p.name.lower()
        if not low.startswith(f"fnt{fam.lower()}"):
            continue
        stem = p.name[4:].lower()          # e.g. "m0.group.bin" / "m1.dat"
        idx = stem[:1]
        if not idx.isdigit():
            continue
        if low.endswith(".group.bin") and idx == "0":
            atlas = p
        elif low.endswith(".dat"):
            decks.setdefault(int(idx), p)
    return atlas, decks


class Shelf:
    """Trivial shelf packer: fill rows left to right below the shipped glyphs."""

    def __init__(self, x0: int, y0: int, width: int, cell_h: int):
        self.x = x0
        self.y = y0
        self.width = width
        self.cell_h = cell_h
        self.row_h = cell_h

    def place(self, w: int, h: int) -> tuple[int, int]:
        self.row_h = max(self.row_h, h)
        if self.x + w > self.width:
            self.x = 0
            self.y += self.row_h + 1
        pos = (self.x, self.y)
        self.x += w + 1
        return pos


def cap_height(glyphs: list[Glyph]) -> int:
    """Cap height in *ink* pixels: shipped boxes carry one blank row top+bottom."""
    hs = [g.h - 2 for g in glyphs if 0x41 <= g.ch <= 0x5A and g.w]
    if not hs:
        hs = [g.h - 2 for g in glyphs if g.w]
    hs.sort()
    return hs[len(hs) // 2] if hs else 10


def build_family(pack_dir: Path, out_dir: Path, fam: str, charset: list[str],
                 ink_ratio: float = 1.4, ink_cap: int = 26, verbose: bool = True) -> dict:
    atlas_path, deck_paths = family_files(pack_dir, fam)
    if atlas_path is None or not deck_paths:
        return {"skipped": True}

    atlas = Atlas(atlas_path)
    decks: dict[int, tuple[int, list[Glyph], bytes]] = {}
    for idx, p in sorted(deck_paths.items()):
        decks[idx] = read_deck(p)

    # glyph boxes already in use -> first free row
    used = [g.box for _page, gls, _tail in decks.values() for g in gls if g.w and g.h]
    caps = cap_height([g for _p, gls, _t in decks.values() for g in gls])
    ink_h = max(9, min(int(round(caps * ink_ratio)), ink_cap))

    # one pixel size for the whole family: keeps stroke weight and metrics even
    size = pick_size(ink_h)
    em_top, em_bot = em_box(size)
    em_h = em_bot - em_top
    # Han ink fills the whole em box, unlike Latin which carries its own
    # side bearings.  A box exactly as wide as the ink makes neighbouring
    # glyphs touch, so give every wide glyph 1px of breathing room on each
    # side (box_w = ink + 2, advance = box_w).
    adv_wide = em_h + 2
    box_h = em_h + PAD_TOP + PAD_BOTTOM

    # how much room do we need?  pick the smallest power-of-two-ish canvas
    y0 = max((y + h for _x, y, _w, h in used), default=0) + 1
    new_w = new_h = None
    for cw, chh in ((512, 512), (1024, 512), (1024, 1024), (2048, 1024), (2048, 2048)):
        if cw < atlas.w or chh < atlas.h:
            continue
        per_row = max(1, cw // (adv_wide + 1))
        rows = (len(charset) + per_row - 1) // per_row
        if chh >= y0 + rows * (box_h + 2):
            new_w, new_h = cw, chh
            break
    if new_w is None:
        raise RuntimeError(f"{fam}: charset too large for any atlas size")
    if (new_w, new_h) != (atlas.w, atlas.h):
        atlas.resize(new_w, new_h)

    shelf = Shelf(0, y0, atlas.w, box_h)
    new_glyphs: list[Glyph] = []
    taller = 0
    for ch in charset:
        mask, mw, mh, top = render_mask(ch, size)
        if not mw:
            continue
        wide = is_wide(ch)
        box_w = adv_wide if wide else mw
        advance = adv_wide if wide else max(1, mw)
        dx = (box_w - mw) // 2 if wide else 0
        dy = PAD_TOP + top
        gh = box_h
        if dy < 0:                        # ink pokes above the em square
            gh += -dy                     # grow the box, keep the ink in place
            dy = 0
        need = dy + mh + PAD_BOTTOM
        if need > gh:                     # ink pokes below it
            gh = need
        if mh <= 0 or box_w <= 0:
            continue
        x, y = shelf.place(box_w, gh)
        if y + gh > atlas.h:
            raise RuntimeError(f"{fam}: atlas overflow at {ch!r}")
        atlas.clear_box(x, y, box_w, gh)
        for gy in range(mh):
            row = mask[gy * mw:(gy + 1) * mw]
            for gx in range(mw):
                a = row[gx]
                if a:
                    atlas.set_alpha(x + dx + gx, y + dy + gy, a)
        if gh != box_h:
            taller += 1
        new_glyphs.append(Glyph(ch=ord(ch) & 0xFFFF, bearing=0, advance=advance,
                                pad=0, x=x, y=y, w=box_w, h=gh, flag=0))

    # ---- distribute the records over the decks (page-0 decks first) ----
    deck_order = sorted(decks.keys())
    pages = {idx: decks[idx][0] for idx in deck_order}
    counts = {idx: len(decks[idx][1]) + (1 if decks[idx][2] else 0) for idx in deck_order}
    additions: dict[int, list[Glyph]] = {idx: [] for idx in deck_order}

    # only page-0 decks can hold CJK: there cp == ch, so the real codepoint is
    # found.  page-4 decks (Cyrillic) would shift every record to 0x04xx.
    queue = list(new_glyphs)
    for idx in deck_order:
        if pages[idx] != 0:
            continue
        room = MAX_DECK - counts[idx]
        take = queue[:room]
        additions[idx] += take
        queue = queue[room:]

    # extra decks for whatever did not fit (page 0 keeps cp = ch)
    overflow = queue
    next_idx = max(deck_order) + 1
    extra = []
    while overflow:
        chunk, overflow = overflow[:MAX_DECK], overflow[MAX_DECK:]
        additions[next_idx] = chunk
        pages[next_idx] = 0
        extra.append(next_idx)
        next_idx += 1

    # ---- write everything ----
    out_dir.mkdir(parents=True, exist_ok=True)
    atlas.save(out_dir / atlas_path.name)
    for idx, p in sorted(deck_paths.items()):
        page, gls, tail = decks[idx]
        if additions[idx]:
            save_deck(out_dir / p.name, page, gls + additions[idx], tail)
        else:
            (out_dir / p.name).write_bytes(p.read_bytes())
    for idx in extra:
        save_deck(out_dir / f"fnt{fam}{idx}.dat", 0, additions[idx])

    info = {
        "family": fam,
        "atlas": f"{atlas.w}x{atlas.h}",
        "size": size,
        "ink": em_h,
        "glyphs": len(new_glyphs),
        "clipped": taller,
        "decks": {idx: len(additions[idx]) for idx in sorted(additions) if additions[idx]},
        "extra_decks": extra,
    }
    if verbose:
        print(f"  {fam}: atlas {atlas.w}x{atlas.h} size={size}px ink={em_h}px "
              f"box_h={box_h} adv={adv_wide} glyphs={len(new_glyphs)} "
              f"clipped={taller} decks={info['decks']} extra={extra}")
    return info


def build_pack(pack: str, charset: list[str], out_root: Path) -> list[dict]:
    src = SRC_ROOT / pack / "respack"
    if not src.exists():
        print(f"{pack}: no unpacked resources, skipped")
        return []
    print(f"=== pack {pack}")
    out = out_root / pack
    caps = {"M": 16, "A": 20, "W": 18}
    # body text needs a touch more ink than the shipped Latin cap height to
    # stay legible at 1280x720; headings are already large enough
    ratios = {"M": 1.5, "A": 1.4, "W": 1.4}
    return [build_family(src, out, fam, charset, ink_ratio=ratios[fam],
                         ink_cap=caps[fam]) for fam in ("M", "A", "W")]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.path.insert(0, str(Path(__file__).parent))
    from zh_strings import ZH

    text = "".join(ZH.values())
    seen: dict[str, int] = {}
    for ch in text:
        if ch.isascii():
            continue
        if ch in "\n^":
            continue
        seen[ch] = seen.get(ch, 0) + 1
    # most frequent first so the guaranteed decks get the most useful glyphs
    charset = sorted(seen, key=lambda c: (-seen[c], c))
    print(f"charset: {len(charset)} distinct non-ASCII characters")

    packs = sys.argv[1:] or ["huge", "huge_hi", "medium"]
    for pack in packs:
        build_pack(pack, charset, ROOT / "build" / "zh_font")


if __name__ == "__main__":
    main()
