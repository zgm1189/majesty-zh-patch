// 探针：在字形绘制点查询当前绑定的 GL 纹理与尺寸
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
send('img=' + img);

const getInt = new NativeFunction(Module.findExportByName('libGLESv2.so', 'glGetIntegerv'), 'void', ['int', 'pointer']);
const getTexLevel = new NativeFunction(Module.findExportByName('libGLESv2.so', 'glGetTexLevelParameteriv'), 'void', ['int', 'int', 'int', 'pointer']);
const GL_TEXTURE_BINDING_2D = 0x8069, GL_TEXTURE_2D = 0x0DE1;
const GL_TEXTURE_WIDTH = 0x1000, GL_TEXTURE_HEIGHT = 0x1001, GL_TEXTURE_INTERNAL_FORMAT = 0x1003;

const buf = Memory.alloc(16);
let n = 0;
Interceptor.attach(img.add(CALL_VA), {
  onEnter(args) {
    if (n >= 8) return;
    n++;
    getInt(GL_TEXTURE_BINDING_2D, buf);
    const id = buf.readU32();
    getTexLevel(GL_TEXTURE_2D, 0, GL_TEXTURE_WIDTH, buf);
    const w = buf.readS32();
    getTexLevel(GL_TEXTURE_2D, 0, GL_TEXTURE_HEIGHT, buf);
    const h = buf.readS32();
    getTexLevel(GL_TEXTURE_2D, 0, GL_TEXTURE_INTERNAL_FORMAT, buf);
    const f = buf.readS32();
    send('bound=' + id + ' ' + w + 'x' + h + ' ifmt=0x' + f.toString(16) + ' texobj=' + args[0]);
  }
});
setTimeout(() => { send({ done: true }); }, 6000);
