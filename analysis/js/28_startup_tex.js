// 启动期探针：抓住引擎所有的纹理上传
const f = (n) => Module.findExportByName('libGLESv2.so', n);
if (!f('glTexImage2D')) { send('no gles'); send({ done: true }); }
else {
  const glGetIntegerv = new NativeFunction(f('glGetIntegerv'), 'void', ['int', 'pointer']);
  const b = Memory.alloc(4);
  let n = 0;
  Interceptor.attach(f('glTexImage2D'), {
    onEnter(a) {
      if (n >= 200) return;
      n++;
      glGetIntegerv(0x8069, b);
      send('TexImage2D id=' + b.readU32() + ' lvl=' + a[1].toInt32() +
        ' ifmt=0x' + a[2].toInt32().toString(16) + ' ' + a[3].toInt32() + 'x' + a[4].toInt32() +
        ' fmt=0x' + a[6].toInt32().toString(16) + ' type=0x' + a[7].toInt32().toString(16) +
        ' px=' + a[8]);
    }
  });
  Interceptor.attach(f('glTexSubImage2D'), {
    onEnter(a) {
      if (n >= 400) return;
      n++;
      glGetIntegerv(0x8069, b);
      send('SubImage2D id=' + b.readU32() + ' lvl=' + a[1].toInt32() +
        ' x=' + a[2].toInt32() + ' y=' + a[3].toInt32() + ' ' + a[4].toInt32() + 'x' + a[5].toInt32() +
        ' fmt=0x' + a[6].toInt32().toString(16) + ' px=' + a[8]);
    }
  });
  setTimeout(() => { send({ done: true }); }, 30000);
}
