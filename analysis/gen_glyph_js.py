#!/usr/bin/env python3
"""生成阶段3验证脚本：把一批汉字光栅化后写进 Frida JS（内嵌十六进制位图）。

用法:  python gen_glyph_js.py "中文字体测试" 22 analysis/js/41_glyph.js
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

TTF = r"C:\Windows\Fonts\simhei.ttf"

TEMPLATE = r"""// 自动生成：把汉字字形塞进引擎字体图集并注册码位
const STR_VA = 0x45cd90, DRAW_VA = 0x110088;
const REWRITE = %(rewrite)s;
const GLYPHS = [
%(glyphs)s
];

function findImage() {
  const ranges = Process.enumerateRanges({ protection: 'r--', coalesce: true });
  for (const r of ranges) {
    if (r.size > 0x8000000 || r.size < 0x100000) continue;
    try {
      const hits = Memory.scanSync(r.base, r.size, '39 43 49 77 47 78 46 6f 6e 74');
      if (hits.length) return hits[0].address.sub(STR_VA);
    } catch (e) { }
  }
  return null;
}
const img = findImage();
send('img=' + img);

const f = (n) => Module.findExportByName('libGLESv2.so', n);
const N = (n, r, a) => new NativeFunction(f(n), r, a);
const glGenFramebuffers = N('glGenFramebuffers', 'void', ['int', 'pointer']);
const glBindFramebuffer = N('glBindFramebuffer', 'void', ['int', 'uint']);
const glFramebufferTexture2D = N('glFramebufferTexture2D', 'void', ['int', 'int', 'int', 'uint', 'int']);
const glCheckFramebufferStatus = N('glCheckFramebufferStatus', 'uint', ['int']);
const glGetIntegerv = N('glGetIntegerv', 'void', ['int', 'pointer']);
const glBindTexture = N('glBindTexture', 'void', ['int', 'uint']);
const glReadPixels = N('glReadPixels', 'void', ['int', 'int', 'int', 'int', 'uint', 'uint', 'pointer']);
const glTexSubImage2D = N('glTexSubImage2D', 'void', ['int', 'int', 'int', 'int', 'int', 'int', 'uint', 'uint', 'pointer']);
const glGetTexLevel = N('glGetTexLevelParameteriv', 'void', ['int', 'int', 'int', 'pointer']);
const glGetError = N('glGetError', 'uint', []);
const GL_TEX2D = 0x0DE1, GL_FBO = 0x8D40, GL_COLOR0 = 0x8CE0;

let fboId = 0;
function readRect(id, sx, sy, w, h) {
  const pf = Memory.alloc(4), pt = Memory.alloc(4), fb = Memory.alloc(4);
  if (!fboId) { glGenFramebuffers(1, fb); fboId = fb.readU32(); }
  glGetIntegerv(0x8CA6, pf); glGetIntegerv(0x8069, pt);
  glBindFramebuffer(GL_FBO, fboId);
  glBindTexture(GL_TEX2D, id);
  glFramebufferTexture2D(GL_FBO, GL_COLOR0, GL_TEX2D, id, 0);
  let out = null;
  if (glCheckFramebufferStatus(GL_FBO) === 0x8CD5) {
    out = Memory.alloc(w * h * 4);
    glReadPixels(sx, sy, w, h, 0x1908, 0x1401, out);
  }
  glBindFramebuffer(GL_FBO, pf.readU32());
  glBindTexture(GL_TEX2D, pt.readU32());
  return out;
}

function hexToBuf(hex) {
  const n = hex.length / 2;
  const out = Memory.alloc(n);
  for (let i = 0; i < n; i++) out.add(i).writeU8(parseInt(hex.substr(i * 2, 2), 16));
  return out;
}

const gMalloc = new NativeFunction(Module.findExportByName(null, 'malloc'), 'pointer', ['ulong']);

let frames = 0, tried = false, targetFont = null;
Interceptor.attach(img.add(DRAW_VA), {
  onEnter(args) {
    frames++;
    if (!tried && frames >= 30) {
      tried = true;
      try { run(args[0]); targetFont = args[0]; } catch (e) { send('ERR ' + e + '\n' + e.stack); }
      return;
    }
    if (!targetFont || !args[0].equals(targetFont)) return;
    const text = args[2], len = args[3].toInt32();
    if (len <= 0 || len > 60) return;
    try {
      const s = text.readUtf16String(len);
      if (!/^[A-Za-z]+$/.test(s)) return;
      Memory.protect(text, (len + 1) * 2, 'rw-');
      for (let i = 0; i < len; i++) text.add(i * 2).writeU16(REWRITE.charCodeAt(i %% REWRITE.length));
    } catch (e) { }
  }
});

function run(font) {
  const count = font.add(0x08).readU32();
  const cap = font.add(0x1c).readU32();
  const codesPtr = font.add(0x10).readPointer();
  const recsPtr = font.add(0x28).readPointer();
  const page = font.add(0x40).readPointer().readPointer();
  const W = page.add(0x1c).readFloat() | 0, H = page.add(0x20).readFloat() | 0;
  send('font=' + font + ' count=' + count + ' cap=' + cap + ' page=' + W + 'x' + H);

  // ---- 识别图集 ----
  const glyphs = [];
  for (let i = 0; i < count && glyphs.length < 60; i++) {
    const rp = recsPtr.add(i * 8).readPointer();
    if (rp.isNull()) continue;
    const r = []; for (let k = 0; k < 8; k++) r.push(rp.add(k * 2).readS16());
    if (r[6] > 2 && r[7] > 5 && r[4] >= 0 && r[5] >= 0) glyphs.push(r);
  }
  const cands = [];
  for (let id = 1; id <= 200; id++) {
    const b = Memory.alloc(4);
    glBindTexture(GL_TEX2D, id);
    glGetTexLevel(GL_TEX2D, 0, 0x1000, b); if (b.readS32() !== W) continue;
    glGetTexLevel(GL_TEX2D, 0, 0x1001, b); if (b.readS32() !== H) continue;
    cands.push(id);
  }
  let atlasId = -1, bestHits = -1;
  for (const id of cands) {
    let hits = 0;
    for (const r of glyphs) {
      const px = readRect(id, r[4], r[5], r[6], r[7]);
      if (!px) continue;
      let ink = 0;
      for (let i = 0; i < r[6] * r[7]; i++) if (px.add(i * 4 + 3).readU8() > 8) ink++;
      if (ink / (r[6] * r[7]) > 0.25) hits++;
    }
    send('  id=' + id + ' 命中 ' + hits + '/' + glyphs.length);
    if (hits > bestHits) { bestHits = hits; atlasId = id; }
  }
  send('atlas id=' + atlasId + ' (' + bestHits + '/' + glyphs.length + ')');
  if (atlasId < 0 || bestHits < glyphs.length * 0.5) return;

  // ---- 读回整张图集，建立占用表 ----
  const atlas = readRect(atlasId, 0, 0, W, H);
  if (!atlas) { send('读回失败'); return; }
  const occ = new Uint8Array(W * H);
  for (let i = 0; i < W * H; i++) occ[i] = atlas.add(i * 4 + 3).readU8() > 8 ? 1 : 0;

  function findSlot(w, h) {
    for (let y = H - h; y >= 0; y--) {
      for (let x = 0; x + w <= W; x++) {
        let ok = true;
        for (let yy = y; yy < y + h && ok; yy++)
          for (let xx = x; xx < x + w; xx++)
            if (occ[yy * W + xx]) { ok = false; break; }
        if (ok) return [x, y];
      }
    }
    return null;
  }

  // ---- 逐个上传并注册 ----
  let added = 0;
  for (const g of GLYPHS) {
    if (count + added >= cap) { send('码表已满，停止'); break; }
    const slot = findSlot(g.w, g.h);
    if (!slot) { send('U+' + g.code.toString(16) + ' 没有空位'); continue; }
    const [sx, sy] = slot;
    for (let yy = sy; yy < sy + g.h; yy++) for (let xx = sx; xx < sx + g.w; xx++) occ[yy * W + xx] = 1;

    const buf = hexToBuf(g.hex);
    const pt = Memory.alloc(4);
    glGetIntegerv(0x8069, pt);
    glBindTexture(GL_TEX2D, atlasId);
    glTexSubImage2D(GL_TEX2D, 0, sx, sy, g.w, g.h, 0x1908, 0x1401, buf);
    glBindTexture(GL_TEX2D, pt.readU32());
    const err = glGetError();
    if (err) { send('上传 U+' + g.code.toString(16) + ' err=0x' + err.toString(16)); continue; }

    // 插入码位（保持升序）
    const n = count + added;
    let ins = n;
    for (let i = 0; i < n; i++) if (codesPtr.add(i * 2).readU16() > g.code) { ins = i; break; }
    for (let i = n; i > ins; i--) {
      codesPtr.add(i * 2).writeU16(codesPtr.add((i - 1) * 2).readU16());
      recsPtr.add(i * 8).writePointer(recsPtr.add((i - 1) * 8).readPointer());
    }
    codesPtr.add(ins * 2).writeU16(g.code);
    const rec = gMalloc(16);
    const vals = [g.dx, g.dy, g.adv, 0, sx, sy, g.w, g.h];
    for (let k = 0; k < 8; k++) rec.add(k * 2).writeS16(vals[k]);
    recsPtr.add(ins * 8).writePointer(rec);
    added++;
    send('U+' + g.code.toString(16) + ' -> (' + sx + ',' + sy + ') ' + g.w + 'x' + g.h +
      ' 记录=' + vals.join(','));
  }

  if (added > 0) {
    font.add(0x08).writeU32(count + added);
    font.add(0x18).writeU32(count + added);
    font.add(0x30).writeU32(count + added);
    send('完成：新增 ' + added + ' 个字，count ' + count + ' -> ' + (count + added));
  }
}
setTimeout(() => { send({ done: true }); }, 25000);
"""


def build(text: str, size: int) -> str:
    fnt = ImageFont.truetype(TTF, size)
    parts = []
    for ch in text:
        if ch in [p.split('code:')[0] for p in parts]:
            continue
        im = Image.new("L", (size * 2, size * 2), 0)
        ImageDraw.Draw(im).text((size // 2, size // 2), ch, font=fnt, fill=255)
        bb = im.getbbox()
        if not bb:
            continue
        im = im.crop(bb)
        w, h = im.size
        px = im.load()
        rgba = bytearray()
        for y in range(h):
            for x in range(w):
                rgba += bytes((255, 255, 255, px[x, y]))
        adv = max(w + 1, int(size * 0.95))
        parts.append(
            "  { code: 0x%04x, dx: %d, dy: %d, adv: %d, w: %d, h: %d, hex: '%s' },"
            % (ord(ch), 1, max(0, 24 - h), adv, w, h, rgba.hex())
        )
    return TEMPLATE % {"glyphs": "\n".join(parts), "rewrite": repr(text)}


def main() -> None:
    text = sys.argv[1] if len(sys.argv) > 1 else "中文字体测试"
    size = int(sys.argv[2]) if len(sys.argv) > 2 else 22
    out = Path(sys.argv[3] if len(sys.argv) > 3 else "analysis/js/41_glyph.js")
    out.write_text(build(text, size), encoding="utf-8")
    print(f"已生成 {out}  ({len(set(text))} 个字, size={size})")


if __name__ == "__main__":
    main()
