// 从 /data/local/tmp 直接 dlopen（测试是否可迭代）
const dlopen = new NativeFunction(Module.findExportByName(null, 'dlopen'), 'pointer', ['pointer', 'int']);
const dlerror = new NativeFunction(Module.findExportByName(null, 'dlerror'), 'pointer', []);
const h = dlopen(Memory.allocUtf8String('/data/local/tmp/zh2.so'), 2);
if (h.isNull()) {
  const e = dlerror();
  send('dlopen 失败: ' + (e.isNull() ? '?' : e.readCString()));
} else {
  send('dlopen 成功 ' + h);
}
setTimeout(() => { send({ done: true }); }, 3000);
