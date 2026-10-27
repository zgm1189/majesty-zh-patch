// 纯观察：hook 引擎 DrawText(img+0x110088)，打印所有含非 ASCII 的短文本调用。
// 目的：确认建筑面板名称是否走这个绘制函数。
const SIG_VA = 0x45cd90;
const DRAW_VA = 0x110088;

function findImage() {
  const ranges = Process.enumerateRanges({ protection: 'r--', coalesce: true });
  const sig = '39 43 49 77 47 78 46 6f 6e 74'; // "9CIwGxFont"
  const maps = Process.enumerateRanges('r--');
  // 直接扫所有可读段
  const all = Process.enumerateRanges({ protection: 'r--' });
  for (const r of all) {
    if (r.size < 0x100000 || r.size > 0x8000000) continue;
    let hits;
    try { hits = Memory.scanSync(r.base, r.size, sig); } catch (e) { continue; }
    for (const h of hits) {
      const base = h.address.sub(SIG_VA);
      if (base.toUInt32() % 0x1000 === 0) return base;
    }
  }
  return null;
}

const base = findImage();
if (!base) { send('找不到镜像'); send({done:true}); }
else {
  send('img base = ' + base);
  const drawAddr = base.add(DRAW_VA);
  let n = 0;
  Interceptor.attach(drawAddr, {
    onEnter(args) {
      if (n > 3000) return;
      try {
        const font = args[0];
        const text = args[2];
        const len = args[3].toInt32();
        if (len <= 0 || len > 20) return;
        const arr = [];
        let has = false;
        for (let i = 0; i < len; i++) {
          const cp = text.add(i * 2).readU16();
          arr.push(cp.toString(16));
          if (cp >= 0x80 && cp !== 0xffff) has = true;
        }
        if (!has) return;
        // 跳过主菜单「创建」
        if (len === 2 && arr[0] === '521b' && arr[1] === '5efa') return;
        n++;
        send('DRAW f=' + font + ' len=' + len + ' cp=' + arr.join(','));
      } catch (e) {}
    }
  });
  send('已 hook DrawText');
}
setTimeout(() => { send({done:true}); }, 60000);
