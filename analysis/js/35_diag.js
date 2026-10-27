// 诊断：码位是否插入成功、上传是否还在
const STR_VA = 0x45cd90, DRAW_VA = 0x110088;
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
const glGetTexLevel = N('glGetTexLevelParameteriv', 'void', ['int', 'int', 'int', 'pointer']);
const GL_TEX2D = 0x0DE1, GL_FBO = 0x8D40, GL_COLOR0 = 0x8CE0;

function withFbo(fn) {
  const pf = Memory.alloc(4), pt = Memory.alloc(4), fb = Memory.alloc(4);
  glGetIntegerv(0x8CA6, pf); glGetIntegerv(0x8069, pt);
  glGenFramebuffers(1, fb); glBindFramebuffer(GL_FBO, fb.readU32());
  const r = fn();
  glBindFramebuffer(GL_FBO, pf.readU32()); glBindTexture(GL_TEX2D, pt.readU32());
  return r;
}

let done = false;
Interceptor.attach(img.add(DRAW_VA), {
  onEnter(args) {
    if (done) return;
    done = true;
    const font = args[0];
    const count = font.add(0x08).readU32();
    const codes = font.add(0x10).readPointer();
    const recs = font.add(0x28).readPointer();
    send('font=' + font + ' count=' + count);
    // 找 0x4e2d
    let idx = -1;
    for (let i = 0; i < count; i++) if (codes.add(i * 2).readU16() === 0x4e2d) { idx = i; break; }
    send('0x4e2d 下标=' + idx);
    if (idx >= 0) {
      const rp = recs.add(idx * 8).readPointer();
      const v = []; for (let k = 0; k < 8; k++) v.push(rp.add(k * 2).readS16());
      send('  记录=' + v.join(',') + ' 指针=' + rp);
      // 读回那个格子
      const page = font.add(0x40).readPointer().readPointer();
      send('  page w/h=' + page.add(0x1c).readFloat() + '/' + page.add(0x20).readFloat());
      const px = withFbo(() => {
        glBindTexture(GL_TEX2D, 17);
        glFramebufferTexture2D(GL_FBO, GL_COLOR0, GL_TEX2D, 17, 0);
        if (glCheckFramebufferStatus(GL_FBO) !== 0x8CD5) return null;
        const b = Memory.alloc(v[6] * v[7] * 4);
        glReadPixels(v[4], v[5], v[6], v[7], 0x1908, 0x1401, b);
        return b;
      });
      if (px) {
        const c = [];
        for (let k = 0; k < 4; k++) c.push([px.add(k * 4).readU8(), px.add(k * 4 + 1).readU8(), px.add(k * 4 + 2).readU8(), px.add(k * 4 + 3).readU8()].join(','));
        send('  id17 该格前 4 像素=' + c.join(' | '));
      } else send('  id17 FBO 失败');
      // 纹理尺寸
      const b2 = Memory.alloc(4);
      glBindTexture(GL_TEX2D, 17);
      glGetTexLevel(GL_TEX2D, 0, 0x1000, b2);
      const w = b2.readS32();
      glGetTexLevel(GL_TEX2D, 0, 0x1001, b2);
      send('  id17 尺寸=' + w + 'x' + b2.readS32());
    }
    // 顺便打印最后几个码位
    const tail = [];
    for (let i = Math.max(0, count - 8); i < count; i++) tail.push(codes.add(i * 2).readU16().toString(16));
    send('码表末尾=' + tail.join(','));
  }
});
setTimeout(() => { send({ done: true }); }, 4000);
