// 实验：把 'P' 的字形格子涂成品红，看会不会被引擎覆盖回去
const STR_VA = 0x45cd90, DRAW_VA = 0x110088;
const CH = 0x50;   // 'P'
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
const glTexSubImage2D = N('glTexSubImage2D', 'void', ['int', 'int', 'int', 'int', 'int', 'int', 'uint', 'uint', 'pointer']);
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

let phase = 0, frames = 0, atlasId = -1, rect = null, font0 = null;
const gMalloc = new NativeFunction(Module.findExportByName(null, 'malloc'), 'pointer', ['ulong']);

Interceptor.attach(img.add(DRAW_VA), {
  onEnter(args) {
    frames++;
    const font = args[0];
    if (!font0) font0 = font;
    if (!font.equals(font0)) return;
    if (frames === 40) {
      const count = font.add(0x08).readU32();
      const codes = font.add(0x10).readPointer();
      const recs = font.add(0x28).readPointer();
      let idx = -1;
      for (let i = 0; i < count; i++) if (codes.add(i * 2).readU16() === CH) { idx = i; break; }
      if (idx < 0) { send('找不到 P'); return; }
      const rp = recs.add(idx * 8).readPointer();
      rect = []; for (let k = 0; k < 8; k++) rect.push(rp.add(k * 2).readS16());
      send('P 记录=' + rect.join(','));
      // 找图集：对两个候选各读该格，比墨迹
      let best = -1;
      for (const id of [8, 17]) {
        const px = readRect(id, rect[4], rect[5], rect[6], rect[7]);
        let ink = 0;
        if (px) for (let i = 0; i < rect[6] * rect[7]; i++) if (px.add(i * 4 + 3).readU8() > 8) ink++;
        send('  id=' + id + ' ink=' + ink + '/' + (rect[6] * rect[7]));
        if (ink > best) { best = ink; atlasId = id; }
      }
      send('用 id=' + atlasId);
      // 涂品红
      const n = rect[6] * rect[7] * 4;
      const buf = gMalloc(n);
      for (let i = 0; i < rect[6] * rect[7]; i++) {
        buf.add(i * 4).writeU8(255); buf.add(i * 4 + 1).writeU8(0);
        buf.add(i * 4 + 2).writeU8(255); buf.add(i * 4 + 3).writeU8(255);
      }
      const pt = Memory.alloc(4);
      glGetIntegerv(0x8069, pt);
      glBindTexture(GL_TEX2D, atlasId);
      glTexSubImage2D(GL_TEX2D, 0, rect[4], rect[5], rect[6], rect[7], 0x1908, 0x1401, buf);
      glBindTexture(GL_TEX2D, pt.readU32());
      send('已涂品红 err=0x' + glGetError().toString(16));
      phase = 1;
    } else if (phase === 1 && frames === 200) {
      phase = 2;
      const px = readRect(atlasId, rect[4], rect[5], rect[6], rect[7]);
      let mag = 0, tot = rect[6] * rect[7];
      if (px) for (let i = 0; i < tot; i++) {
        if (px.add(i * 4).readU8() > 200 && px.add(i * 4 + 1).readU8() < 60) mag++;
      }
      send('160 帧后回读：品红像素 ' + mag + '/' + tot);
    }
  }
});
setTimeout(() => { send({ done: true }); }, 15000);
