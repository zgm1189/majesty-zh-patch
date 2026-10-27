// 由 type_info 反查真正的 CIwGxFont vtable（type_info 指针存放在 vtable 的 -8 处）
const STR_VA = 0x45cd90;

function findImage() {
  const ranges = Process.enumerateRanges({ protection: 'r--', coalesce: true });
  for (const r of ranges) {
    if (r.size > 0x8000000 || r.size < 0x100000) continue;
    try {
      const hits = Memory.scanSync(r.base, r.size, '39 43 49 77 47 78 46 6f 6e 74');
      if (hits.length) return { base: hits[0].address.sub(STR_VA), range: r };
    } catch (e) { }
  }
  return null;
}
function hexPat(p) {
  const lo = p.toUInt32() >>> 0, hi = p.shr(32).toUInt32() >>> 0, out = [];
  for (let i = 0; i < 4; i++) out.push(((lo >>> (8 * i)) & 0xff).toString(16).padStart(2, '0'));
  for (let i = 0; i < 4; i++) out.push(((hi >>> (8 * i)) & 0xff).toString(16).padStart(2, '0'));
  return out.join(' ');
}

const img = findImage();
const want = img.base.add(STR_VA);
const tiHit = Memory.scanSync(img.range.base, img.range.size, hexPat(want))[0].address.sub(8);
const ti = tiHit;
send(`type_info = ${ti} (img+0x${ti.sub(img.base).toString(16)})`);

const vtHits = Memory.scanSync(img.range.base, img.range.size, hexPat(ti));
send(`type_info 被引用 ${vtHits.length} 处`);
for (const h of vtHits) {
  const ap = h.address.add(8);          // address point = 第一个虚函数
  const toTop = h.address.sub(8).readS64();
  send(`  vtable address-point = ${ap} (img+0x${ap.sub(img.base).toString(16)})  offset-to-top=${toTop}`);
  for (let i = 0; i < 24; i++) {
    const fn = ap.add(i * 8).readPointer();
    if (fn.isNull()) break;
    const off = fn.sub(img.base);
    send(`    [${i}] img+0x${off.toString(16)}  ${fn}`);
  }
}
send({ done: true });
