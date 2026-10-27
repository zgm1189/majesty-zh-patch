// 把 s3e 镜像整块内存 dump 下来，用于离线对齐与静态分析
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

const img = findImage();
const size = img.range.size;
send(`镜像 ${img.base} size=0x${size.toString(16)}`);
const CHUNK = 0x100000;
for (let off = 0; off < size; off += CHUNK) {
  const n = Math.min(CHUNK, size - off);
  const buf = Memory.readByteArray(img.base.add(off), n);
  send({ file: `img_${off.toString(16).padStart(6, '0')}.bin`, base: img.base.toString(), off: off }, buf);
}
send(`IMG_BASE=${img.base}`);
send({ done: true });
