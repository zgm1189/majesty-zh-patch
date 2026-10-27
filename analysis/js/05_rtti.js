// 用 RTTI 找到 CIwGxFont 的 type_info 和 vtable
const STR_VA = 0x45cd90;          // "9CIwGxFont" 在镜像里的 vaddr
const REGION_HINT = ptr('0x758cf8b000');

function findImage() {
  const ranges = Process.enumerateRanges({ protection: 'r--', coalesce: true });
  for (const r of ranges) {
    if (r.size > 0x8000000 || r.size < 0x100000) continue;
    try {
      const hits = Memory.scanSync(r.base, r.size, '39 43 49 77 47 78 46 6f 6e 74');
      if (hits.length) return { base: hits[0].address.sub(STR_VA), range: r, hits: hits.length };
    } catch (e) { }
  }
  return null;
}

const img = findImage();
if (!img) { send('没找到镜像'); send({ done: true }); }
else {
  send(`镜像基址 = ${img.base}  (区段 ${img.range.base} size=0x${img.range.size.toString(16)} ${img.range.protection})`);

  // type_info 里第 2 个指针指向类名字符串
  const want = img.base.add(STR_VA);
  const lo = want.toUInt32() >>> 0, hi = want.shr(32).toUInt32() >>> 0;
  const pat = [];
  for (let i = 0; i < 4; i++) pat.push(((lo >>> (8 * i)) & 0xff).toString(16).padStart(2, '0'));
  for (let i = 0; i < 4; i++) pat.push(((hi >>> (8 * i)) & 0xff).toString(16).padStart(2, '0'));
  const hits = Memory.scanSync(img.range.base, img.range.size, pat.join(' '));
  send(`指向类名的指针出现 ${hits.length} 次`);
  for (const h of hits) {
    const ti = h.address.sub(8);
    const vt = ti.readPointer();
    const nm = ti.add(8).readPointer();
    const raw = nm.readCString();
    const nmStr = raw.replace(/^\d+/, '');
    send(`  type_info@${ti}  vtable=${vt}  name="${nmStr}"`);
    if (nmStr === 'CIwGxFont') {
      send('  --- vtable 前 32 项 ---');
      for (let i = 0; i < 32; i++) {
        const fn = vt.add(i * 8).readPointer();
        const off = fn.sub(img.base);
        send(`    [${i}] ${fn}  img+0x${off.toString(16)}`);
      }
    }
  }
  send({ done: true });
}
