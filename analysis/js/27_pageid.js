// 探针：把页对象字段与 512x256 纹理 id 对照
const STR_VA = 0x45cd90, CALL_VA = 0x110338;
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
const glGetTexLevel = new NativeFunction(f('glGetTexLevelParameteriv'), 'void', ['int', 'int', 'int', 'pointer']);
const glBindTexture = new NativeFunction(f('glBindTexture'), 'void', ['int', 'uint']);

const ids = {};
Interceptor.attach(f('glBindTexture'), {
  onEnter(a) { if (a[0].toInt32() === 0x0DE1 && a[1].toInt32()) ids[a[1].toInt32()] = 1; }
});

let done = false;
Interceptor.attach(img.add(CALL_VA), {
  onEnter(args) {
    if (done) return;
    done = true;
    const font = this.context.x19;
    const page = font.add(0x40).readPointer().readPointer();
    const u32 = [];
    for (let o = 0; o < 0x80; o += 4) u32.push(o.toString(16) + '=' + page.add(o).readU32());
    send('page=' + page + '\n' + u32.join(' '));
    const b = Memory.alloc(8);
    const found = [];
    for (const k of Object.keys(ids)) {
      const id = parseInt(k, 10);
      glGetTexLevel(0x0DE1, 0, 0x1000, b); const w = b.readS32();
      glGetTexLevel(0x0DE1, 0, 0x1001, b); const h = b.readS32();
      if (w === 512 && h === 256) found.push(id);
    }
    send('512x256 ids = ' + found.join(','));
  }
});
setTimeout(() => { send({ done: true }); }, 6000);
