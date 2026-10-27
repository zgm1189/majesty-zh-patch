// 探针：把「记录原始字节」和「实际绘制参数」配对
const STR_VA = 0x45cd90;
const REC_VA = 0x110338;    // x0 = 记录指针
const CALL_VA = 0x1103f0;   // s0..s5 = 绘制参数

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

let pending = null, n = 0;

Interceptor.attach(img.add(REC_VA), {
  onEnter(args) {
    if (n >= 16) { pending = null; return; }
    try {
      const p = this.context.x0;
      const s = [];
      for (let i = 0; i < 8; i++) s.push(p.add(i * 2).readS16());
      pending = s;
    } catch (e) { pending = null; }
  }
});

Interceptor.attach(img.add(CALL_VA), {
  onEnter(args) {
    if (pending === null) return;
    n++;
    const c = this.context;
    const rec = pending; pending = null;
    send('rec[' + rec.join(',') + ']  ->  x=' + c.s0 + ' y=' + c.s1 +
      ' a=' + c.s2 + ' b=' + c.s3 + ' c=' + c.s4 + ' d=' + c.s5);
  }
});
setTimeout(() => { send({ done: true }); }, 6000);
