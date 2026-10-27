// 诊断：看「中」有没有产生绘制四边形
const STR_VA = 0x45cd90, DRAW_VA = 0x110088, CALL_VA = 0x1103f0, REC_VA = 0x110338;
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
let inDraw = false, pending = null, n = 0;

Interceptor.attach(img.add(DRAW_VA), {
  onEnter(args) {
    inDraw = true;
    try {
      const t = args[2], len = args[3].toInt32();
      if (len > 0 && len < 40) {
        const s = t.readUtf16String(len);
        if (/^[A-Za-z]+$/.test(s)) {
          send('文本 ' + JSON.stringify(s) + ' len=' + len + ' font=' + args[0]);
        }
      }
    } catch (e) { }
  },
  onLeave() { inDraw = false; }
});

Interceptor.attach(img.add(REC_VA), {
  onEnter(args) {
    if (!inDraw) return;
    const p = this.context.x0;
    const v = []; for (let k = 0; k < 8; k++) v.push(p.add(k * 2).readS16());
    pending = v;
  }
});

Interceptor.attach(img.add(CALL_VA), {
  onEnter(args) {
    if (!inDraw || !pending) return;
    if (n >= 30) return;
    n++;
    const c = this.context;
    send('quad rec=' + pending.join(',') + ' -> x=' + c.s0 + ' y=' + c.s1 +
      ' w=' + c.s2 + ' h=' + c.s3 + ' sx=' + c.s4 + ' sy=' + c.s5);
    pending = null;
  }
});
setTimeout(() => { send({ done: true }); }, 5000);
