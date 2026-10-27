// 把码表 + 全部记录 dump 下来做离线分析
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
    const cnt = font.add(8).readU32();
    const codes = font.add(0x10).readPointer();
    const recs = font.add(0x28).readPointer();
    const texs = font.add(0x40).readPointer();
    send(`font=${font} count=${cnt} codes=${codes} recs=${recs} textures=${texs}`);
    send({ file: 'codes.bin', cnt }, codes.readByteArray(cnt * 2));

    const blob = new Uint8Array(cnt * 24);
    for (let i = 0; i < cnt; i++) {
      const p = recs.add(i * 8).readPointer();
      blob.set(new Uint8Array(p.readByteArray(24)), i * 24);
    }
    send({ file: 'recs.bin', n: cnt }, blob.buffer);

    // 纹理表（最多 8 个）
    const texBlob = new Uint8Array(8 * 8);
    for (let i = 0; i < 8; i++) {
      const p = texs.add(i * 8).readPointer();
      for (let b = 0; b < 8; b++) texBlob[i * 8 + b] = p.add(b).readU8();
    }
    send({ file: 'texs.bin' }, texBlob.buffer);
    // 纹理对象本身（前 0x100 字节）
    const t0 = texs.readPointer();
    send({ file: 'tex0.bin' }, t0.readByteArray(0x100));
    send(`tex0=${t0}`);
    setTimeout(() => send({ done: true }), 200);
  }
});
setTimeout(() => { if (!taken) { send('没抓到'); send({ done: true }); } }, 5000);
