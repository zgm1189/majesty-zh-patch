// 启动期探针：保存疑似字体图集的纹理数据
const f = (n) => Module.findExportByName('libGLESv2.so', n);
const glGetIntegerv = new NativeFunction(f('glGetIntegerv'), 'void', ['int', 'pointer']);
const b = Memory.alloc(4);
let saved = 0;
Interceptor.attach(f('glTexImage2D'), {
  onEnter(a) {
    const w = a[3].toInt32(), h = a[4].toInt32(), type = a[7].toInt32(), px = a[8];
    const bpp = (type === 0x8033 || type === 0x8034 || type === 0x8363) ? 2 : 4;
    if (!px.isNull() && (w === 512 || w === 256) && h >= 128 && saved < 12) {
      glGetIntegerv(0x8069, b);
      const id = b.readU32();
      saved++;
      send('save id=' + id + ' ' + w + 'x' + h + ' type=0x' + type.toString(16));
      send({ file: 'U' + id + '_' + w + 'x' + h + '_t' + type.toString(16) + '.raw' }, px.readByteArray(w * h * bpp));
    }
  }
});
setTimeout(() => { send({ done: true }); }, 25000);
