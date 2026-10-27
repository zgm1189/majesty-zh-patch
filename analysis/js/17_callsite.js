// 探针：在字形绘制函数的 call 点取实际参数
const STR_VA = 0x45cd90, DRAW_VA = 0x110088, CALLSITE_VA = 0x1103f0;

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

let logged = 0;
Interceptor.attach(img.add(CALLSITE_VA), {
  onEnter(args) {
    if (logged >= 20) return;
    logged++;
    const c = this.context;
    let w = 0, h = 0;
    try { w = args[0].add(0x1c).readFloat(); h = args[0].add(0x20).readFloat(); } catch (e) { }
    send('tex=' + args[0] + ' (' + w + 'x' + h + ')' +
      ' | s0=' + c.s0 + ' s1=' + c.s1 + ' s2=' + c.s2 +
      ' s3=' + c.s3 + ' s4=' + c.s4 + ' s5=' + c.s5);
  }
});
setTimeout(() => { send({ done: true }); }, 6000);
