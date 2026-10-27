// 探针：用 FBO 把候选纹理读回来，确认哪一张是字体图集
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
const glGenFramebuffers = new NativeFunction(f('glGenFramebuffers'), 'void', ['int', 'pointer']);
const glBindFramebuffer = new NativeFunction(f('glBindFramebuffer'), 'void', ['int', 'uint']);
const glFramebufferTexture2D = new NativeFunction(f('glFramebufferTexture2D'), 'void', ['int', 'int', 'int', 'uint', 'int']);
const glCheckFramebufferStatus = new NativeFunction(f('glCheckFramebufferStatus'), 'uint', ['int']);
const glGetIntegerv = new NativeFunction(f('glGetIntegerv'), 'void', ['int', 'pointer']);
const glBindTexture = new NativeFunction(f('glBindTexture'), 'void', ['int', 'uint']);
const glReadPixels = new NativeFunction(f('glReadPixels'), 'void', ['int', 'int', 'int', 'int', 'uint', 'uint', 'pointer']);
const glGetError = new NativeFunction(f('glGetError'), 'uint', []);
const glFinish = new NativeFunction(f('glFinish'), 'void', []);

const GL_TEXTURE_2D = 0x0DE1, GL_FRAMEBUFFER = 0x8D40, GL_COLOR_ATTACHMENT0 = 0x8CE0;
const GL_FRAMEBUFFER_BINDING = 0x8CA6, GL_TEXTURE_BINDING_2D = 0x8069;
const GL_RGBA = 0x1908, GL_UNSIGNED_BYTE = 0x1401;

let done = false;
Interceptor.attach(img.add(CALL_VA), {
  onEnter(args) {
    if (done) return;
    done = true;
    const W = 512, H = 256, bytes = W * H * 4;
    const prevFbo = Memory.alloc(4), prevTex = Memory.alloc(4), fbo = Memory.alloc(4);
    const px = Memory.alloc(bytes);
    glGetIntegerv(GL_FRAMEBUFFER_BINDING, prevFbo);
    glGetIntegerv(GL_TEXTURE_BINDING_2D, prevTex);
    glGenFramebuffers(1, fbo);
    glBindFramebuffer(GL_FRAMEBUFFER, fbo.readU32());
    for (const id of [41, 42]) {
      glBindTexture(GL_TEXTURE_2D, id);
      glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, id, 0);
      const st = glCheckFramebufferStatus(GL_FRAMEBUFFER);
      if (st !== 0x8CD5) { send('id=' + id + ' fbo incomplete 0x' + st.toString(16)); continue; }
      glReadPixels(0, 0, W, H, GL_RGBA, GL_UNSIGNED_BYTE, px);
      const err = glGetError();
      send('id=' + id + ' readback err=0x' + err.toString(16), px.readByteArray(bytes));
      send({ file: 'tex_' + id + '.rgba' }, px.readByteArray(bytes));
    }
    glBindFramebuffer(GL_FRAMEBUFFER, prevFbo.readU32());
    glBindTexture(GL_TEXTURE_2D, prevTex.readU32());
  }
});
setTimeout(() => { send({ done: true }); }, 5000);
