// 给 CIwGxFont vtable 的每个槽位挂钩，看哪个函数拿到的是“字符码”
const STR_VA = 0x45cd90;
const VT_VA = 0x51fd78;
const SLOTS = 18;

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
send('镜像 = ' + img);
const vt = img.add(VT_VA);

const stats = {};
const listeners = [];
for (let i = 0; i < SLOTS; i++) {
  const fn = vt.add(i * 8).readPointer();
  if (fn.isNull()) continue;
  stats[i] = { n: 0, args: [] };
  try {
    listeners.push(Interceptor.attach(fn, {
      onEnter(args) {
        const s = stats[i];
        s.n++;
        if (s.args.length < 6) {
          s.args.push([args[0].toString(), args[1].toString(), args[2].toString()]);
        }
      }
    }));
  } catch (e) {
    send(`槽 ${i} hook 失败: ${e.message}`);
  }
}
send(`已挂钩 ${listeners.length} 个槽位，采样 3 秒...`);

setTimeout(() => {
  for (const l of listeners) l.detach();
  for (const k of Object.keys(stats)) {
    const s = stats[k];
    if (!s.n) continue;
    send(`槽 ${k}: ${s.n} 次`);
    for (const a of s.args) send(`    arg0=${a[0]} arg1=${a[1]} arg2=${a[2]}`);
  }
  send({ done: true });
}, 3000);
