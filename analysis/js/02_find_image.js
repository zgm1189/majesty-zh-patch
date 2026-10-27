// 找 s3e 镜像落在哪块内存：直接扫所有可读区段找 "CIwGxFont"
const ranges = Process.enumerateRanges({ protection: 'r--', coalesce: true });
send('可读区段: ' + ranges.length);
let total = 0, hitsAll = [];
for (const r of ranges) {
  if (r.size > 0x8000000) continue;           // >128MB 跳过
  total += r.size;
  try {
    const hits = Memory.scanSync(r.base, r.size, '43 49 77 47 78 46 6f 6e 74');
    if (hits.length) {
      hitsAll.push({ base: r.base, size: r.size, prot: r.protection, n: hits.length, first: hits[0].address });
    }
  } catch (e) {
    send('scan err ' + r.base + ' size=0x' + r.size.toString(16) + ' ' + e.message);
  }
}
send('已扫 ' + (total / 1048576).toFixed(0) + ' MB');
for (const h of hitsAll) {
  send(`  命中 ${h.base} size=0x${h.size.toString(16)} ${h.prot} n=${h.n} first=${h.first}`);
}
send({ done: true });
