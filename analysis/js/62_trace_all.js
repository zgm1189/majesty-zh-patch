// 追踪 img+0x110088 的每一次调用（去重），用于回答：
//   建筑面板的名称到底走不走 DrawText？
// 不加载 libzhfont.so —— 纯观察，避免两套钩子打架。

const SIG = '9CIwGxFont';
const SIG_VA = 0x45cd90;
const DRAW_VA = 0x110088;

let pats = [];
for (let i = 0; i < SIG.length; i++) pats.push(('0' + SIG.charCodeAt(i).toString(16)).slice(-2));
const pattern = pats.join(' ');

let base = null;
for (const prot of ['rwx', 'r-x', '--x']) {
  let rs;
  try { rs = Process.enumerateRanges(prot); } catch (e) { continue; }
  for (const r of rs) {
    if (r.size < 0x100000 || r.size > 0x8000000) continue;
    let hits;
    try { hits = Memory.scanSync(r.base, r.size, pattern); } catch (e) { continue; }
    for (const h of hits) {
      const b = h.address.sub(SIG_VA);
      if (b.and(0xfff).toInt32() === 0) { base = b; break; }
    }
    if (base) break;
  }
  if (base) break;
}

if (!base) {
  send('找不到镜像');
  send({ done: true });
} else {
  send('img base = ' + base + '  draw = ' + base.add(DRAW_VA));
  const seen = new Set();
  let total = 0;
  Interceptor.attach(base.add(DRAW_VA), {
    onEnter(args) {
      total++;
      const font = args[0];
      const text = args[2];
      const len = args[3].toInt32();
      if (len <= 0 || len > 300) return;
      try {
        let s = '';
        for (let i = 0; i < len; i++) {
          const c = text.add(i * 2).readU16();
          s += (c >= 0x20 && c < 0x7f) ? String.fromCharCode(c) : ('\\u' + c.toString(16));
        }
        const key = font + '|' + len + '|' + s;
        if (seen.has(key)) return;
        seen.add(key);
        send('#' + seen.size + ' f=' + font + ' n=' + len + ' [' + s + ']');
      } catch (e) { send('读取失败 ' + e); }
    }
  });
  send('钩子已装');
  setInterval(() => { send('--- 累计调用 ' + total + ' 去重 ' + seen.size + ' ---'); }, 20000);
}
