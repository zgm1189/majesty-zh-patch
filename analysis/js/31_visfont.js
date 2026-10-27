// 探针：dump 主菜单可见字体的结构
const STR_VA = 0x45cd90, DRAW_VA = 0x110088;
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
const seen = {};
Interceptor.attach(img.add(DRAW_VA), {
  onEnter(args) {
    const font = args[0];
    const key = font.toString();
    if (seen[key]) return;
    seen[key] = 1;
    const count = font.add(0x08).readU32();
    const codes = font.add(0x10).readPointer();
    const recs = font.add(0x28).readPointer();
    const texArr = font.add(0x40).readPointer();
    const texCount = font.add(0x48).readU32();
    const line = [];
    for (let i = 0; i < texCount && i < 4; i++) {
      const p = texArr.add(i * 8).readPointer();
      line.push('page[' + i + ']=' + p + ' w=' + p.add(0x1c).readFloat() + ' h=' + p.add(0x20).readFloat());
    }
    send('FONT ' + font + ' count=' + count + ' codes=' + codes + ' recs=' + recs +
      ' texCount=' + texCount + ' | ' + line.join(' '));
    // 采样前 8 个码位
    const cs = [];
    for (let i = 0; i < 8; i++) cs.push(codes.add(i * 2).readU16().toString(16));
    send('   codes[0..8]=' + cs.join(','));
    for (const idx of [0, 1, 2]) {
      const rp = recs.add(idx * 8).readPointer();
      const v = [];
      for (let k = 0; k < 8; k++) v.push(rp.add(k * 2).readS16());
      send('   rec[' + idx + ']=' + v.join(','));
    }
  }
});
setTimeout(() => { send({ done: true }); }, 4000);
