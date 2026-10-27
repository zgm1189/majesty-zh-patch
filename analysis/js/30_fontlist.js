// 探针：列出每一帧里所有字体绘制调用（字体对象 + 文本）
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
let n = 0;
Interceptor.attach(img.add(DRAW_VA), {
  onEnter(args) {
    if (n >= 60) return;
    const font = args[0];
    const text = args[2];
    const len = args[3].toInt32();
    if (len <= 0 || len > 200) return;
    n++;
    let s = '';
    try { s = text.readUtf16String(len); } catch (e) { s = '<err>'; }
    send('font=' + font + ' len=' + len + ' ' + JSON.stringify(s));
  }
});
setTimeout(() => { send({ done: true }); }, 4000);
