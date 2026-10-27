#!/usr/bin/env python3
"""纯拼音方案 · 第三批：关卡名(sL*) · 任务目标(sTask*) · 教程提示(stHint*) · 地图说明(mnu*)。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(r"D:\project\逆向\北方的扩张")
TDAT = ROOT / "build" / "assets" / "translate.dat"

PY3: dict[str, str] = {
    # ================= 关卡名 sL* =================
    "sL0": "JiaoCheng",
    "sL1": "1. ShengNvBaoDong",
    "sL2": "2. MoShuiWeiJi",
    "sL3": "3. JiaZhiHuangJinDeBingGan",
    "sL4": "4. XiXueGuiFuShuangBei",
    "sL5": "5. GeBuLinDouYiYang",
    "sL6": "6. BeiFangYangShengQu",
    "sL7": "7. ShenDuBingFeng",
    "sL8": "8. QianNianJuLong",
    "sL9": "9. ShuiShouWeiJi",
    "sL10": "10. RenKouGuoSheng",
    "sL11": "11. HuangJinDiShi",
    "sL12": "12. DaoDeLunSang",
    "sL13": "13. HaiGuTaiDuo",
    "sL14": "14. AiRenYuLe",
    "sL15": "15. LiYiChongTu",
    "sL16": "16. ZiYouZhuYiBaoDong",
    # ================= 任务目标 sTask* =================
    "sTaskHead": "MuBiao",
    "sTaskL1": "JiBaiPanLuanDeShengNv.",
    "sTaskL3": "CuiHuiFengKuangWuShiZhiTa.",
    "sTaskL4": "CuiHuiXiXueGuiChengBao.",
    "sTaskL5": "CuiHuiSuoYouGeBuLinJuSuo.",
    "sTaskL6": "XiaoMieSuoYouShiMoXiang.",
    "sTaskL7": "XiaoMieSuoYouJuLong.",
    "sTaskL8": "JiBaiJuLongZhiWang.",
    "sTaskL9": "XunZhaoJuLongBaoZang.",
    "sTaskL9-1": "JieChuZuZhouBingDuoQuBaoZang.",
    "sTaskL9-2": "ShiFangJuLongBingYanJiuBaoZang.",
    "sTaskL10": "CuiHuiSuoYouYiMinJuDian.",
    "sTaskL11": "ZhaoDaoBingCuiHuiXiXueGuiChengBao.",
    "sTaskL12": "JiBaiChuanShuoZhanShi.",
    "sTaskL13": "ZhaoDaoWuYaoShiDeCanHai.",
    "sTaskL13-1": "ZaiYiJiaoSiMiaoJiShaWuYaoShi.",
    "sTaskL15": "JiBaiShiMoXiangHuoJuLong.",
    # ================= 教程提示 stHint* =================
    "stHintHead": "JiaoCheng",
    "stHintHead0": "JianZhu",
    "stHintHead1": "GuYongYingXiong",
    "stHintHead2": "QiZhi",
    "stHintHead3": "ShengJiJianZhu",
    "stHintHead4": "ShiYongFaShu",
    "stHintText16": "JiaoChengDaoCiJieShu.",
    # ================= 地图/战役说明 mnu* =================
    "mnuSSM00": "XinShouTaoZhuang",
    "mnuSSM01": "WoXuanZeHeiAn",
    "mnuSSM02": "ShengMingShouHuZhe",
    "mnuSSM03": "ZhanDouFaShi",
    "mnuSSM04": "SenLinShouHuZhe",
    "mnuSSM05": "KuaiSuKaiJu",
    "mnuSSM06": "KeLuoMuJiSi",
    "mnuSSM07": "ShaoBingChengBao",
    "mnuSSM08": "ZiJianChengBao",
    "mnuSSM10": "MoFaSenLin",
    "mnuSSM11": "GeBuLinBuLuo",
    "mnuSSM12": "ZhaoZeYaoJing",
    "mnuSSM13": "WangZheZhiGu",
    "mnuSSM14": "TaTaErWeiShi",
    "mnuSSM15": "GeErGongNuQun",
    "mnuSSM20": "Fou",
    "mnuSSM21": "ShuQunXiLai",
    "mnuSSM22": "HaiGu",
    "mnuSSM23": "GeBuLinKaiLuZhe",
    "mnuSSM24": "YingShenNv",
    "mnuSSM25": "NiuTouRen",
    "mnuSSM26": "XiXueGui",
    "mnuSSM27": "MeiDuSha",
    "mnuSSM28": "ShiMoXiang",
    "mnuSSM29": "JuLong",
    "mnuSSM30": "ADaNiYaPingYuan",
    "mnuSSM31": "ZhanChang",
    "mnuSSM310": "TuZiPaDao",
    "mnuSSM311": "XueYuanPingYuan",
    "mnuSSM312": "JuLongGaoYuan",
    "mnuSSM32": "FaMu",
    "mnuSSM33": "FeiXu",
    "mnuSSM34": "JingLingSenLin",
    "mnuSSM35": "NongMinTuDi",
    "mnuSSM36": "TeLanXiWaNiYa",
    "mnuSSM37": "MoGuSenLin",
    "mnuSSM38": "SiWangZhiDi",
    "mnuSSM39": "MuDi",
    "mnuSSM4": "# HuangJin",
    "mnuSSM50": "XiaoMieDiRen",
    "mnuSSM51-4": "ShouJi # HuangJin",
    "mnuSSM55-8": "JianShou # Tian",
    "mnuSST0": "WanJiaJunLi",
    "mnuSST1": "DiFangJunLi",
    "mnuSST2": "YouDangGuaiWu",
    "mnuSST3": "DiXing",
    "mnuSST4": "QiDongZiJin",
    "mnuSST5": "ShengLiTiaoJian",
    "mnuSSH4": "# HuangJin",
    "mnuSSH06": "YiJiChengBao,KeLuoMuShenMiao",
    "mnuSSH08": "JinYouYiJiChengBao",
    "mnuSSH11": "GeBuLinZaiCiBiNan.",
    "mnuSSH21": "ZheiXieTuDiBeiLaoShuQinXi.",
    "mnuSSH23": "GeBuLinRuQinNiDeWangGuo.",
    "mnuSSH27": "MeiDuShaRuQinZheiXieTuDi.",
    "mnuSSH28": "ShiMoXiangZhiLuChuanGuoNiDeTuDi.",
    "mnuSSH29": "JuLongXiJiNiDeJuDian.",
    "mnuSSH31": "ShiBingDeXueZiXiaZhangBuChuCao.",
    "mnuSSH312": "JuLongChaoXueYuJiaoTu.",
    "mnuSSH35": "ChiBaoLeCaiHaoDaZhang.",
    "mnuSSH36": "XiXueGuiJiaYuan,HuangLiangQiLiang.",
    "mnuSSH50": "XiaoMieDiRen",
    "mnuSSH51-4": "ShouJi # HuangJin",
    "mnuSSH55-8": "JianShou # Tian",
}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    d = TDAT.read_bytes()
    recs, i = [], 0
    while i < len(d):
        n = int.from_bytes(d[i : i + 2], "big")
        i += 2
        recs.append(d[i : i + n].decode("utf-8"))
        i += n
    hit, miss = 0, set(PY3)
    out = []
    for r in recs:
        k, sep, v = r.partition(": ")
        if sep:
            stem, _, lang = k.rpartition("_")
            if stem in PY3 and lang in ("en", "de"):
                miss.discard(stem)
                r = f"{k}: {PY3[stem]}"
                hit += 1
        out.append(r)
    buf = bytearray()
    for r in out:
        b = r.encode("utf-8")
        buf += len(b).to_bytes(2, "big") + b
    TDAT.write_bytes(bytes(buf))
    print(f"改写 {hit} 条  (映射 {len(PY3)}, 未命中 {len(miss)}: {sorted(miss)})")
    print(f"写出 {len(buf)} bytes")


if __name__ == "__main__":
    main()
