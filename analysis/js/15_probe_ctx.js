// 探针：确认 Frida 在 arm64 上暴露哪些浮点寄存器字段
const STR_VA = 0x45cd90, DRAW_VA = 0x110088, QUAD_VA = 0x1ba194;

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

let keysDumped = false, inDraw = 0, logged = 0;

Interceptor.attach(img.add(DRAW_VA), {
  onEnter(args) { inDraw++; },
  onLeave(ret) { inDraw--; }
});

Interceptor.attach(img.add(QUAD_VA), {
  onEnter(args) {
    if (!keysDumped) {
      keysDumped = true;
      send('ctx keys: ' + Object.keys(this.context).join(','));
    }
    if (inDraw <= 0) return;
    if (logged > 40) return;
    logged++;
    const c = this.context;
    const parts = ['tex=' + args[0]];
    for (const k of ['s0', 's1', 's2', 's3', 's4', 's5', 'd0', 'd1', 'd2', 'q0', 'q1', 'q2']) {
      if (c[k] !== undefined) parts.push(k + '=' + c[k]);
    }
    send(parts.join(' '));
  }
});

setTimeout(() => { send({ done: true }); }, 8000);
