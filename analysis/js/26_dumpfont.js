// 按确认后的结构重新导出字体码表与记录
const STR_VA = 0x45cd90, CALL_VA = 0x110338;
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
let done = false;

Interceptor.attach(img.add(CALL_VA), {
  onEnter(args) {
    if (done) return;
    done = true;
    const font = this.context.x19;
    const count = font.add(0x08).readU32();
    const capCodes = font.add(0x1c).readU32();
    const codesPtr = font.add(0x10).readPointer();
    const capRecs = font.add(0x34).readU32();
    const recsPtr = font.add(0x28).readPointer();
    const texArr = font.add(0x40).readPointer();
    const texCount = font.add(0x48).readU32();
    send('font=' + font + ' count=' + count + ' capCodes=' + capCodes +
      ' codes=' + codesPtr + ' capRecs=' + capRecs + ' recs=' + recsPtr +
      ' texCount=' + texCount + ' texArr=' + texArr);

    send({ file: 'codes2.bin' }, codesPtr.readByteArray(count * 2));

    const out = Memory.alloc(count * 16);
    for (let i = 0; i < count; i++) {
      const p = recsPtr.add(i * 8).readPointer();
      try { out.add(i * 16).writeByteArray(p.readByteArray(16)); }
      catch (e) { out.add(i * 16).writeByteArray(new ArrayBuffer(16)); }
    }
    send({ file: 'recs2.bin' }, out.readByteArray(count * 16));

    // 同时记录每页的尺寸
    for (let i = 0; i < texCount; i++) {
      const page = texArr.add(i * 8).readPointer();
      send('page[' + i + ']=' + page + ' vt=' + page.readPointer() +
        ' w=' + page.add(0x1c).readFloat() + ' h=' + page.add(0x20).readFloat());
    }
  }
});
setTimeout(() => { send({ done: true }); }, 6000);
