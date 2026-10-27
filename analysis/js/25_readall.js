// 探针：枚举所有纹理并逐个读回，找出真正的字体图集
const STR_VA = 0x45cd90, CALL_VA = 0x1103f0;
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
const gl = 'libGLESv2.so';
const f = (n) => Module.findExportByName(gl, n);
const N = (n, r, a) => new NativeFunction(f(n), r, a);
const glGenFramebuffers = N('glGenFramebuffers', 'void', ['int', 'pointer']);
const glBindFramebuffer = N('glBindFramebuffer', 'void', ['int', 'uint']);
const glFramebufferTexture2D = N('glFramebufferTexture2D', 'void', ['int', 'int', 'int', 'uint', 'int']);
const glCheckFramebufferStatus = N('glCheckFramebufferStatus', 'uint', ['int']);
const glGetIntegerv = N('glGetIntegerv', 'void', ['int', 'pointer']);
const glBindTexture = N('glBindTexture', 'void', ['int', 'uint']);
const glReadPixels = N('glReadPixels', 'void', ['int', 'int', 'int', 'int', 'uint', 'uint', 'pointer']);
const glGetTexLevel = N('glGetTexLevelParameteriv', 'void', ['int', 'int', 'int', 'pointer']);

const ids = {};
Interceptor.attach(f('glBindTexture'), {
  onEnter(a) { if (a[0].toInt32() === 0x0DE1 && a[1].toInt32()) ids[a[1].toInt32()] = 1; }
});

let phase = 0;
setTimeout(() => { phase = 1; send('ids=' + Object.keys(ids).join(',')); }, 3000);

Interceptor.attach(img.add(CALL_VA), {
  onEnter(a) {
    if (phase !== 1) return;
    phase = 2;
    const b = Memory.alloc(4);
    const prevFbo = Memory.alloc(4), prevTex = Memory.alloc(4), fbo = Memory.alloc(4);
    glGetIntegerv(0x8CA6, prevFbo);
    glGetIntegerv(0x8069, prevTex);
    glGenFramebuffers(1, fbo);
    glBindFramebuffer(0x8D40, fbo.readU32());
    for (const k of Object.keys(ids)) {
      const id = parseInt(k, 10);
      glBindTexture(0x0DE1, id);
      glGetTexLevel(0x0DE1, 0, 0x1000, b); const w = b.readS32();
      glGetTexLevel(0x0DE1, 0, 0x1001, b); const h = b.readS32();
      if (!w || !h || w * h * 4 > 4 * 1024 * 1024) { send('id=' + id + ' skip ' + w + 'x' + h); continue; }
      glFramebufferTexture2D(0x8D40, 0x8CE0, 0x0DE1, id, 0);
      const st = glCheckFramebufferStatus(0x8D40);
      if (st !== 0x8CD5) { send('id=' + id + ' ' + w + 'x' + h + ' fbo=0x' + st.toString(16)); continue; }
      const px = Memory.alloc(w * h * 4);
      glReadPixels(0, 0, w, h, 0x1908, 0x1401, px);
      send('id=' + id + ' ' + w + 'x' + h);
      send({ file: 'T' + id + '_' + w + 'x' + h + '.rgba' }, px.readByteArray(w * h * 4));
    }
    glBindFramebuffer(0x8D40, prevFbo.readU32());
    glBindTexture(0x0DE1, prevTex.readU32());
    send({ done: true });
  }
});
setTimeout(() => { send({ done: true }); }, 20000);
