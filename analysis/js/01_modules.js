// 第一步：看看进程里到底有哪些模块，s3e 镜像在哪
const mods = Process.enumerateModules();
send("模块数: " + mods.length);
mods.sort((a, b) => b.size - a.size);
for (const m of mods.slice(0, 25)) {
  send(`  ${m.name.padEnd(42)} base=${m.base} size=0x${m.size.toString(16)} path=${m.path}`);
}

// 找带 s3e / majesty 的
send("--- 可疑模块 ---");
for (const m of mods) {
  const n = (m.name + m.path).toLowerCase();
  if (n.includes("s3e") || n.includes("majesty") || n.includes("herocraft")) {
    send(`  ${m.name} base=${m.base} size=0x${m.size.toString(16)}`);
  }
}
send({ done: true });
