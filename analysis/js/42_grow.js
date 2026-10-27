// 关键实验：把图集扩到 1024x1024，看原有文字是否仍然正常
const STR_VA = 0x45cd90, DRAW_VA = 0x110088;
const NEW_W = 1024, NEW_H = 1024;

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
const glGetTexLevel = N('glGetTexLevelParameteriv', 'void', ['int', 'int', 'int', 'pointer']);
const glGetError = N('glGetError', 'uint', []);
const GL_TEX2D = 0x0DE1, GL_FBO = 0x8D40, GL_COLOR0 = 0x8CE0;
const gMalloc = new NativeFunction(Module.findExportByName(null, 'malloc'), 'pointer', ['ulong']);

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

let frames = 0, done = false;
Interceptor.attach(img.add(DRAW_VA), {
  onEnter(args) {
    if (done) return;
    frames++;
    if (frames < 40) return;
    done = true;
    const font = args[0];
    const count = font.add(0x08).readU32();
    const recs = font.add(0x28).readPointer();
    const page = font.add(0x40).readPointer().readPointer();
    const W = page.add(0x1c).readFloat() | 0, H = page.add(0x20).readFloat() | 0;
    send('font=' + font + ' count=' + count + ' page=' + W + 'x' + H);

    const glyphs = [];
    for (let i = 0; i < count && glyphs.length < 60; i++) {
      const rp = recs.add(i * 8).readPointer();
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
    let atlasId = -1, best = -1;
    for (const id of cands) {
      let hits = 0;
      for (const r of glyphs) {
        const px = readRect(id, r[4], r[5], r[6], r[7]);
        if (!px) continue;
        let ink = 0;
        for (let i = 0; i < r[6] * r[7]; i++) if (px.add(i * 4 + 3).readU8() > 8) ink++;
        if (ink / (r[6] * r[7]) > 0.25) hits++;
      }
      if (hits > best) { best = hits; atlasId = id; }
    }
    send('atlas id=' + atlasId + ' 命中=' + best + '/' + glyphs.length);
    if (atlasId < 0) return;

    const old = readRect(atlasId, 0, 0, W, H);
    if (!old) { send('读回失败'); return; }
    // 拷进新尺寸缓冲
    const big = gMalloc(NEW_W * NEW_H * 4);
    for (let i = 0; i < NEW_W * NEW_H; i++) big.add(i * 4 + 3).writeU8(0);
    for (let y = 0; y < H; y++) {
      for (let x = 0; x < W; x++) {
        const s = (y * W + x) * 4, d = (y * NEW_W + x) * 4;
        big.add(d).writeU8(old.add(s).readU8());
        big.add(d + 1).writeU8(old.add(s + 1).readU8());
        big.add(d + 2).writeU8(old.add(s + 2).readU8());
        big.add(d + 3).writeU8(old.add(s + 3).readU8());
      }
    }
    const pt = Memory.alloc(4);
    glGetIntegerv(0x8069, pt);
    glBindTexture(GL_TEX2D, atlasId);
    glTexImage2D(GL_TEX2D, 0, 0x1908, NEW_W, NEW_H, 0, 0x1908, 0x1401, big);
    send('扩容 err=0x' + glGetError().toString(16));
    glBindTexture(GL_TEX2D, pt.readU32());
    const b2 = Memory.alloc(4);
    glBindTexture(GL_TEX2D, atlasId);
    glGetTexLevel(GL_TEX2D, 0, 0x1000, b2); const nw = b2.readS32();
    glGetTexLevel(GL_TEX2D, 0, 0x1001, b2);
    send('新尺寸=' + nw + 'x' + b2.readS32());
    page.add(0x1c).writeFloat(NEW_W); page.add(0x20).writeFloat(NEW_H);
    page.add(0x24).writeFloat(NEW_W); page.add(0x28).writeFloat(NEW_H);
    send('page 已更新为 ' + page.add(0x1c).readFloat() + 'x' + page.add(0x20).readFloat());
  }
});
setTimeout(() => { send({ done: true }); }, 12000);
