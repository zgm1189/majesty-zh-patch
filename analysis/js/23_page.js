// 探针：深入 dump 字体纹理页结构
const STR_VA = 0x45cd90, CALL_VA = 0x110338;

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
let done = false;

function isPtr(v) {
  return v.compare(0x1000) > 0 && v.compare(0x0000ffffffffffff) < 0;
}

Interceptor.attach(img.add(CALL_VA), {
  onEnter(args) {
    if (done) return;
    done = true;
    const font = this.context.x19;
    const texArr = font.add(0x40).readPointer();
    send('font=' + font + ' texArr=' + texArr);
    const page = texArr.readPointer();
    send('page=' + page);
    const words = [];
    for (let off = 0; off < 0x60; off += 8) {
      const p = page.add(off).readPointer();
      words.push('+' + off.toString(16) + '=' + p);
    }
    send('page qwords:\n' + words.join('\n'));
    for (let off = 0; off < 0x60; off += 8) {
      const p = page.add(off).readPointer();
      if (!isPtr(p)) continue;
      try {
        const inner = [];
        for (let o2 = 0; o2 < 0x40; o2 += 8) inner.push(p.add(o2).readPointer());
        send('-> [' + off.toString(16) + '] ' + p + ' : ' + inner.join(' '));
      } catch (e) { send('-> [' + off.toString(16) + '] ' + p + ' unreadable'); }
    }
  }
});
setTimeout(() => { send({ done: true }); }, 5000);
