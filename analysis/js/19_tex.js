// 探针：抓引擎的纹理上传，看字体图集的真实尺寸
const lib = Process.findModuleByName('libGLESv2.so');
send('libGLESv2=' + lib);
if (lib) {
  const p = Module.findExportByName('libGLESv2.so', 'glTexImage2D');
  send('glTexImage2D=' + p);
  let n = 0;
  Interceptor.attach(p, {
    onEnter(args) {
      if (n >= 60) return;
      n++;
      const target = args[0].toInt32();
      const level = args[1].toInt32();
      const ifmt = args[2].toInt32();
      const w = args[3].toInt32(), h = args[4].toInt32();
      const fmt = args[6].toInt32(), type = args[7].toInt32();
      const px = args[8];
      send('TexImage2D tgt=' + target + ' lvl=' + level + ' ifmt=' + ifmt +
        ' ' + w + 'x' + h + ' fmt=' + fmt + ' type=' + type + ' px=' + px);
    }
  });
}
setTimeout(() => { send({ done: true }); }, 7000);
