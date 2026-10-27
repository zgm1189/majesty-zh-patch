// 用多处签名验证 file_offset -> memory_offset 的映射
const REGION = ptr('0x758cf8b000');
const SIZE = 0x586000;

// 从本地 bin 里取几处 24 字节签名（由 Python 生成后替换）
const SIGS = [{"off": 327680, "hex": "91 84 02 06 cb 84 fc 41 d3 84 04 00 91 9f 38 00 f1 29 0f 00 54 00 4b 00"}, {"off": 589824, "hex": "a9 21 00 0e 91 01 00 00 f9 f5 03 00 aa 61 f6 ff 97 81 25 00 90 e0 03 15"}, {"off": 1179648, "hex": "79 25 01 66 9e bf 00 04 eb 80 19 00 54 05 0c 40 79 04 20 00 91 e5 0c 00"}, {"off": 1703936, "hex": "97 00 1c 00 53 80 ea ff 34 ee ff ff 17 a1 16 00 d0 e0 03 14 aa 21 60 3f"}, {"off": 2424832, "hex": "aa e0 03 02 91 4c 8a ff 97 fa ff ff 17 f4 03 00 aa e0 03 15 aa 48 8a ff"}, {"off": 3145728, "hex": "b0 e0 03 13 aa 21 00 1e 91 61 02 00 f9 33 24 fc 97 e0 03 13 aa fe 0b 40"}, {"off": 3801088, "hex": "91 21 80 31 91 e0 c3 00 91 8e c5 f7 97 f3 1b 40 f9 f8 fe ff 17 c2 06 00"}, {"off": 4194304, "hex": "f9 c0 f3 ff b5 a6 ff ff 17 21 01 66 9e 43 01 66 9e 20 fc 41 93 01 6b 60"}, {"off": 4587520, "hex": "20 64 6f 74 28 56 45 52 54 5f 43 4f 4c 2e 72 67 62 20 2d 20 76 65 63 33"}, {"off": 5373952, "hex": "00 05 00 00 00 00 00 00 00 88 d6 46 4a 00 00 00 00 05 00 00 00 08 00 00"}];

for (const s of SIGS) {
  const hits = Memory.scanSync(REGION, SIZE, s.hex);
  if (!hits.length) { send(`file@0x${s.off.toString(16)} 未命中`); continue; }
  const memOff = hits[0].address.sub(REGION);
  send(`file@0x${s.off.toString(16)} -> mem@0x${memOff.toString(16)}  delta=0x${s.off - memOff.toUInt32()}`);
}
send({ done: true });
