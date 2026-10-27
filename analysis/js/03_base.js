// 在 RWX 区里找 XE3U 头，算出镜像基址，并和本地解出的 bin 对齐验证
const REGION = ptr('0x758cf8b000');
const SIZE = 0x586000;

const hits = Memory.scanSync(REGION, SIZE, '58 45 33 55 00 28 04 00');
send('XE3U 命中: ' + hits.length);
for (const h of hits) send('  ' + h.address + '  delta=0x' + h.address.sub(REGION).toString(16));

// 顺便看看 CIwGxFont 附近，确认布局
const fontHit = Memory.scanSync(REGION, SIZE, '43 49 77 47 78 46 6f 6e 74');
send('CIwGxFont 命中: ' + fontHit.length);
for (const h of fontHit.slice(0, 10)) {
  send('  ' + h.address + '  delta=0x' + h.address.sub(REGION).toString(16));
}
send({ done: true });
