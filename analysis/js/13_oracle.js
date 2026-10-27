// 用引擎自己当判据：每帧把横幅文本改写成已知串，看画出来对不对
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
const TEST = 'ABCDEFGHIJKLMNOPQRSTUVW';
let announced = false;

Interceptor.attach(img.add(DRAW_VA), {
  onEnter(args) {
    const text = args[2];
    const len = args[3].toInt32();
    if (len !== TEST.length) return;
    if (!announced) {
      announced = true;
      send('开始改写: ' + JSON.stringify(text.readUtf16String(len)));
    }
    try {
      Memory.protect(text, (len + 2) * 2, 'rw-');
      for (let i = 0; i < len; i++) text.add(i * 2).writeU16(TEST.charCodeAt(i));
    } catch (e) { }
  }
});
setTimeout(() => { send('改写窗口结束'); send({ done: true }); }, 6000);
