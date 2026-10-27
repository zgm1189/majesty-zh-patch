// 探针：dump 字体对象与它的 textures 数组
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
send('img=' + img);

let done = false;
Interceptor.attach(img.add(CALL_VA), {
  onEnter(args) {
    if (done) return;
    done = true;
    const ctx = this.context;
    // 反推字体对象：调用点处 x19 是 font
    const font = ctx.x19;
    send('font=' + font);
    const dump = [];
    for (let off = 0; off < 0xa0; off += 8) {
      dump.push(off.toString(16) + ':' + font.add(off).readPointer());
    }
    send('font fields:\n' + dump.join('\n'));
    try {
      const texArr = font.add(0x40).readPointer();
      for (let i = 0; i < 6; i++) {
        const t = texArr.add(i * 8).readPointer();
        const f = [];
        for (let off = 0; off < 0x30; off += 4) {
          f.push(off.toString(16) + '=' + t.add(off).readU32());
        }
        send('tex[' + i + ']=' + t + '  ' + f.join(' '));
      }
    } catch (e) { send('tex err ' + e); }
  }
});
setTimeout(() => { send({ done: true }); }, 5000);
