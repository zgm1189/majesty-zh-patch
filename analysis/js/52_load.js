// 纯加载：dlopen APK 内的 libzhfont.so，观察构造函数是否崩
const dlopen = new NativeFunction(Module.findExportByName(null, 'dlopen'), 'pointer', ['pointer', 'int']);
const dlerror = new NativeFunction(Module.findExportByName(null, 'dlerror'), 'pointer', []);
const h = dlopen(Memory.allocUtf8String('libzhfont.so'), 2 /* RTLD_NOW */);
if (h.isNull()) {
  const e = dlerror();
  send('dlopen 失败: ' + (e.isNull() ? '?' : e.readCString()));
} else {
  send('dlopen 成功 handle=' + h);
}
setTimeout(() => { send({ done: true }); }, 3000);
