// 探针：列出所有绑定过的 2D 纹理及其尺寸
const getTexLevel = new NativeFunction(Module.findExportByName('libGLESv2.so', 'glGetTexLevelParameteriv'), 'void', ['int', 'int', 'int', 'pointer']);
const buf = Memory.alloc(16);
const seen = {};
let n = 0;
Interceptor.attach(Module.findExportByName('libGLESv2.so', 'glBindTexture'), {
  onEnter(args) {
    const tgt = args[0].toInt32(), id = args[1].toInt32();
    if (tgt !== 0x0DE1 || id === 0) return;
    if (seen[id]) return;
    seen[id] = 1;
    if (n >= 40) return;
    n++;
    getTexLevel(0x0DE1, 0, 0x1000, buf);
    const w = buf.readS32();
    getTexLevel(0x0DE1, 0, 0x1001, buf);
    const h = buf.readS32();
    send('bind id=' + id + ' ' + w + 'x' + h);
  }
});
setTimeout(() => { send({ done: true }); }, 8000);
