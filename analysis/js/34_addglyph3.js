// 阶段3：往引擎字体图集里塞一个新字形（图集已满时先扩容）
const STR_VA = 0x45cd90, DRAW_VA = 0x110088;
const MODE = 'magenta';          // 'magenta' | 'glyph'
const TARGET = 0x4e2d;           // 中
const GROW_W = 1024, GROW_H = 512;

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
const glTexImage2D = N('glTexImage2D', 'void', ['int', 'int', 'int', 'int', 'int', 'int', 'uint', 'uint', 'pointer']);
const glTexSubImage2D = N('glTexSubImage2D', 'void', ['int', 'int', 'int', 'int', 'int', 'int', 'uint', 'uint', 'pointer']);
const glGetTexLevel = N('glGetTexLevelParameteriv', 'void', ['int', 'int', 'int', 'pointer']);
const glGetError = N('glGetError', 'uint', []);
const GL_TEX2D = 0x0DE1, GL_FBO = 0x8D40, GL_COLOR0 = 0x8CE0;
const GL_FBO_BIND = 0x8CA6, GL_TEX_BIND = 0x8069;
const GL_RGBA = 0x1908, GL_UBYTE = 0x1401, GL_COMPLETE = 0x8CD5;

function withFbo(fn) {
  const prevFbo = Memory.alloc(4), prevTex = Memory.alloc(4), fbo = Memory.alloc(4);
  glGetIntegerv(GL_FBO_BIND, prevFbo);
  glGetIntegerv(GL_TEX_BIND, prevTex);
  glGenFramebuffers(1, fbo);
  glBindFramebuffer(GL_FBO, fbo.readU32());
  const r = fn();
  glBindFramebuffer(GL_FBO, prevFbo.readU32());
  glBindTexture(GL_TEX2D, prevTex.readU32());
  return r;
}

function texSize(id) {
  const b = Memory.alloc(4);
  glBindTexture(GL_TEX2D, id);
  glGetTexLevel(GL_TEX2D, 0, 0x1000, b); const w = b.readS32();
  glGetTexLevel(GL_TEX2D, 0, 0x1001, b); const h = b.readS32();
  return [w, h];
}

function readRect(id, sx, sy, w, h) {
  return withFbo(() => {
    glBindTexture(GL_TEX2D, id);
    glFramebufferTexture2D(GL_FBO, GL_COLOR0, GL_TEX2D, id, 0);
    if (glCheckFramebufferStatus(GL_FBO) !== GL_COMPLETE) return null;
    const px = Memory.alloc(w * h * 4);
    glReadPixels(sx, sy, w, h, GL_RGBA, GL_UBYTE, px);
    return px;
  });
}

function inkOf(px, n) {
  let c = 0;
  for (let i = 0; i < n; i++) if (px.add(i * 4 + 3).readU8() > 8) c++;
  return c;
}

let setup = false;
Interceptor.attach(img.add(DRAW_VA), {
  onEnter(args) {
    if (!setup) {
      setup = true;
      try { run(args[0]); } catch (e) { send('ERR ' + e + '\n' + e.stack); }
    }
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
  send('probe idx=' + probe.i + ' rec=' + probe.r.join(','));

  const cands = [];
  for (let id = 1; id <= 160; id++) {
    const sz = texSize(id);
    if (sz[0] === pageW && sz[1] === pageH) cands.push(id);
  }
  send('候选 ' + pageW + 'x' + pageH + ': ' + cands.join(','));

  // 优先用页对象里出现过的 id
  let atlasId = -1;
  const pageBytes = [];
  for (let o = 0; o < 0x300; o += 4) pageBytes.push(page.add(o).readU32());
  for (const id of cands) {
    if (pageBytes.indexOf(id) >= 0) { atlasId = id; send('页对象里命中 id=' + id); break; }
  }
  // 否则用墨迹打分
  if (atlasId < 0) {
    let best = -1;
    for (const id of cands) {
      let score = 0;
      for (let i = 0; i < Math.min(count, 40); i++) {
        const rp = recsPtr.add(i * 8).readPointer();
        const r = []; for (let k = 0; k < 8; k++) r.push(rp.add(k * 2).readS16());
        if (r[6] <= 0 || r[7] <= 0) continue;
        const px = readRect(id, r[4], r[5], r[6], r[7]);
        if (!px) continue;
        score += inkOf(px, r[6] * r[7]) / (r[6] * r[7]);
      }
      send('  id=' + id + ' 墨迹分=' + score.toFixed(2));
      if (score > best) { best = score; atlasId = id; }
    }
  }
  send('atlas id=' + atlasId);
  if (atlasId < 0) return;

  const W = pageW | 0, H = pageH | 0;
  const atlas = readRect(atlasId, 0, 0, W, H);
  if (!atlas) { send('读回失败'); return; }
  let maxInkY = -1;
  for (let y = H - 1; y >= 0; y--) {
    let hit = false;
    for (let x = 0; x < W; x++) if (atlas.add((y * W + x) * 4 + 3).readU8() > 8) { hit = true; break; }
    if (hit) { maxInkY = y; break; }
  }
  send('最下有像素的行 y=' + maxInkY + ' / ' + H);

  const gw = 22, gh = 22;
  // 找一块 gw x gh 的空白矩形（行优先，从下往上找，避开密集区）
  function freeAt(ox, oy) {
    for (let y = oy; y < oy + gh; y++) {
      for (let x = ox; x < ox + gw; x++) {
        if (atlas.add((y * W + x) * 4 + 3).readU8() > 8) return false;
      }
    }
    return true;
  }
  let px = -1, py = -1;
  for (let y = H - gh; y >= 0 && px < 0; y--) {
    for (let x = 0; x + gw <= W; x++) {
      if (freeAt(x, y)) { px = x; py = y; break; }
    }
  }
  if (px < 0) { send('图集没有 ' + gw + 'x' + gh + ' 的空位'); return; }
  send('空位 (' + px + ',' + py + ')');

  const buf = Memory.alloc(gw * gh * 4);
  for (let y = 0; y < gh; y++) {
    for (let x = 0; x < gw; x++) {
      const o = (y * gw + x) * 4;
      if (MODE === 'magenta') {
        buf.add(o).writeU8(255); buf.add(o + 1).writeU8(0);
        buf.add(o + 2).writeU8(255); buf.add(o + 3).writeU8(255);
      } else {
        buf.add(o).writeU8(255); buf.add(o + 1).writeU8(255);
        buf.add(o + 2).writeU8(255); buf.add(o + 3).writeU8(0);
      }
    }
  }
  withFbo(() => {
    glBindTexture(GL_TEX2D, atlasId);
    glTexSubImage2D(GL_TEX2D, 0, px, py, gw, gh, GL_RGBA, GL_UBYTE, buf);
  });
  send('上传完成 err=0x' + glGetError().toString(16));
  const chk = readRect(atlasId, px, py, gw, gh);
  send('回读校验 ink=' + (chk ? inkOf(chk, gw * gh) : -1) + '/' + (gw * gh));

  let ins = count;
  for (let i = 0; i < count; i++) if (codesPtr.add(i * 2).readU16() > TARGET) { ins = i; break; }
  send('插入位置 ' + ins);
  if (count >= cap) { send('码表已满，需要扩容'); return; }
  for (let i = count; i > ins; i--) {
    codesPtr.add(i * 2).writeU16(codesPtr.add((i - 1) * 2).readU16());
    recsPtr.add(i * 8).writePointer(recsPtr.add((i - 1) * 8).readPointer());
  }
  codesPtr.add(ins * 2).writeU16(TARGET);
  // 用游戏进程的 malloc，脚本卸载后内存依然有效
  const gMalloc = new NativeFunction(Module.findExportByName(null, 'malloc'), 'pointer', ['ulong']);
  const newRec = gMalloc(16);
  const vals = [1, 3, gw + 1, 0, px, py, gw, gh];
  for (let k = 0; k < 8; k++) newRec.add(k * 2).writeS16(vals[k]);
  recsPtr.add(ins * 8).writePointer(newRec);
  send('新记录指针=' + newRec + ' 内容=' + (() => { const v = []; for (let k = 0; k < 8; k++) v.push(newRec.add(k * 2).readS16()); return v.join(','); })());
  font.add(0x08).writeU32(count + 1);
  font.add(0x18).writeU32(count + 1);
  font.add(0x30).writeU32(count + 1);
  send('已插入 U+' + TARGET.toString(16) + ' count ' + count + '->' + (count + 1) + ' rec=' + vals.join(','));
}
setTimeout(() => { send({ done: true }); }, 12000);
