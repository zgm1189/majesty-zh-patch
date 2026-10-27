#!/usr/bin/env python3
"""纯拼音方案 · 第四批：成就(acName*) · 成就描述(acText*) · 成就标题(acHead*)。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(r"D:\project\逆向\北方的扩张")
TDAT = ROOT / "build" / "assets" / "translate.dat"

PY4: dict[str, str] = {
    # ============ 标题 / 杂项 ============
    "acHead0": "YiHuoDe",
    "acHead1": "WeiHuoDe",
    "acHead2": "QuanBu",
    "acHead4": "\"RenWu\"",
    "acHead5": "\"FaShu\"",
    "acHead6": "\"JiSha\"",
    "acHead7": "\"YingXiong\"",
    "acHead8": "\"QiTa\"",
    "acLooser": "NiHaiMeiYouHuoDeRenHeChengJiu.",
    "acMessHead": "HuoDeChengJiu!",
    "acProgress": "JinDu",
    "acRoomHead": "ChengJiu",
    # ============ 成就名 ============
    "acName1": "\"QianCheng\"",
    "acName2": "\"ChaoJiShuJi\"",
    "acName3": "\"HaoGeBuLinSiGeBuLin\"",
    "acName4": "\"JinYa\"",
    "acName5": "\"ALuKaDeZhiZhu\"",
    "acName6": "\"GeBuLinBingQiLin\"",
    "acName7": "\"ShiTouJunZhu\"",
    "acName8": "\"KaoGuXueJia\"",
    "acName9": "\"TuLongZhe\"",
    "acName10": "\"TuZaiChang\"",
    "acName11": "\"ShangHaiYingEr!\"",
    "acName12": "\"HuangJinZiWei\"",
    "acName13": "\"FuNvShaShou\"",
    "acName14": "\"GaoMiZheDeGanJi\"",
    "acName15": "\"XueXingZhiQian\"",
    "acName16": "\"ADaNiYaShuYuADaNiYaRen\"",
    "acName17": "\"ZuiQinJinDeDiRen\"",
    "acName18": "\"TaMenHuoZhe!\"",
    "acName19": "\"ZunJingZhangBei\"",
    "acName20": "\"ShaHeShengCunZhe\"",
    "acName21": "\"KuaiSuShengLi\"",
    "acName22": "\"BieFangManJieZou!\"",
    "acName23": "\"LeiTingShengLi\"",
    "acName24": "\"ShiJieJiLu!\"",
    "acName25": "\"CiShanJia\"",
    "acName26": "\"QianChengTu\"",
    "acName27": "\"WangLingJun\"",
    "acName28": "\"JinJiQingKuang\"",
    "acName29": "\"ZuZhouNi!\"",
    "acName30": "\"WangLingLingZhu\"",
    "acName31": "\"LiaoKuoDiPingXian\"",
    "acName32": "\"WuShiDeZhuShou\"",
    "acName33": "\"FengBaoLingZhu\"",
    "acName34": "\"WuXingDeSiWang\"",
    "acName35": "\"LeiTingZhiJi\"",
    "acName36": "\"XieEYan\"",
    "acName37": "\"BuShuZhe\"",
    "acName38": "\"TangLiaoZhiPin\"",
    "acName39": "\"GeBuLinKeXing\"",
    "acName40": "\"ZhiZhuShaShou\"",
    "acName41": "\"FaMuGong\"",
    "acName42": "\"BuNiaoZhe\"",
    "acName43": "\"NiuRouTang\"",
    "acName44": "\"WangLingLieShou\"",
    "acName45": "\"CheDiSiTou\"",
    "acName46": "\"JiShiKanShou\"",
    "acName47": "\"WuLongDiXiaCheng\"",
    "acName48": "\"ShiMoXiangSuiLieZhe\"",
    "acName49": "\"BuZhuoFuLu\"",
    "acName50": "\"ShenShengBaoYing\"",
    "acName51": "\"JiaoTu\"",
    "acName52": "\"LaoBing\"",
    "acName53": "\"LuoBinHan\"",
    "acName54": "\"YaMaXunNvWang\"",
    "acName55": "\"DiYuDaJunJiangJun\"",
    "acName56": "\"DaBangQiuZhang\"",
    "acName57": "\"BaiFaEr\"",
    "acName58": "\"MiNiJuRen\"",
    "acName59": "\"DaFaShi\"",
    "acName60": "\"JiuShiZhu\"",
    "acName61": "\"SiWangHuaShen\"",
    "acName62": "\"GuanJunJiaoLian\"",
    "acName63": "\"XinBingLieShou\"",
    "acName64": "\"FuQinZhiHuiGuan\"",
    "acName65": "\"BuLuoZhiZhu\"",
    "acName66": "\"PengYouMuDi\"",
    "acName67": "\"DiDong\"",
    "acName68": "\"YanShiZhe\"",
    "acName69": "\"RongYuShiJiang\"",
    "acName70": "\"ChengZhenJianZaoZhe\"",
    "acName71": "\"WeiDaJianZhuShi\"",
    "acName72": "\"ManYouZhe\"",
    "acName73": "\"LuXingZhe\"",
    "acName74": "\"TanXianZhe\"",
    "acName75": "\"JingJiXueJia\"",
    "acName76": "\"LingRenXianMuDeXinLang\"",
    "acName77": "\"JinRongJia\"",
    "acName78": "\"LiXiangZhanLueJia\"",
    "acName79": "\"CheTuiShiKe\"",
    "acName80": "\"ShiBaiDeZhanZheng\"",
    "acName81": "\"ZuiChaDeGuoWang\"",
    "acName104": "\"HeLaKeLeSi\"",
    "acName105": "\"PoErXiuSi\"",
    "acName106": "\"ShiJiShuiShou\"",
    "acName107": "\"WuQing\"",
    "acName108": "\"YiZuYingXiong\"",
    "acName109": "\"ZhengYiTianPing\"",
    "acName110": "\"LueDuoZhe\"",
    "acName111": "\"GuanJunLieShou\"",
    "acName112": "\"YiHuoYuJian\"",
    "acName113": "\"MuDiKanShou\"",
    "acName114": "\"TuPiDaYi\"",
    "acName115": "\"TieBang\"",
    "acName116": "\"WoDeBuXuBieRenDong\"",
    "acName117": "\"ChiBangYuWeiBa\"",
    "acName118": "\"ShiTouJiangBei\"",
    "acName119": "\"DuCaiZhe\"",
    "acName120": "\"WeiXiaoDeChengFa\"",
    # ============ 成就描述 ============
    "acText1": "WanCheng {0} GeRenWu.",
    "acText2": "WanChengJiaoChengGuanQia.",
    "acText3": "Zai {0} TianNeiWanCheng 2 GeRenWu.",
    "acText4": "Zai {0} TianNeiWanCheng 4 GeRenWu.",
    "acText5": "Zai {0} TianNeiWanCheng 7 GeRenWu.",
    "acText6": "Zai {0} TianNeiWanChengYouXi.",
    "acText7": "MeiJuYouXiShiYong\"{0}\"{1}Ci.",
    "acText8": "JiSha {0} ZhiJuShu.",
    "acText9": "JiSha {0} GeHaiGu.",
    "acText10": "JiSha {0} GeGeBuLin.",
    "acText11": "JiSha {0} ZhiMoWangZhiZhu.",
    "acText12": "JiSha {0} ZhiMoShu.",
    "acText13": "JiSha {0} ZhiYingShenNv.",
    "acText14": "JiSha {0} ZhiNiuTouRen.",
    "acText15": "JiSha {0} GeXiXueGui.",
    "acText16": "JiSha {0} GeJiangShi.",
    "acText17": "JiSha {0} GeZhaoZeYaoJing.",
    "acText18": "JiSha {0} TiaoJuLong.",
    "acText19": "JiSha {0} GeShiMoXiang.",
    "acText20": "ZaiYouXiZhongJiSha {0} GeDiRen.",
    "acText21": "BaZhanShiShengJiDao {0} Ji.",
    "acText22": "BaYouXiaShengJiDao {0} Ji.",
    "acText23": "BaShengQiShiShengJiDao {0} Ji.",
    "acText24": "BaBuHeZhiZhanShiShengJiDao {0} Ji.",
    "acText25": "BaYeManRenShengJiDao {0} Ji.",
    "acText26": "BaJingLingShengJiDao {0} Ji.",
    "acText27": "BaAiRenShengJiDao {0} Ji.",
    "acText28": "BaWuShiShengJiDao {0} Ji.",
    "acText29": "BaZhiLiaoWuShiShengJiDao {0} Ji.",
    "acText30": "BaWuYaoShiShengJiDao {0} Ji.",
    "acText31": "BaSuoYouYingXiongShengJiDao 20 Ji.",
    "acText32": "GuYong {0} MingYingXiong.",
    "acText33": "{0} MingYingXiongZhenWang.",
    "acText34": "JianZao {0} ZuoJianZhu.",
    "acText35": "TanSuo {0} ZhangDiTu.",
    "acText36": "TanSuo {0} ZhangDiTu.",
    "acText37": "TanSuo {0} ZhangDiTu.",
    "acText38": "MeiGuanHuoDe {0} HuangJin.",
    "acText39": "CongWeiShiBai.",
    "acText40": "ShiBai {0} Ci.",
    "acText41": "ShiFangWuYaoShi.",
    "acText42": "CuiHuiGeBuLin.",
    "acText43": "CuiHuiNiuTouRen.",
    "acText44": "CuiHuiAiRen.",
    "acText45": "JiBaiJuLongZhiWang.",
    "acText46": "JiSha {0} GeMeiDuSha.",
    "acText47": "WanCheng\"ShuiShouWeiJi\"RenWu.",
    "acText48": "Zai\"ShuiShouWeiJi\"ZhongJiBaiJuLong.",
    "acText49": "WanCheng\"RenKouGuoSheng\"RenWu.",
    "acText50": "WanCheng\"HuangJinDiShi\"RenWu.",
    "acText51": "Zai\"HuangJinDiShi\"ZhongCuiHuiSuoYouJinKu.",
    "acText52": "WanCheng\"DaoDeLunSang\"RenWu.",
    "acText53": "Zai\"DaoDeLunSang\"ZhongCuiHuiSuoYouDiDuiGongHui.",
    "acText54": "WanCheng\"HaiGuTaiDuo\"RenWu.",
    "acText55": "Zai\"HaiGuTaiDuo\"ZhongJiBai 30 ZhiTuZi.",
    "acText56": "Zai\"AiRenYuLe\"ZhongJiBaiSuoYouAiRen.",
    "acText57": "Zai\"AiRenYuLe\"ZhongCuiHuiSuoYouChaoXue.",
    "acText58": "WanCheng\"LiYiChongTu\"BingCuiHuiJuLong.",
    "acText59": "WanCheng\"LiYiChongTu\"BingCuiHuiShiMoXiang.",
    "acText60": "WanCheng\"ZiYouZhuYiBaoDong\"RenWu.",
    "acText61": "Zai\"ZiYouZhuYiBaoDong\"ZhongCuiHuiSuoYouZhuRuXiaoWu.",
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
    hit, miss = 0, set(PY4)
    out = []
    for r in recs:
        k, sep, v = r.partition(": ")
        if sep:
            stem, _, lang = k.rpartition("_")
            if stem in PY4 and lang in ("en", "de"):
                miss.discard(stem)
                r = f"{k}: {PY4[stem]}"
                hit += 1
        out.append(r)
    buf = bytearray()
    for r in out:
        b = r.encode("utf-8")
        buf += len(b).to_bytes(2, "big") + b
    TDAT.write_bytes(bytes(buf))
    print(f"改写 {hit} 条  (映射 {len(PY4)}, 未命中 {len(miss)}: {sorted(miss)})")
    print(f"写出 {len(buf)} bytes")


if __name__ == "__main__":
    main()
