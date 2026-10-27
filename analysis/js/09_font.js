// 挂钩 0x110088（字符串排版/绘制），dump 字体对象结构和实际绘制的文本
const STR_VA = 0x45cd90;
const DRAW_VA = 0x110088;

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
send('镜像 = ' + img);
const fn = img.add(DRAW_VA);
send('目标 = ' + fn);

const seen = new Set();
let count = 0;
Interceptor.attach(fn, {
  onEnter(args) {
    const font = args[0];
    const text = args[2];
    const len = args[3].toInt32();
    count++;
    if (count > 40) return;
    let s = '';
    try { s = text.readUtf16String(len); } catch (e) { s = '<读不到>'; }
    const key = font + '|' + s;
    if (seen.has(key)) return;
    seen.add(key);
    send(`--- font=${font} len=${len} text=${JSON.stringify(s)}`);
    try {
      const b = font.readByteArray(0xa0);
      const u8 = new Uint8Array(b);
      const dv = new DataView(b);
      send(`    +0x00 u8=${u8[0]}  +0x08 u32=${dv.getUint32(8, true)}  +0x10 ptr=${font.add(0x10).readPointer()}`);
      send(`    +0x28 ptr=${font.add(0x28).readPointer()}  +0x84 u32=${dv.getUint32(0x84, true)}  +0x88 u32=${dv.getUint32(0x88, true)}  +0x8c u8=${u8[0x8c]}`);
      const cnt = dv.getUint32(8, true);
      if (cnt > 0 && cnt < 4000) {
        const codes = font.add(0x10).readPointer();
        const recs = font.add(0x28).readPointer();
        const arr = [];
        for (let i = 0; i < Math.min(cnt, 12); i++) arr.push(codes.add(i * 2).readU16());
        send(`    码表前12: ${arr.map(x => x.toString(16)).join(',')}`);
        const r0 = recs.readPointer();
        send(`    记录[0]=${r0}  前16字节=${r0.readByteArray(16) ? '' : ''}`);
        const raw = new Uint8Array(r0.readByteArray(16));
        send(`    rec0 bytes: ${Array.from(raw).map(x => x.toString(16).padStart(2, '0')).join(' ')}`);
      }
    } catch (e) { send('    结构读取失败: ' + e.message); }
  }
});
setTimeout(() => { send('总调用 ' + count); send({ done: true }); }, 4000);
