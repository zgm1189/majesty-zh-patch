// 诊断：检查码表插入点附近
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
let done = false;
Interceptor.attach(img.add(DRAW_VA), {
  onEnter(args) {
    if (done) return;
    done = true;
    const font = args[0];
    const count = font.add(0x08).readU32();
    const cap = font.add(0x1c).readU32();
    const codes = font.add(0x10).readPointer();
    send('font=' + font + ' count=' + count + ' cap=' + cap);
    const all = [];
    for (let i = 0; i < count; i++) all.push(codes.add(i * 2).readU16());
    let bad = 0;
    for (let i = 1; i < count; i++) if (all[i] < all[i - 1]) bad++;
    send('逆序对数量=' + bad);
    send('codes[0..12]=' + all.slice(0, 12).map(v => v.toString(16)).join(','));
    send('codes[220..234]=' + all.slice(220, 234).map(v => v.toString(16)).join(','));
    // 复刻汇编里的二分查找
    const target = 0x4e2d;
    let w3 = count - 1, w1 = 0;
    if (w3 < 0) { send('空表'); return; }
    w1 = (all[w3] === target) ? w3 : 0;
    let w4 = w3 - w1;
    let mid = (w3 + w1) >> 1;
    let guard = 0;
    while (w4 > 1 && guard++ < 40) {
      const v = all[mid];
      if (v > target) { w3 = mid; }
      else { w1 = mid; if (v === target) w3 = mid; }
      w4 = w3 - w1;
      mid = (w3 + w1) >> 1;
    }
    send('复刻查找: w1=' + w1 + ' codes[w1]=' + all[w1].toString(16) +
      ' 命中=' + (all[w1] === target));
  }
});
setTimeout(() => { send({ done: true }); }, 4000);
