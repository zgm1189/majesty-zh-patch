// 探针：在最内层绘制函数上取 s0..s7 与纹理尺寸
const STR_VA = 0x45cd90, DRAW_VA = 0x110088, INNER_VA = 0x1b9edc;

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

let inDraw = 0, logged = 0;

Interceptor.attach(img.add(DRAW_VA), {
  onEnter(args) { inDraw++; },
  onLeave(ret) { inDraw--; }
});

Interceptor.attach(img.add(INNER_VA), {
  onEnter(args) {
    if (inDraw <= 0) return;
    if (logged >= 24) return;
    logged++;
    const c = this.context;
    let w = 0, h = 0;
    try { w = args[0].add(0x1c).readU32(); h = args[0].add(0x20).readU32(); } catch (e) { }
    send('W=' + w + ' H=' + h + ' | s0=' + c.s0 + ' s1=' + c.s1 + ' s2=' + c.s2 +
      ' s3=' + c.s3 + ' s4=' + c.s4 + ' s5=' + c.s5 + ' s6=' + c.s6 + ' s7=' + c.s7);
  }
});

setTimeout(() => { send({ done: true }); }, 8000);
