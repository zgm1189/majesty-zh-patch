#!/usr/bin/env python3
"""纯拼音方案：把 UI 核心词条的英文（_en）改写为拼音。

字体完全不动 —— 拼音只用 a-z，全都在 fntM0 的 ASCII 槽位里。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(r"D:\project\逆向\北方的扩张")
TDAT = ROOT / "build" / "assets" / "translate.dat"

# 英文 -> 拼音。`{0}` 占位符、`^` 换行符原样保留。
PY: dict[str, str] = {
    # ---- 通用词 ----
    "kOk": "QueDing",
    "kCancel": "QuXiao",
    "kArmor": "FangYu",
    "kPotions": "HuiFuYaoShui",
    "kRingProt": "BaoHuJieZhi",
    "kTlprt": "ChuanSong",
    "kAmTel": "ChuanSongHuFu",
    "kResearch": "YanJiu",
    "kResist": "KangXing",
    "kDodge": "ShanBi",
    "kMResist": "MoFaKangXing",
    "kUMagic": "MoFaKangXing",
    "kFBall": "HuoQiu",
    "kFBlast": "HuoYanBao",
    "kFShld": "HuoDun",
    "kMStorm": "YunShiYu",
    "kMrktDay": "JiShiRi",
    "kBldngs": "RenWu",
    "kNoConnection": "WuWangLuo.QingJianChaSheZhi.",
    "kAvaliableInFullVersion": "XuWanZhengBan",
    "kMissionCompleteDiff": "NanDuDengJi",
    # ---- 难度 ----
    "kDiffLevel0": "HePingZhuYi",
    "kDiffLevel1": "TiaoTingZhe",
    "kDiffLevel2": "ShiXueZhe",
    # ---- 主菜单 / 导航 ----
    "kdMainMenu": "ZhuCaiDan",
    "kdPlay": "KaiShi",
    "kdLoad": "ZaiRu",
    "kdSave": "BaoCun",
    "kdOptions": "SheZhi",
    "kdExit": "TuiChu",
    "kdBack": "FanHui",
    "kdContinue": "JiXu",
    "kdProfile": "DangAn",
    "kdCreateProfile": "ChuangJian",
    "kdNewGame": "ShanChuJinDu",
    "kdCampaign": "ZhanYi",
    "kdSkirmish": "ZaoYuZhan",
    "kdAchivements": "ChengJiu",
    "kdAwards": "JiangZhang",
    "kdScores": "JiFen",
    "kdAbout": "GuanYu",
    "kdInfo": "BangZhu",
    "kdHelp": "TiShi",
    "kdTask": "MuBiao",
    "kdEndMission": "JieShu",
    "kdRestartLevelQ": "ChongXinKaiShiRenWu?",
    "kdChangeLogHead": "ZhuYi!",
    # ---- 设置项 ----
    "kdSound": "YinXiao",
    "kdMusic": "YinYue",
    "kdLanguage": "YuYan",
    "kdOn": "Kai",
    "kdOff": "Guan",
    "kdSoundQ": "KaiQiYinXiao?",
    # ---- 帮助分类 ----
    "kdHelpBuildingCh": "JianZhu",
    "kdHelpHeroCh": "YingXiong",
    "kdHelpMagicCh": "FaShu",
    "kdHelpMonsterCh": "GuaiWu",
    "kdHelpOtherCh": "JiChu",
    # ---- 确认框（精简拼音）----
    "kdExitQ": "QueDingTuiChuYouXi?",
    "kdExitMissionQ": "JieShuRenWu?",
    "kdExitToMainMenuQ": "FanHuiZhuCaiDan?",
    "kdLoadQ": "QueDingZaiRuYouXi?",
    "kdLoadQ2": "DangQianRenWuJiangZhongDuan.",
    "kdNewGameQ": "QueDingShanChuJinDu?",
    "kdErrorProfileEql": "DangAn\"{0}\"YiCunZai!",
    "kdProfileDeleteQ": "QueDingShanChuDangAn\"{0}\"?",
    "kdError": "CuoWu!",
    # ---- 其他菜单项 ----
    "kdLocalRecords": "BenDi",
    "kdOnline": "ZaiXian",
    "kdMoreGames": "GengDuoYouXi",
    "kdScreenShot": "JieTu",
    "kdTalks": "TaoLun",
    "kdTellAFriend": "GaoSuPengYou",
    "kdSendSMS": "ChongZhiGuoKu",
    "kdSynchGame": "TongBu",
    "kdSynchGameQ": "TongBuYouXiJinDu?",
    "kdAchSincQ": "HuoDeXinChengJiu!^YaoFaSongMa?",
    "kdPurchaseHead": "BaoGao",
    "kdPurchaseOk": "GouMaiChengGong.",
    "kdPurchaseFail": "GouMaiShiChuCuo.",
    "kdPurchaseGoldFail": "GouMaiJinBiShiChuCuo.",
    "kdPurchaseLevelFail": "GouMaiShiChuCuo.",
    "kdPurchaseLevelQ": "YongMoFaYaoShiJieSuoQuanBuGuanQia?",
    "kdYourCraft": "NiDeZuoPin",
    # ---- 界面提示 ----
    "uiAutoSave": "ZiDongBaoCun",
    "uiPlayMode": "XuanZeYouXiMoShi",
    "uiRestartLevel": "ChongXinKaiShiGuanQia",
    "uiWeather": "TianQi",
    "uiChooseSlot": "XuanZeDangWei",
    "uiEmptySlot": "KongDangWei",
    "uiCheats": "BiShaJi",
    "uiNotEnoughCrystals": "ShuiJingBuZu.",
    "uiBuyCrystalsQ": "GouMai{0}GeShuiJing?",
    "uiBuyCrystalsQ1": "YongDuanXinGouMai{0}GeShuiJing?",
    "uiBuyCrystalsTitle": "GouMai",
    "uiBuyCrystalsTxt": "ShuiJing",
    "uiGetCheatQ": "Hua{0}ShuiJingJiHuo?",
    # ---- 作弊项 ----
    "uiCheatName0": "BuSiShuiWuGuan",
    "uiCheatName1": "KuaiSuJianZao",
    "uiCheatName2": "LaoBing",
    "uiCheatName3": "QingSongShengJi",
    "uiCheatName4": "JianGuChengQiang",
    "uiCheatName5": "JianTa",
    "uiCheatName6": "JieSuoDiTu",
    "uiCheatName7": "LiXiangChengBao",
    "uiCheatName8": "KuaiSuGuYong",
    "uiCheatName10": "QiangDaSiLing",
    "uiCheatName11": "GengDuoYingXiong",
    "uiCheatName12": "KuanChangGongHui",
    "uiCheatName13": "ZhuangJinBaoXiang",
    "uiCheatTxt7": "Yi3JiChengBaoKaiShiYouXi.",
    "uiCheatTxt8": "YingXiongLiJiGuYong.",
    "uiCheatTxt13": "HuoDe10000JinBi.",
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

    hit = 0
    out = []
    for r in recs:
        k, sep, v = r.partition(": ")
        if sep:
            stem, _, lang = k.rpartition("_")
            if lang in ("en", "de") and stem in PY:
                if lang == "en":
                    print(f"  {stem:26s} {v[:42]:44s} -> {PY[stem]}")
                r = f"{k}: {PY[stem]}"
                hit += 1
        out.append(r)

    buf = bytearray()
    for r in out:
        b = r.encode("utf-8")
        buf += len(b).to_bytes(2, "big") + b
    TDAT.write_bytes(bytes(buf))
    print(f"\n改写 {hit} / {len(PY)} 条   写出 {len(buf)} bytes")


if __name__ == "__main__":
    main()
