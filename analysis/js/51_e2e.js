// 端到端测试：加载 libzhfont.so，再把内存里的菜单字符串换成中文
const dlopen = new NativeFunction(Module.findExportByName(null, 'dlopen'), 'pointer', ['pointer', 'int']);
const dlerror = new NativeFunction(Module.findExportByName(null, 'dlerror'), 'pointer', []);

const h = dlopen(Memory.allocUtf8String('libzhfont.so'), 2);
if (h.isNull()) {
  const e = dlerror();
  send('dlopen 失败: ' + (e.isNull() ? '?' : e.readCString()));
} else {
  send('dlopen 成功 ' + h);
}

function replaceUtf16(from, to) {
  if (from.length !== to.length) { send('长度不一致'); return 0; }
  const pat = [];
  for (const ch of from) { pat.push(ch.charCodeAt(0).toString(16).padStart(2, '0'), '00'); }
  const ranges = Process.enumerateRanges({ protection: 'rw-', coalesce: true });
  let n = 0;
  for (const r of ranges) {
    if (r.size < 16 || r.size > 0x4000000) continue;
    let hits;
    try { hits = Memory.scanSync(r.base, r.size, pat.join(' ')); } catch (e) { continue; }
    for (const hit of hits) {
      try {
        Memory.protect(hit.address, to.length * 2 + 2, 'rw-');
        for (let i = 0; i < to.length; i++) hit.address.add(i * 2).writeU16(to.charCodeAt(i));
        n++;
      } catch (e) { }
    }
  }
  return n;
}

setTimeout(() => {
  const a = replaceUtf16('CREATE', '创建新的游戏');
  const b = replaceUtf16('PLAYE', '开始游戏吧');
  send('替换 CREATE=' + a + '  PLAYE=' + b);
  send({ done: true });
}, 2500);
