// 收集 3 秒内所有不同的字体对象，看各自码表
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
const fonts = new Map();

Interceptor.attach(img.add(DRAW_VA), {
  onEnter(args) {
    const f = args[0];
    const key = f.toString();
    let e = fonts.get(key);
    if (!e) {
      let text = '';
      try { text = args[2].readUtf16String(args[3].toInt32()); } catch (err) { }
      e = { font: f, count: f.add(8).readU32(), codes: f.add(0x10).readPointer(), recs: f.add(0x28).readPointer(), texts: [], n: 0 };
      fonts.set(key, e);
    }
    e.n++;
    if (e.texts.length < 3) { try { e.texts.push(args[2].readUtf16String(args[3].toInt32())); } catch (err) { } }
  }
});

setTimeout(() => {
  send(`不同字体对象: ${fonts.size}`);
  for (const e of fonts.values()) {
    const head = Array.from({ length: 10 }, (_, i) => e.codes.add(i * 2).readU16()).join(',');
    const tail = Array.from({ length: 4 }, (_, i) => e.codes.add((e.count - 4 + i) * 2).readU16()).join(',');
    send(`  font=${e.font} count=${e.count} 调用=${e.n}`);
    send(`    codes head=${head} tail=${tail}`);
    send(`    recs=${e.recs} 文本=${JSON.stringify(e.texts)}`);
  }
  send({ done: true });
}, 3000);
