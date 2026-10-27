// 用 Frida 把 libzhfont.so 载进来（只是测试手段，正式版不需要 Frida）
const dlopen = new NativeFunction(Module.findExportByName(null, 'dlopen'), 'pointer', ['pointer', 'int']);
const dlerror = new NativeFunction(Module.findExportByName(null, 'dlerror'), 'pointer', []);
const path = Memory.allocUtf8String('/data/local/tmp/libzhfont.so');
const h = dlopen(path, 2 /* RTLD_NOW */);
if (h.isNull()) {
  const e = dlerror();
  send('dlopen 失败: ' + (e.isNull() ? '?' : e.readCString()));
} else {
  send('dlopen 成功 handle=' + h);
}
setTimeout(() => { send({ done: true }); }, 3000);
