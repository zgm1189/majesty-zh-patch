// 抓一个字体对象，完整 dump 结构
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
const hex = (buf, n) => Array.from(new Uint8Array(buf, 0, n)).map(x => x.toString(16).padStart(2, '0')).join(' ');

let done = false;
Interceptor.attach(img.add(DRAW_VA), {
  onEnter(args) {
    if (done) return;
    done = true;
    const font = args[0];
    const len = args[3].toInt32();
    let text = '';
    try { text = args[2].readUtf16String(len); } catch (e) { }
    send(`font=${font} text=${JSON.stringify(text)}`);

    send('对象前 0x100 字节:');
    for (let off = 0; off < 0x100; off += 0x20) {
      send(`  +${off.toString(16).padStart(3, '0')}: ${hex(font.add(off).readByteArray(0x20), 0x20)}`);
    }
    const cnt = font.add(8).readU32();
    const codes = font.add(0x10).readPointer();
    const recs = font.add(0x28).readPointer();
    send(`count=${cnt} codes=${codes} recs=${recs}`);
    send(`codes[0..15]: ${Array.from({ length: 16 }, (_, i) => codes.add(i * 2).readU16()).join(',')}`);
    send(`codes[last8]: ${Array.from({ length: 8 }, (_, i) => codes.add((cnt - 8 + i) * 2).readU16()).join(',')}`);
    send('records 指针[0..7]:');
    for (let i = 0; i < 8; i++) {
      const p = recs.add(i * 8).readPointer();
      send(`  [${i}] ${p}  ${hex(p.readByteArray(20), 20)}`);
    }
    // 顺便看看对象里所有像指针的字段
    send('对象里 8 字节对齐的疑似指针:');
    for (let off = 0; off < 0x100; off += 8) {
      const v = font.add(off).readU64();
      if (v.compare(ptr('0x1000')) > 0 && v.compare(ptr('0x800000000000')) < 0) {
        send(`  +${off.toString(16)} = ${v}`);
      }
    }
    setTimeout(() => send({ done: true }), 300);
  }
});
setTimeout(() => { if (!done) { send('4 秒内没抓到绘制'); send({ done: true }); } }, 4000);
