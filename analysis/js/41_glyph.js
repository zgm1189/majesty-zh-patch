// 自动生成：把汉字字形塞进引擎字体图集并注册码位
const STR_VA = 0x45cd90, DRAW_VA = 0x110088;
const REWRITE = '中文字体测试';
const GLYPHS = [
  { code: 0x4e2d, dx: 1, dy: 3, adv: 20, w: 18, h: 21, hex: 'ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff05ffffffe0ffffffd2ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff01ffffffffffffffe9ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00fffffffcffffffe2ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00fffffff6ffffffdeffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff22ffffff54ffffff54ffffff54ffffff54ffffff54ffffff54ffffff54fffffff6ffffffe8ffffff54ffffff54ffffff54ffffff54ffffff54ffffff54ffffff54ffffff1cffffff63ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff4effffff5bffffffffffffff7effffff0cffffff0cffffff0cffffff0cffffff0cfffffff0ffffffddffffff0cffffff0cffffff0cffffff0cffffff0cffffff91ffffffffffffff47ffffff57ffffffffffffff78ffffff00ffffff00ffffff00ffffff00ffffff00fffffff0ffffffdcffffff00ffffff00ffffff00ffffff00ffffff00ffffff8cffffffffffffff42ffffff55ffffffffffffff78ffffff00ffffff00ffffff00ffffff00ffffff00fffffff0ffffffdcffffff00ffffff00ffffff00ffffff00ffffff00ffffff8cffffffffffffff40ffffff54ffffffffffffff78ffffff00ffffff00ffffff00ffffff00ffffff00fffffff0ffffffdcffffff00ffffff00ffffff00ffffff00ffffff00ffffff8cffffffffffffff40ffffff55ffffffffffffff78ffffff00ffffff00ffffff00ffffff00ffffff00fffffff0ffffffdcffffff00ffffff00ffffff00ffffff00ffffff00ffffff8cffffffffffffff40ffffff58ffffffffffffffefffffffe0ffffffe0ffffffe0ffffffe0ffffffe0fffffffefffffffbffffffe0ffffffe0ffffffe0ffffffe0ffffffe0fffffff1ffffffffffffff43ffffff5dffffffffffffffbcffffff80ffffff80ffffff80ffffff80ffffff80fffffff8ffffffeeffffff80ffffff80ffffff80ffffff80ffffff80ffffffc6ffffffffffffff49ffffff50ffffffc8ffffff5dffffff00ffffff00ffffff00ffffff00ffffff00fffffff0ffffffdcffffff00ffffff00ffffff00ffffff00ffffff00ffffff6dffffffc8ffffff40ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00fffffff0ffffffdcffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00fffffff0ffffffdcffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00fffffff1ffffffdcffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00fffffff6ffffffe0ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff01fffffffdffffffe7ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff11ffffffffffffffefffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff01ffffff10ffffff0fffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00' },
  { code: 0x6587, dx: 1, dy: 3, adv: 21, w: 20, h: 21, hex: 'ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff35ffffffc9ffffff29ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff3dffffffffffffffc2ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffffa3ffffffffffffff5bffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff1cfffffff6ffffffc1ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff62ffffff73ffffff6cffffff68ffffff68ffffff68ffffff68ffffff68ffffff68ffffffa4ffffff6cffffff68ffffff68ffffff68ffffff68ffffff68ffffff69ffffff6dffffff74ffffff59ffffffccffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffb8ffffff38ffffff33ffffff29ffffff24ffffffc3ffffffffffffff43ffffff38ffffff38ffffff38ffffff38ffffff38ffffff3bfffffffaffffffdaffffff3affffff3cffffff3fffffff47ffffff37ffffff00ffffff00ffffff00ffffff00ffffff77ffffffffffffff40ffffff00ffffff00ffffff00ffffff00ffffff00ffffff33ffffffffffffff9affffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff2fffffffffffffff7fffffff00ffffff00ffffff00ffffff00ffffff00ffffff75ffffffffffffff5cffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffffd3ffffffdcffffff01ffffff00ffffff00ffffff00ffffff00ffffffd2fffffff4ffffff0effffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff6bffffffffffffff48ffffff00ffffff00ffffff00ffffff3bffffffffffffff9cffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff0dffffffe8ffffffd4ffffff04ffffff00ffffff00ffffffc2fffffffcffffff2bffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff63ffffffffffffff81ffffff00ffffff5cffffffffffffff9affffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff02ffffffbdfffffffeffffff76fffffff1ffffffe8ffffff16ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff13ffffffdeffffffffffffffffffffff43ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff51ffffffeeffffffffffffffffffffffa8ffffff11ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff20ffffff9cffffffffffffffe0ffffff3fffffff92ffffffffffffffeaffffff73ffffff0effffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff03ffffff42ffffffa6fffffffcfffffffeffffff9effffff10ffffff00ffffff00ffffff44ffffffdbfffffffffffffff5ffffffa8ffffff5effffff16ffffff00ffffff00ffffff55ffffffa9ffffffecffffffffffffffffffffffbbffffff35ffffff00ffffff00ffffff00ffffff00ffffff00ffffff06ffffff6affffffdaffffffffffffffffffffffffffffffe2ffffff70ffffff26fffffff7ffffffecffffff99ffffff2effffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff39ffffff91ffffffdfffffffdfffffff0affffff00ffffff2bffffff04ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff0cffffff00' },
  { code: 0x5b57, dx: 1, dy: 3, adv: 21, w: 20, h: 21, hex: 'ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff05ffffff87ffffffa1ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff07ffffffc4ffffffffffffff61ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff39ffffff4cffffff4cffffff4cffffff4cffffff4cffffff4cffffff60fffffff7fffffff3ffffff54ffffff4cffffff4cffffff4cffffff4cffffff4cffffff4cffffff4cffffff01ffffff00ffffffb7fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffbffffff00ffffff00ffffffaefffffff4ffffff14ffffff14ffffff14ffffff14ffffff14ffffff14ffffff14ffffff14ffffff14ffffff14ffffff14ffffff14ffffff14ffffff14ffffffb6fffffff1ffffff00ffffff00ffffffb4fffffff4ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffffb0fffffff8ffffff00ffffff00ffffff5dffffff76ffffff01ffffff67ffffff5cffffff58ffffff58ffffff58ffffff58ffffff58ffffff58ffffff58ffffff58ffffff58ffffff58ffffff09ffffff44ffffff64ffffff01ffffff00ffffff00ffffff00ffffff04ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff1cffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff2cffffff20ffffff1cffffff1cffffff1cffffff1cffffff1cffffff1cffffff79fffffff9fffffff8ffffff89ffffff06ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff1effffffb2ffffffffffffffb9ffffff23ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff73fffffff7fffffff3ffffff62ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffffa9ffffffffffffff43ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff48fffffffdfffffff6fffffff0fffffff0fffffff0fffffff0fffffff0fffffff0fffffff9fffffffffffffff3fffffff0fffffff0fffffff0fffffff0fffffff0fffffff1fffffff7ffffffcaffffff2bffffff96ffffff8fffffff88ffffff88ffffff88ffffff88ffffff88ffffff88ffffffcfffffffffffffffa0ffffff88ffffff88ffffff88ffffff88ffffff88ffffff8bffffff99ffffff88ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff98ffffffffffffff34ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff98ffffffffffffff34ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff98ffffffffffffff34ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffffa0ffffffffffffff33ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff45ffffffa9ffffffa6fffffff5ffffffffffffff1cffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff19fffffffffffffffffffffffbffffff9fffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff44ffffff2cffffff07ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00' },
  { code: 0x4f53, dx: 1, dy: 4, adv: 23, w: 22, h: 20, hex: 'ffffff00ffffff00ffffff00ffffff00ffffff19ffffff63ffffff0bffffff00ffffff00ffffff00ffffff00ffffff00ffffff53ffffffa0ffffff1affffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff57ffffffffffffffa2ffffff00ffffff00ffffff00ffffff00ffffff00ffffff7dffffffffffffff21ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff9fffffffffffffff2effffff00ffffff00ffffff00ffffff00ffffff00ffffff78ffffffffffffff1cffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff07ffffffefffffffc9ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff76ffffffffffffff18ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff5bffffffffffffff6dffffff10ffffff48ffffff3effffff3cffffff3cffffff3cffffff95ffffffffffffff4effffff3cffffff3cffffff3cffffff3effffff45ffffff1effffff00ffffff00ffffff00ffffff00ffffffc8ffffffffffffff40ffffff34ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff60ffffff00ffffff00ffffff00ffffff40ffffffffffffffffffffff40ffffff0bffffff2effffff27ffffff24ffffff41ffffffffffffffe7ffffffffffffffe9ffffffbfffffff24ffffff24ffffff26ffffff2cffffff14ffffff00ffffff00ffffff00ffffffc3ffffffffffffffffffffff40ffffff00ffffff00ffffff00ffffff00ffffff6effffffffffffffa5ffffffffffffffa0fffffff8ffffff0effffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff59ffffffffffffffc1ffffffffffffff40ffffff00ffffff00ffffff00ffffff00ffffffc2ffffffedffffff76ffffffffffffff54ffffffffffffff62ffffff00ffffff00ffffff00ffffff00ffffff00ffffff0cffffffebffffffdcffffff53ffffffffffffff40ffffff00ffffff00ffffff00ffffff3fffffffffffffff8bffffff74ffffffffffffff19ffffffcfffffffe0ffffff09ffffff00ffffff00ffffff00ffffff00ffffff00ffffff5bffffff45ffffff4cffffffffffffff40ffffff00ffffff00ffffff01ffffffc9fffffff9ffffff1affffff74ffffffffffffff18ffffff4fffffffffffffff80ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff4cffffffffffffff40ffffff00ffffff00ffffff81ffffffffffffff8effffff00ffffff74ffffffffffffff18ffffff00ffffffbafffffffcffffff54ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff4cffffffffffffff40ffffff00ffffff5affffffffffffffd2ffffff08ffffff00ffffff74ffffffffffffff18ffffff00ffffff15ffffffe3fffffff9ffffff57ffffff00ffffff00ffffff00ffffff00ffffff00ffffff4cffffffffffffff40ffffff76fffffffcfffffff3ffffff2bffffff00ffffff00ffffff74ffffffffffffff18ffffff00ffffff00ffffff35ffffffefffffffffffffffa8ffffff0fffffff00ffffff00ffffff00ffffff4cffffffffffffff92fffffffefffffff1ffffff3affffff6effffff94ffffff8effffffbfffffffffffffff93ffffff8affffff8fffffff36ffffff2cffffffe4ffffff8affffff02ffffff00ffffff00ffffff00ffffff4cffffffffffffff40ffffff5affffff36ffffff00ffffffaaffffffe7ffffffe0ffffffebffffffffffffffdcffffffdbffffffe2ffffff54ffffff00ffffff17ffffff01ffffff00ffffff00ffffff00ffffff00ffffff4cffffffffffffff40ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff76ffffffffffffff19ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff4effffffffffffff41ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff78ffffffffffffff1cffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff53ffffffffffffff46ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff7effffffffffffff23ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff53ffffffe4ffffff45ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff82fffffffcffffff2affffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00' },
  { code: 0x6d4b, dx: 1, dy: 3, adv: 22, w: 21, h: 21, hex: 'ffffff00ffffff00ffffff21ffffff02ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff3affffff74ffffff1fffffff00ffffff1affffffe8ffffffc3ffffff1fffffff00ffffff1dffffff40ffffff40ffffff40ffffff40ffffff40ffffff40ffffff35ffffff00ffffff00ffffff00ffffff00ffffff77ffffffffffffff3bffffff00ffffff05ffffff87fffffffdffffffecffffff44ffffff6fffffffffffffffffffffffffffffffffffffffffffffffffffffffcbffffff00ffffff00ffffff00ffffff00ffffff71ffffffffffffff35ffffff00ffffff00ffffff00ffffff49ffffffecffffff3effffff64ffffffffffffff31ffffff20ffffff20ffffff20ffffffd2ffffffc3ffffff00ffffff7affffffb2ffffff00ffffff70ffffffffffffff34ffffff00ffffff00ffffff00ffffff00ffffff0fffffff00ffffff60ffffffffffffff14ffffff03ffffff00ffffff00ffffffccffffffc0ffffff00ffffffa2fffffff5ffffff00ffffff70ffffffffffffff34ffffff00ffffff00ffffff03ffffff00ffffff00ffffff00ffffff60ffffffffffffff14ffffff98ffffffe9ffffff2effffffccffffffc0ffffff00ffffff9dfffffff0ffffff00ffffff70ffffffffffffff34ffffff00ffffff67ffffffc1ffffff17ffffff00ffffff00ffffff60ffffffffffffff14ffffff89ffffffffffffff24ffffffccffffffc0ffffff00ffffff9cfffffff0ffffff00ffffff70ffffffffffffff34ffffff00ffffff87ffffffffffffffe3ffffff2effffff00ffffff60ffffffffffffff14ffffff82ffffffffffffff16ffffffccffffffc0ffffff00ffffff9cfffffff0ffffff00ffffff70ffffffffffffff34ffffff00ffffff00ffffff5cfffffffcffffffe2ffffff06ffffff60ffffffffffffff14ffffff81ffffffffffffff0bffffffccffffffc0ffffff00ffffff9cfffffff0ffffff00ffffff70ffffffffffffff34ffffff00ffffff00ffffff00ffffff5dffffff43ffffff00ffffff60ffffffffffffff14ffffff83ffffffffffffff03ffffffccffffffc0ffffff00ffffff9cfffffff0ffffff00ffffff70ffffffffffffff34ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff61ffffffffffffff14ffffff9bfffffff8ffffff00ffffffccffffffc1ffffff00ffffff9cfffffff0ffffff00ffffff70ffffffffffffff34ffffff00ffffff00ffffff00ffffff00ffffff94ffffff18ffffff69ffffffffffffff14ffffffb5ffffffe7ffffff00ffffffccffffffc9ffffff00ffffff9cfffffff0ffffff00ffffff70ffffffffffffff34ffffff00ffffff00ffffff00ffffff39ffffffffffffffa9ffffff71ffffffffffffff14ffffffdfffffffc7ffffff00ffffffccffffffd1ffffff00ffffff9dfffffff1ffffff00ffffff70ffffffffffffff34ffffff00ffffff00ffffff00ffffffa2ffffffffffffff38ffffff33ffffff70ffffff31ffffffffffffff9bffffff00ffffff49ffffff4dffffff00ffffffa1fffffff5ffffff00ffffff70ffffffffffffff34ffffff00ffffff00ffffff1ffffffffbffffffbaffffff00ffffff00ffffff00ffffff74ffffffffffffff5affffff5dffffff08ffffff00ffffff00ffffffabfffffffdffffff00ffffff70ffffffffffffff34ffffff00ffffff00ffffff9effffffffffffff3cffffff00ffffff00ffffff02ffffffdbfffffff2ffffff65ffffffffffffffaaffffff00ffffff00ffffff0effffff14ffffff00ffffff70ffffffffffffff34ffffff00ffffff34fffffffdffffffc0ffffff00ffffff00ffffff00ffffff68ffffffffffffff87ffffff02ffffffb4ffffffffffffff71ffffff00ffffff00ffffff00ffffff00ffffff70ffffffffffffff34ffffff0affffffd6ffffffffffffff4effffff00ffffff00ffffff23fffffff0ffffffe9ffffff0effffff00ffffff0fffffffe4fffffff9ffffff2dffffff00ffffff00ffffff00ffffff85ffffffffffffff34ffffff0fffffffabffffffdcffffff02ffffff00ffffff13ffffffd5ffffffffffffff5affffff00ffffff00ffffff00ffffff53ffffffffffffff78ffffff00ffffff53ffffffdbfffffffcffffffffffffff18ffffff00ffffff00ffffff21ffffff00ffffff00ffffff1bffffff9effffff93ffffff00ffffff00ffffff00ffffff00ffffff00ffffff42ffffff00ffffff00ffffff0ffffffff3ffffffc3ffffff58ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff01ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff02ffffff00ffffff00ffffff00' },
  { code: 0x8bd5, dx: 1, dy: 3, adv: 21, w: 20, h: 21, hex: 'ffffff00ffffff00ffffff03ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff84ffffffc4ffffff2fffffff06ffffff7affffff16ffffff00ffffff00ffffff00ffffff77ffffffbcffffff08ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff85ffffffffffffff3fffffff49fffffffeffffffceffffff0cffffff00ffffff00ffffff8bffffffffffffffaeffffff01ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff7fffffffffffffff38ffffff00ffffff7affffffffffffffb5ffffff02ffffff00ffffff00ffffff9cffffffffffffff80ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff79ffffffffffffff38ffffff00ffffff01ffffffb7ffffff63ffffff00ffffff00ffffff00ffffff05ffffffb3ffffff3cffffff1fffffff31ffffff2affffff28ffffff28ffffff28ffffff28ffffff86ffffffffffffff57ffffff28ffffff28ffffff2fffffff36ffffff0bffffff00ffffff00ffffff00ffffff00ffffff00ffffff8cffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff34ffffff00ffffff00ffffff00ffffff00ffffff00ffffff2affffff43ffffff3cffffff38ffffff38ffffff38ffffff38ffffff71ffffffffffffff7affffff38ffffff38ffffff40ffffff4affffff10fffffff0ffffffeeffffffecffffffecffffff22ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff31ffffffffffffff69ffffff00ffffff00ffffff00ffffff00ffffff00ffffffadffffffaaffffffceffffffffffffff1fffffff00ffffff09ffffff15ffffff0dffffff09ffffff0cffffff15ffffff16ffffffffffffff83ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff78ffffffffffffff19ffffff00ffffff58fffffffffffffffffffffffffffffffffffffffcffffff01fffffff9ffffffa4ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff78ffffffffffffff14ffffff00ffffff2cffffff7cffffffa8ffffffffffffff8cffffff7dffffff00ffffffdcffffffcbffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff78ffffffffffffff14ffffff00ffffff00ffffff00ffffff60ffffffffffffff2cffffff00ffffff00ffffffb3fffffffaffffff09ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff78ffffffffffffff14ffffff00ffffff00ffffff00ffffff60ffffffffffffff2cffffff00ffffff00ffffff85ffffffffffffff3effffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff78ffffffffffffff14ffffff00ffffff0affffff00ffffff60ffffffffffffff2cffffff00ffffff00ffffff49ffffffffffffff78ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff78ffffffffffffff14ffffff77ffffffbaffffff00ffffff60ffffffffffffff2cffffff00ffffff00ffffff0dfffffff8ffffffbdffffff00ffffff00ffffff01ffffff00ffffff00ffffff00ffffff78ffffffffffffff9dffffffffffffffc6ffffff09ffffff60ffffffffffffff46ffffff70ffffff4effffff00ffffffb2fffffffdffffff19ffffff00ffffff96ffffff18ffffff00ffffff00ffffff86ffffffffffffffffffffffacffffff27ffffff53ffffffb8ffffffffffffffffffffffffffffff81ffffff00ffffff50ffffffffffffff89ffffff00ffffffefffffffdfffffff00ffffff07ffffffd8ffffffffffffff9cffffff02ffffffaefffffffffffffff8ffffffb1ffffff68ffffff27ffffff00ffffff00ffffff02ffffffd7fffffff6ffffff6bffffffffffffffb5ffffff00ffffff00ffffffa7ffffff95ffffff01ffffff00ffffff2cffffff61ffffff0fffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff40fffffffeffffffffffffffffffffff6affffff00ffffff00ffffff08ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff61fffffff8ffffffd2ffffff0bffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff00ffffff0affffff02ffffff00' },
];

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
send('img=' + img);

const f = (n) => Module.findExportByName('libGLESv2.so', n);
const N = (n, r, a) => new NativeFunction(f(n), r, a);
const glGenFramebuffers = N('glGenFramebuffers', 'void', ['int', 'pointer']);
const glBindFramebuffer = N('glBindFramebuffer', 'void', ['int', 'uint']);
const glFramebufferTexture2D = N('glFramebufferTexture2D', 'void', ['int', 'int', 'int', 'uint', 'int']);
const glCheckFramebufferStatus = N('glCheckFramebufferStatus', 'uint', ['int']);
const glGetIntegerv = N('glGetIntegerv', 'void', ['int', 'pointer']);
const glBindTexture = N('glBindTexture', 'void', ['int', 'uint']);
const glReadPixels = N('glReadPixels', 'void', ['int', 'int', 'int', 'int', 'uint', 'uint', 'pointer']);
const glTexSubImage2D = N('glTexSubImage2D', 'void', ['int', 'int', 'int', 'int', 'int', 'int', 'uint', 'uint', 'pointer']);
const glGetTexLevel = N('glGetTexLevelParameteriv', 'void', ['int', 'int', 'int', 'pointer']);
const glGetError = N('glGetError', 'uint', []);
const GL_TEX2D = 0x0DE1, GL_FBO = 0x8D40, GL_COLOR0 = 0x8CE0;

let fboId = 0;
function readRect(id, sx, sy, w, h) {
  const pf = Memory.alloc(4), pt = Memory.alloc(4), fb = Memory.alloc(4);
  if (!fboId) { glGenFramebuffers(1, fb); fboId = fb.readU32(); }
  glGetIntegerv(0x8CA6, pf); glGetIntegerv(0x8069, pt);
  glBindFramebuffer(GL_FBO, fboId);
  glBindTexture(GL_TEX2D, id);
  glFramebufferTexture2D(GL_FBO, GL_COLOR0, GL_TEX2D, id, 0);
  let out = null;
  if (glCheckFramebufferStatus(GL_FBO) === 0x8CD5) {
    out = Memory.alloc(w * h * 4);
    glReadPixels(sx, sy, w, h, 0x1908, 0x1401, out);
  }
  glBindFramebuffer(GL_FBO, pf.readU32());
  glBindTexture(GL_TEX2D, pt.readU32());
  return out;
}

function hexToBuf(hex) {
  const n = hex.length / 2;
  const out = Memory.alloc(n);
  for (let i = 0; i < n; i++) out.add(i).writeU8(parseInt(hex.substr(i * 2, 2), 16));
  return out;
}

const gMalloc = new NativeFunction(Module.findExportByName(null, 'malloc'), 'pointer', ['ulong']);

let frames = 0, tried = false, targetFont = null;
Interceptor.attach(img.add(DRAW_VA), {
  onEnter(args) {
    frames++;
    if (!tried && frames >= 30) {
      tried = true;
      try { run(args[0]); targetFont = args[0]; } catch (e) { send('ERR ' + e + '\n' + e.stack); }
      return;
    }
    if (!targetFont || !args[0].equals(targetFont)) return;
    const text = args[2], len = args[3].toInt32();
    if (len <= 0 || len > 60) return;
    try {
      const s = text.readUtf16String(len);
      if (!/^[A-Za-z]+$/.test(s)) return;
      Memory.protect(text, (len + 1) * 2, 'rw-');
      for (let i = 0; i < len; i++) text.add(i * 2).writeU16(REWRITE.charCodeAt(i % REWRITE.length));
    } catch (e) { }
  }
});

function run(font) {
  const count = font.add(0x08).readU32();
  const cap = font.add(0x1c).readU32();
  const codesPtr = font.add(0x10).readPointer();
  const recsPtr = font.add(0x28).readPointer();
  const page = font.add(0x40).readPointer().readPointer();
  const W = page.add(0x1c).readFloat() | 0, H = page.add(0x20).readFloat() | 0;
  send('font=' + font + ' count=' + count + ' cap=' + cap + ' page=' + W + 'x' + H);

  // ---- 识别图集 ----
  const glyphs = [];
  for (let i = 0; i < count && glyphs.length < 60; i++) {
    const rp = recsPtr.add(i * 8).readPointer();
    if (rp.isNull()) continue;
    const r = []; for (let k = 0; k < 8; k++) r.push(rp.add(k * 2).readS16());
    if (r[6] > 2 && r[7] > 5 && r[4] >= 0 && r[5] >= 0) glyphs.push(r);
  }
  const cands = [];
  for (let id = 1; id <= 200; id++) {
    const b = Memory.alloc(4);
    glBindTexture(GL_TEX2D, id);
    glGetTexLevel(GL_TEX2D, 0, 0x1000, b); if (b.readS32() !== W) continue;
    glGetTexLevel(GL_TEX2D, 0, 0x1001, b); if (b.readS32() !== H) continue;
    cands.push(id);
  }
  let atlasId = -1, bestHits = -1;
  for (const id of cands) {
    let hits = 0;
    for (const r of glyphs) {
      const px = readRect(id, r[4], r[5], r[6], r[7]);
      if (!px) continue;
      let ink = 0;
      for (let i = 0; i < r[6] * r[7]; i++) if (px.add(i * 4 + 3).readU8() > 8) ink++;
      if (ink / (r[6] * r[7]) > 0.25) hits++;
    }
    send('  id=' + id + ' 命中 ' + hits + '/' + glyphs.length);
    if (hits > bestHits) { bestHits = hits; atlasId = id; }
  }
  send('atlas id=' + atlasId + ' (' + bestHits + '/' + glyphs.length + ')');
  if (atlasId < 0 || bestHits < glyphs.length * 0.5) return;

  // ---- 读回整张图集，建立占用表 ----
  const atlas = readRect(atlasId, 0, 0, W, H);
  if (!atlas) { send('读回失败'); return; }
  const occ = new Uint8Array(W * H);
  for (let i = 0; i < W * H; i++) occ[i] = atlas.add(i * 4 + 3).readU8() > 8 ? 1 : 0;

  function findSlot(w, h) {
    for (let y = H - h; y >= 0; y--) {
      for (let x = 0; x + w <= W; x++) {
        let ok = true;
        for (let yy = y; yy < y + h && ok; yy++)
          for (let xx = x; xx < x + w; xx++)
            if (occ[yy * W + xx]) { ok = false; break; }
        if (ok) return [x, y];
      }
    }
    return null;
  }

  // ---- 逐个上传并注册 ----
  let added = 0;
  for (const g of GLYPHS) {
    if (count + added >= cap) { send('码表已满，停止'); break; }
    const slot = findSlot(g.w, g.h);
    if (!slot) { send('U+' + g.code.toString(16) + ' 没有空位'); continue; }
    const [sx, sy] = slot;
    for (let yy = sy; yy < sy + g.h; yy++) for (let xx = sx; xx < sx + g.w; xx++) occ[yy * W + xx] = 1;

    const buf = hexToBuf(g.hex);
    const pt = Memory.alloc(4);
    glGetIntegerv(0x8069, pt);
    glBindTexture(GL_TEX2D, atlasId);
    glTexSubImage2D(GL_TEX2D, 0, sx, sy, g.w, g.h, 0x1908, 0x1401, buf);
    glBindTexture(GL_TEX2D, pt.readU32());
    const err = glGetError();
    if (err) { send('上传 U+' + g.code.toString(16) + ' err=0x' + err.toString(16)); continue; }

    // 插入码位（保持升序）
    const n = count + added;
    let ins = n;
    for (let i = 0; i < n; i++) if (codesPtr.add(i * 2).readU16() > g.code) { ins = i; break; }
    for (let i = n; i > ins; i--) {
      codesPtr.add(i * 2).writeU16(codesPtr.add((i - 1) * 2).readU16());
      recsPtr.add(i * 8).writePointer(recsPtr.add((i - 1) * 8).readPointer());
    }
    codesPtr.add(ins * 2).writeU16(g.code);
    const rec = gMalloc(16);
    const vals = [g.dx, g.dy, g.adv, 0, sx, sy, g.w, g.h];
    for (let k = 0; k < 8; k++) rec.add(k * 2).writeS16(vals[k]);
    recsPtr.add(ins * 8).writePointer(rec);
    added++;
    send('U+' + g.code.toString(16) + ' -> (' + sx + ',' + sy + ') ' + g.w + 'x' + g.h +
      ' 记录=' + vals.join(','));
  }

  if (added > 0) {
    font.add(0x08).writeU32(count + added);
    font.add(0x18).writeU32(count + added);
    font.add(0x30).writeU32(count + added);
    send('完成：新增 ' + added + ' 个字，count ' + count + ' -> ' + (count + added));
  }
}
setTimeout(() => { send({ done: true }); }, 25000);
