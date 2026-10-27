// 阶段3：正确识别图集 -> 找空位 -> 上传字形 -> 插入码位 -> 改写可见文本
const STR_VA = 0x45cd90, DRAW_VA = 0x110088;
const MODE = 'magenta';       // 'magenta' | 'glyph'
const TARGET = 0x4e2d;        // 中

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

function inkOf(px, n) {
  let c = 0;
  for (let i = 0; i < n; i++) if (px.add(i * 4 + 3).readU8() > 8) c++;
  return c;
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
    if (len <= 0 || len > 40) return;
    try {
      const s = text.readUtf16String(len);
      if (!/^[A-Za-z]+$/.test(s)) return;
      Memory.protect(text, (len + 1) * 2, 'rw-');
      for (let i = 0; i < len; i++) text.add(i * 2).writeU16(TARGET);
    } catch (e) { }
  }
});

function run(font) {
  const count = font.add(0x08).readU32();
  const cap = font.add(0x1c).readU32();
  const codesPtr = font.add(0x10).readPointer();
  const recsPtr = font.add(0x28).readPointer();
  const page = font.add(0x40).readPointer().readPointer();
  const pageW = page.add(0x1c).readFloat() | 0, pageH = page.add(0x20).readFloat() | 0;
  send('font=' + font + ' count=' + count + ' cap=' + cap + ' page=' + pageW + 'x' + pageH);

  // 取前 60 条可用记录
  const glyphs = [];
  for (let i = 0; i < count && glyphs.length < 60; i++) {
    const rp = recsPtr.add(i * 8).readPointer();
    if (rp.isNull()) continue;
    const r = []; for (let k = 0; k < 8; k++) r.push(rp.add(k * 2).readS16());
    if (r[6] > 2 && r[7] > 5 && r[4] >= 0 && r[5] >= 0) glyphs.push(r);
  }
  send('可用记录 ' + glyphs.length + ' 条');

  // 枚举所有 2D 纹理，按「命中率」识别图集
  const cands = [];
  for (let id = 1; id <= 200; id++) {
    const b = Memory.alloc(4);
    glBindTexture(GL_TEX2D, id);
    glGetTexLevel(GL_TEX2D, 0, 0x1000, b); const w = b.readS32();
    if (w !== pageW) continue;
    glGetTexLevel(GL_TEX2D, 0, 0x1001, b);
    if (b.readS32() === pageH) cands.push(id);
  }
  send('候选 ' + pageW + 'x' + pageH + ': ' + cands.join(','));

  let atlasId = -1, bestHits = -1;
  for (const id of cands) {
    let hits = 0;
    for (const r of glyphs) {
      const px = readRect(id, r[4], r[5], r[6], r[7]);
      if (!px) continue;
      if (inkOf(px, r[6] * r[7]) / (r[6] * r[7]) > 0.25) hits++;
    }
    send('  id=' + id + ' 命中 ' + hits + '/' + glyphs.length);
    if (hits > bestHits) { bestHits = hits; atlasId = id; }
  }
  send('atlas id=' + atlasId + ' 命中 ' + bestHits + '/' + glyphs.length);
  if (atlasId < 0 || bestHits < glyphs.length * 0.5) { send('图集识别不可靠，放弃'); return; }

  const atlas = readRect(atlasId, 0, 0, pageW, pageH);
  if (!atlas) { send('读回失败'); return; }
  const rowFree = [];
  for (let y = 0; y < pageH; y++) {
    let hit = false;
    for (let x = 0; x < pageW; x++) if (atlas.add((y * pageW + x) * 4 + 3).readU8() > 8) { hit = true; break; }
    rowFree.push(!hit);
  }
  // 找最大的空白方块（从 24 递减）
  let gw = 0, px = -1, py = -1;
  for (let s = 24; s >= 10 && px < 0; s--) {
    for (let y = pageH - s; y >= 0 && px < 0; y--) {
      let ok = true;
      for (let k = 0; k < s && ok; k++) if (!rowFree[y + k]) ok = false;
      if (!ok) continue;
      for (let x = 0; x + s <= pageW; x++) {
        let good = true;
        for (let yy = y; yy < y + s && good; yy++) {
          for (let xx = x; xx < x + s; xx++) {
            if (atlas.add((yy * pageW + xx) * 4 + 3).readU8() > 8) { good = false; break; }
          }
        }
        if (good) { px = x; py = y; gw = s; break; }
      }
    }
  }
  if (px < 0) { send('没有 >=10x10 的空位'); return; }
  const GH = gw;
  send('空位 (' + px + ',' + py + ') ' + gw + 'x' + GH);

  const buf = gMalloc(gw * GH * 4);
  for (let i = 0; i < gw * GH; i++) {
    if (MODE === 'magenta') {
      buf.add(i * 4).writeU8(255); buf.add(i * 4 + 1).writeU8(0);
      buf.add(i * 4 + 2).writeU8(255); buf.add(i * 4 + 3).writeU8(255);
    } else {
      buf.add(i * 4).writeU8(255); buf.add(i * 4 + 1).writeU8(255);
      buf.add(i * 4 + 2).writeU8(255); buf.add(i * 4 + 3).writeU8(0);
    }
  }
  const pt = Memory.alloc(4);
  glGetIntegerv(0x8069, pt);
  glBindTexture(GL_TEX2D, atlasId);
  glTexSubImage2D(GL_TEX2D, 0, px, py, gw, GH, 0x1908, 0x1401, buf);
  send('上传 err=0x' + glGetError().toString(16));
  glBindTexture(GL_TEX2D, pt.readU32());

  let ins = count;
  for (let i = 0; i < count; i++) if (codesPtr.add(i * 2).readU16() > TARGET) { ins = i; break; }
  if (count >= cap) { send('码表已满'); return; }
  for (let i = count; i > ins; i--) {
    codesPtr.add(i * 2).writeU16(codesPtr.add((i - 1) * 2).readU16());
    recsPtr.add(i * 8).writePointer(recsPtr.add((i - 1) * 8).readPointer());
  }
  codesPtr.add(ins * 2).writeU16(TARGET);
  const newRec = gMalloc(16);
  const vals = [1, 3, gw + 1, 0, px, py, gw, GH];
  for (let k = 0; k < 8; k++) newRec.add(k * 2).writeS16(vals[k]);
  recsPtr.add(ins * 8).writePointer(newRec);
  font.add(0x08).writeU32(count + 1);
  font.add(0x18).writeU32(count + 1);
  font.add(0x30).writeU32(count + 1);
  const chk = [];
  for (let i = Math.max(0, ins - 2); i <= Math.min(count, ins + 2); i++) chk.push(codesPtr.add(i * 2).readU16().toString(16));
  send('插入 @' + ins + ' 码表=' + chk.join(',') + ' count ' + count + '->' + (count + 1));
}
setTimeout(() => { send({ done: true }); }, 20000);
