#!/usr/bin/env python3
"""生成「批量注入汉字」的 Frida 脚本：图集扩容 + 码表扩容 + 逐字光栅化上传。

用法:  python gen_inject_js.py <charset.txt> <size> <out.js> [重写串]
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

TTF = r"C:\Windows\Fonts\simhei.ttf"

TEMPLATE = r"""// 自动生成：批量注入汉字（图集与码表都会扩容）
const STR_VA = 0x45cd90, DRAW_VA = 0x110088;
const REWRITE = %(rewrite)s;
const BLOB = '%(blob)s';

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
const glTexImage2D = N('glTexImage2D', 'void', ['int', 'int', 'int', 'int', 'int', 'int', 'uint', 'uint', 'pointer']);
const glGetTexLevel = N('glGetTexLevelParameteriv', 'void', ['int', 'int', 'int', 'pointer']);
const glGetError = N('glGetError', 'uint', []);
const GL_TEX2D = 0x0DE1, GL_FBO = 0x8D40, GL_COLOR0 = 0x8CE0;

const gMalloc = new NativeFunction(Module.findExportByName(null, 'malloc'), 'pointer', ['ulong']);

// ---- 解析位图数据 ----
function parseBlob() {
  const bytes = [];
  for (let i = 0; i < BLOB.length; i += 2) bytes.push(parseInt(BLOB.substr(i, 2), 16));
  let p = 0;
  const rdU16 = () => { const v = bytes[p] | (bytes[p + 1] << 8); p += 2; return v; };
  const rdS16 = () => { const v = bytes[p] | (bytes[p + 1] << 8); p += 2; return v >= 0x8000 ? v - 0x10000 : v; };
  const n = rdU16();
  const out = [];
  for (let i = 0; i < n; i++) {
    const g = { code: rdU16(), w: rdU16(), h: rdU16(), adv: rdU16(), dy: rdS16(), dx: rdS16() };
    g.alpha = bytes.slice(p, p + g.w * g.h); p += g.w * g.h;
    out.push(g);
  }
  return out;
}

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
  const count0 = font.add(0x08).readU32();
  const codesPtr0 = font.add(0x10).readPointer();
  const recsPtr0 = font.add(0x28).readPointer();
  const page = font.add(0x40).readPointer().readPointer();
  const W0 = page.add(0x1c).readFloat() | 0, H0 = page.add(0x20).readFloat() | 0;
  const GLYPHS = parseBlob();
  send('font=' + font + ' count=' + count0 + ' page=' + W0 + 'x' + H0 + ' 待注入 ' + GLYPHS.length);

  // ---- 1. 识别图集 ----
  const glyphs = [];
  for (let i = 0; i < count0 && glyphs.length < 60; i++) {
    const rp = recsPtr0.add(i * 8).readPointer();
    if (rp.isNull()) continue;
    const r = []; for (let k = 0; k < 8; k++) r.push(rp.add(k * 2).readS16());
    if (r[6] > 2 && r[7] > 5 && r[4] >= 0 && r[5] >= 0) glyphs.push(r);
  }
  const cands = [];
  for (let id = 1; id <= 200; id++) {
    const b = Memory.alloc(4);
    glBindTexture(GL_TEX2D, id);
    glGetTexLevel(GL_TEX2D, 0, 0x1000, b); if (b.readS32() !== W0) continue;
    glGetTexLevel(GL_TEX2D, 0, 0x1001, b); if (b.readS32() !== H0) continue;
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
    if (hits > bestHits) { bestHits = hits; atlasId = id; }
  }
  send('atlas id=' + atlasId + ' 命中=' + bestHits + '/' + glyphs.length);
  if (atlasId < 0 || bestHits < glyphs.length * 0.5) { send('识别失败'); return; }

  // ---- 2. 估算需要的图集尺寸并扩容 ----
  let need = 0;
  for (const g of GLYPHS) need += (g.w + 2) * (g.h + 2);
  let NW = W0, NH = H0;
  while (NW * NH < need * 2.2) {
    if (NH < 2048) NH *= 2;
    else if (NW < 2048) NW *= 2;
    else break;
  }
  if (NW !== W0 || NH !== H0) {
    const old = readRect(atlasId, 0, 0, W0, H0);
    const big = gMalloc(NW * NH * 4);
    for (let i = 0; i < NW * NH; i++) big.add(i * 4 + 3).writeU8(0);
    for (let y = 0; y < H0; y++) {
      for (let x = 0; x < W0; x++) {
        const s = (y * W0 + x) * 4, d = (y * NW + x) * 4;
        big.add(d).writeU8(old.add(s).readU8());
        big.add(d + 1).writeU8(old.add(s + 1).readU8());
        big.add(d + 2).writeU8(old.add(s + 2).readU8());
        big.add(d + 3).writeU8(old.add(s + 3).readU8());
      }
    }
    const pt = Memory.alloc(4);
    glGetIntegerv(0x8069, pt);
    glBindTexture(GL_TEX2D, atlasId);
    glTexImage2D(GL_TEX2D, 0, 0x1908, NW, NH, 0, 0x1908, 0x1401, big);
    send('图集扩容 ' + W0 + 'x' + H0 + ' -> ' + NW + 'x' + NH + ' err=0x' + glGetError().toString(16));
    glBindTexture(GL_TEX2D, pt.readU32());
    page.add(0x1c).writeFloat(NW); page.add(0x20).writeFloat(NH);
    page.add(0x24).writeFloat(NW); page.add(0x28).writeFloat(NH);
  }
  const W = NW, H = NH;

  // ---- 3. 建立占用表，并算出最后一行的位置 ----
  const atlas = readRect(atlasId, 0, 0, W, H);
  if (!atlas) { send('读回失败'); return; }
  const occ = new Uint8Array(W * H);
  let maxUsedY = -1;
  for (let y = 0; y < H; y++) {
    let hit = false;
    for (let x = 0; x < W; x++) {
      const a = atlas.add((y * W + x) * 4 + 3).readU8() > 8 ? 1 : 0;
      occ[y * W + x] = a;
      if (a) hit = true;
    }
    if (hit) maxUsedY = y;
  }
  send('已用到的最后一行 y=' + maxUsedY + ' / ' + H);

  // 货架式分配：一行一行往下排
  let curX = 0, curY = maxUsedY + 2, rowH = 0;
  function alloc(w, h) {
    if (curX + w > W) { curY += rowH + 1; curX = 0; rowH = 0; }
    if (curY + h > H) return null;
    const slot = [curX, curY];
    curX += w + 1;
    if (h > rowH) rowH = h;
    return slot;
  }

  // ---- 4. 收集现有码位 ----
  const entries = [];
  for (let i = 0; i < count0; i++) entries.push([codesPtr0.add(i * 2).readU16(), recsPtr0.add(i * 8).readPointer()]);

  // ---- 5. 逐字上传 ----
  const have = {};
  for (const [c] of entries) have[c] = 1;
  let added = 0, noSlot = 0;
  for (const g of GLYPHS) {
    if (have[g.code]) continue;
    const slot = alloc(g.w, g.h);
    if (!slot) { noSlot++; continue; }
    const [sx, sy] = slot;
    const buf = gMalloc(g.w * g.h * 4);
    for (let i = 0; i < g.w * g.h; i++) {
      buf.add(i * 4).writeU8(255); buf.add(i * 4 + 1).writeU8(255);
      buf.add(i * 4 + 2).writeU8(255); buf.add(i * 4 + 3).writeU8(g.alpha[i]);
    }
    const pt = Memory.alloc(4);
    glGetIntegerv(0x8069, pt);
    glBindTexture(GL_TEX2D, atlasId);
    glTexSubImage2D(GL_TEX2D, 0, sx, sy, g.w, g.h, 0x1908, 0x1401, buf);
    glBindTexture(GL_TEX2D, pt.readU32());
    const rec = gMalloc(16);
    const vals = [g.dx, g.dy, g.adv, 0, sx, sy, g.w, g.h];
    for (let k = 0; k < 8; k++) rec.add(k * 2).writeS16(vals[k]);
    entries.push([g.code, rec]);
    have[g.code] = 1;
    added++;
  }
  send('上传完成 新增=' + added + ' 无空位=' + noSlot);

  // ---- 6. 重建码表（新容量）----
  entries.sort((a, b) => a[0] - b[0]);
  const newCount = entries.length;
  const newCap = Math.max(newCount + 256, 1024);
  const nCodes = gMalloc(newCap * 2);
  const nRecs = gMalloc(newCap * 8);
  for (let i = 0; i < newCount; i++) {
    nCodes.add(i * 2).writeU16(entries[i][0]);
    nRecs.add(i * 8).writePointer(entries[i][1]);
  }
  for (let i = newCount; i < newCap; i++) {
    nCodes.add(i * 2).writeU16(0xffff);
    nRecs.add(i * 8).writePointer(ptr(0));
  }
  font.add(0x10).writePointer(nCodes);
  font.add(0x08).writeU32(newCount);
  font.add(0x18).writeU32(newCount);
  font.add(0x1c).writeU32(newCap);
  font.add(0x28).writePointer(nRecs);
  font.add(0x30).writeU32(newCount);
  font.add(0x34).writeU32(newCap);
  send('码表重建：' + count0 + ' -> ' + newCount + '（容量 ' + newCap + '）');

  const chk = [];
  for (let i = 0; i < 6; i++) chk.push(nCodes.add(i * 2).readU16().toString(16));
  send('前 6 个码位=' + chk.join(','));
}
setTimeout(() => { send({ done: true }); }, 60000);
"""


def build(charset: str, size: int, rewrite: str) -> str:
    fnt = ImageFont.truetype(TTF, size)
    glyphs = []
    seen = set()
    for ch in charset:
        cp = ord(ch)
        if cp in seen or not (0x20 <= cp <= 0xFFFF):
            continue
        seen.add(cp)
        im = Image.new("L", (size * 2, size * 2), 0)
        ImageDraw.Draw(im).text((size // 2, size // 2), ch, font=fnt, fill=255)
        bb = im.getbbox()
        if not bb:
            continue
        im = im.crop(bb)
        w, h = im.size
        alpha = bytes(im.tobytes())
        adv = max(w + 1, int(size * 0.95))
        glyphs.append((cp, w, h, adv, max(0, 24 - h), 1, alpha))

    blob = bytearray()
    blob += len(glyphs).to_bytes(2, "little")
    for cp, w, h, adv, dy, dx, alpha in glyphs:
        blob += cp.to_bytes(2, "little")
        blob += w.to_bytes(2, "little") + h.to_bytes(2, "little") + adv.to_bytes(2, "little")
        blob += (dy & 0xFFFF).to_bytes(2, "little") + (dx & 0xFFFF).to_bytes(2, "little")
        blob += alpha
    return TEMPLATE % {"blob": blob.hex(), "rewrite": repr(rewrite)}


def main() -> None:
    charset_file = Path(sys.argv[1])
    size = int(sys.argv[2]) if len(sys.argv) > 2 else 22
    out = Path(sys.argv[3] if len(sys.argv) > 3 else "analysis/js/43_bulk.js")
    rewrite = sys.argv[4] if len(sys.argv) > 4 else "中文字体渲染测试"
    charset = charset_file.read_text(encoding="utf-8")
    js = build(charset, size, rewrite)
    out.write_text(js, encoding="utf-8")
    print(f"已生成 {out}  {len(js)/1024/1024:.2f} MB  size={size}")


if __name__ == "__main__":
    main()
