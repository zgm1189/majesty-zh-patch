// 把第一个字体的码表和记录表 dump 出来（本地分析）
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
let taken = false;
Interceptor.attach(img.add(DRAW_VA), {
  onEnter(args) {
    if (taken) return;
    taken = true;
    const font = args[0];
    const len = args[3].toInt32();
    let text = '';
    try { text = args[2].readUtf16String(len); } catch (e) { }
    send(`font=${font} text=${JSON.stringify(text)}`);

    const cnt = font.add(8).readU32();
    const codes = font.add(0x10).readPointer();
    const recs = font.add(0x28).readPointer();
    send({ file: 'codes.bin', cnt }, codes.readByteArray(cnt * 2));
    // 记录指针表（只取前 64 个指针 + 每个记录 32 字节）
    const recBuf = [];
    for (let i = 0; i < Math.min(cnt, 64); i++) {
      const p = recs.add(i * 8).readPointer();
      recBuf.push(p);
    }
    let blob = new Uint8Array(64 * 32);
    for (let i = 0; i < recBuf.length; i++) {
      blob.set(new Uint8Array(recBuf[i].readByteArray(32)), i * 32);
    }
    send({ file: 'recs.bin', n: recBuf.length }, blob.buffer);
    send(`记录指针: ${recBuf.map(p => p.toString()).join(',')}`);
    setTimeout(() => send({ done: true }), 200);
  }
});
setTimeout(() => { if (!taken) { send('没抓到'); send({ done: true }); } }, 5000);
