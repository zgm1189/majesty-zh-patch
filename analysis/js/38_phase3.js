// 阶段3（正式版）：识别字体图集 -> 找空位 -> 上传字形 -> 插入码位 -> 改写可见文本
const STR_VA = 0x45cd90, DRAW_VA = 0x110088;
const MODE = 'magenta';       // 'magenta' | 'glyph'
const TARGET = 0x4e2d;        // 中
const GW = 22, GH = 22;

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
const glDeleteFramebuffers = N('glDeleteFramebuffers', 'void', ['int', 'pointer']);
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
const GL_RGBA = 0x1908, GL_UBYTE = 0x1401, GL_COMPLETE = 0x8CD5;

// 收集帧内绑定过的纹理 id（不暴力扫，避免创建垃圾纹理）
const ids = {};
Interceptor.attach(f('glBindTexture'), {
  onEnter(a) { if (a[0].toInt32() === GL_TEX2D && a[1].toInt32()) ids[a[1].toInt32()] = 1; }
});

let fboId = 0;
function ensureFbo() {
  if (fboId) return fboId;
  const b = Memory.alloc(4);
  glGenFramebuffers(1, b);
  fboId = b.readU32();
  return fboId;
}

function readRect(id, sx, sy, w, h) {
  const pf = Memory.alloc(4), pt = Memory.alloc(4);
  glGetIntegerv(0x8CA6, pf); glGetIntegerv(0x8069, pt);
  glBindFramebuffer(GL_FBO, ensureFbo());
  glBindTexture(GL_TEX2D, id);
  glFramebufferTexture2D(GL_FBO, GL_COLOR0, GL_TEX2D, id, 0);
  let out = null;
  if (glCheckFramebufferStatus(GL_FBO) === GL_COMPLETE) {
    out = Memory.alloc(w * h * 4);
    glReadPixels(sx, sy, w, h, GL_RGBA, GL_UBYTE, out);
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
    if (!tried && frames >= 90 && Object.keys(ids).length >= 4) {
      tried = true;
      try { run(args[0]); targetFont = args[0]; } catch (e) { send('ERR ' + e + '\n' + e.stack); }
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
  const pageW = page.add(0x1c).readFloat(), pageH = page.add(0x20).readFloat();
  send('font=' + font + ' count=' + count + ' cap=' + cap + ' page=' + pageW + 'x' + pageH);

  let probe = null;
  for (let i = 0; i < Math.min(count, 120); i++) {
    const rp = recsPtr.add(i * 8).readPointer();
    const r = []; for (let k = 0; k < 8; k++) r.push(rp.add(k * 2).readS16());
    const a = r[6] * r[7];
    if (!probe || a > probe.a) probe = { i: i, r: r, a: a };
  }
  send('probe rec=' + probe.r.join(','));

  const cands = [];
  for (const k of Object.keys(ids)) {
    const id = parseInt(k, 10);
    glBindTexture(GL_TEX2D, id);
    const b = Memory.alloc(4);
    glGetTexLevel(GL_TEX2D, 0, 0x1000, b); const w = b.readS32();
    glGetTexLevel(GL_TEX2D, 0, 0x1001, b); const h = b.readS32();
    if (w === pageW && h === pageH) cands.push(id);
  }
  send('候选 ' + pageW + 'x' + pageH + ': ' + cands.join(','));

  let atlasId = -1, best = -1;
  for (const id of cands) {
    let score = 0;
    for (let i = 0; i < Math.min(count, 40); i++) {
      const rp = recsPtr.add(i * 8).readPointer();
      const r = []; for (let k = 0; k < 8; k++) r.push(rp.add(k * 2).readS16());
      if (r[6] <= 0 || r[7] <= 0) continue;
      const px = readRect(id, r[4], r[5], r[6], r[7]);
      if (px) score += inkOf(px, r[6] * r[7]) / (r[6] * r[7]);
    }
    send('  id=' + id + ' 墨迹分=' + score.toFixed(2));
    if (score > best) { best = score; atlasId = id; }
  }
  send('atlas id=' + atlasId);
  if (atlasId < 0) return;

  const W = pageW | 0, H = pageH | 0;
  const atlas = readRect(atlasId, 0, 0, W, H);
  if (!atlas) { send('读回失败'); return; }

  const rowFree = [];
  for (let y = 0; y < H; y++) {
    let hit = false;
    for (let x = 0; x < W; x++) if (atlas.add((y * W + x) * 4 + 3).readU8() > 8) { hit = true; break; }
    rowFree.push(!hit);
  }
  let px = -1, py = -1;
  for (let y = H - GH; y >= 0 && px < 0; y--) {
    let ok = true;
    for (let k = 0; k < GH && ok; k++) if (!rowFree[y + k]) ok = false;
    if (!ok) continue;
    for (let x = 0; x + GW <= W; x++) {
      let good = true;
      for (let yy = y; yy < y + GH && good; yy++) {
        for (let xx = x; xx < x + GW; xx++) {
          if (atlas.add((yy * W + xx) * 4 + 3).readU8() > 8) { good = false; break; }
        }
      }
      if (good) { px = x; py = y; break; }
    }
  }
  if (px < 0) { send('没有 ' + GW + 'x' + GH + ' 空位'); return; }
  send('空位 (' + px + ',' + py + ')');

  const buf = gMalloc(GW * GH * 4);
  for (let y = 0; y < GH; y++) {
    for (let x = 0; x < GW; x++) {
      const o = (y * GW + x) * 4;
      if (MODE === 'magenta') {
        buf.add(o).writeU8(255); buf.add(o + 1).writeU8(0);
        buf.add(o + 2).writeU8(255); buf.add(o + 3).writeU8(255);
      } else {
        buf.add(o).writeU8(255); buf.add(o + 1).writeU8(255);
        buf.add(o + 2).writeU8(255); buf.add(o + 3).writeU8(0);
      }
    }
  }
  const pf = Memory.alloc(4), pt = Memory.alloc(4);
  glGetIntegerv(0x8CA6, pf); glGetIntegerv(0x8069, pt);
  glBindTexture(GL_TEX2D, atlasId);
  glTexSubImage2D(GL_TEX2D, 0, px, py, GW, GH, GL_RGBA, GL_UBYTE, buf);
  send('上传 err=0x' + glGetError().toString(16));
  glBindTexture(GL_TEX2D, pt.readU32());
  const chk = readRect(atlasId, px, py, GW, GH);
  send('回读 ink=' + (chk ? inkOf(chk, GW * GH) : -1) + '/' + (GW * GH));

  let ins = count;
  for (let i = 0; i < count; i++) if (codesPtr.add(i * 2).readU16() > TARGET) { ins = i; break; }
  if (count >= cap) { send('码表已满'); return; }
  for (let i = count; i > ins; i--) {
    codesPtr.add(i * 2).writeU16(codesPtr.add((i - 1) * 2).readU16());
    recsPtr.add(i * 8).writePointer(recsPtr.add((i - 1) * 8).readPointer());
  }
  codesPtr.add(ins * 2).writeU16(TARGET);
  const newRec = gMalloc(16);
  const vals = [1, 3, GW + 1, 0, px, py, GW, GH];
  for (let k = 0; k < 8; k++) newRec.add(k * 2).writeS16(vals[k]);
  recsPtr.add(ins * 8).writePointer(newRec);
  font.add(0x08).writeU32(count + 1);
  font.add(0x18).writeU32(count + 1);
  font.add(0x30).writeU32(count + 1);
  const chkCodes = [];
  for (let i = Math.max(0, ins - 2); i <= ins + 2; i++) chkCodes.push(codesPtr.add(i * 2).readU16().toString(16));
  send('插入 @' + ins + ' 附近码表=' + chkCodes.join(',') + ' count ' + count + '->' + (count + 1));
}
setTimeout(() => { send({ done: true }); }, 20000);
