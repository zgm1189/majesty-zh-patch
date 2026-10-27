#!/usr/bin/env python3
"""纯拼音方案 · 第二批：武器/护甲(sn*) · 法术(sm*) · 建筑与单位名(h*)。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(r"D:\project\逆向\北方的扩张")
TDAT = ROOT / "build" / "assets" / "translate.dat"

PY2: dict[str, str] = {
    # ================= 武器 snWeapon* =================
    "snWeapon": "WuQi",
    "snWeapon0": "DuanJian",
    "snWeapon1": "KuoJian",
    "snWeapon2": "ZaZhongJian",
    "snWeapon3": "GangZhiZaJian",
    "snWeapon4": "ChangGong",
    "snWeapon5": "JingZhiChangGong",
    "snWeapon6": "ZiShanChangGong",
    "snWeapon7": "FuHeChangGong",
    "snWeapon8": "RenGun",
    "snWeapon9": "FengLiRenGun",
    "snWeapon10": "HunDunRenGun",
    "snWeapon11": "ChuanShuoHunDunGun",
    "snWeapon12": "FuTou",
    "snWeapon13": "ZhongFu",
    "snWeapon14": "KuoFu",
    "snWeapon15": "ZhanFu",
    "snWeapon16": "ChuiZi",
    "snWeapon17": "GangChui",
    "snWeapon18": "ZhanChui",
    "snWeapon19": "ZhongZhanChui",
    "snWeapon20": "ShengMingZhang",
    "snWeapon21": "YingYingZhang",
    "snWeapon22": "ZhanDouZhang",
    # ================= 护甲 snArmor* =================
    "snArmor": "HuJia",
    "snArmor0": "WuHuJia",
    "snArmor1": "BanJia",
    "snArmor2": "ZhongBanJia",
    "snArmor3": "GangBanJia",
    "snArmor4": "MiYinBanJia",
    "snArmor5": "RuanPiJia",
    "snArmor6": "YingPiJia",
    "snArmor7": "XiangDingPiJia",
    "snArmor8": "SuoZiJia",
    "snArmor9": "PiJia",
    "snArmor10": "FengRenJia",
    "snArmor11": "HunDunJia",
    "snArmor12": "ChaoJiHunDunJia",
    "snArmor13": "TieSuoJia",
    "snArmor14": "GangSuoJia",
    "snArmor15": "QiangHuaSuoJia",
    "snArmor16": "MiYinSuoJia",
    # ================= 杂项/卷轴 =================
    "snPotions": "ZhiLiaoYaoShui",
    "snCasts": "FaShu",
    "snEffects": "FuMo",
    "snThings": "ZaXiang",
    "snInvis": "YinShenJuanZhou",
    "snCamuflage": "WeiZhuangJuanZhou",
    "snEnBlst": "NengLiangBaoJuanZhou",
    "snFireBlst": "HuoYanBaoJuanZhou",
    "snAmTel": "ChuanSongHuFu",
    # ================= 法术 sm* =================
    "sm1": "ChuanSong",
    "sm2": "WeiZhuang",
    "sm3": "ZhiLiao",
    "sm4": "MingXiang",
    "sm5": "HePingGuangHuan",
    "sm6": "XiQuShengMing",
    "sm7": "ZhaoHuanHaiGu",
    "sm8": "KongZhiWangLing",
    "sm9": "NengLiangBao",
    "sm10": "HuoDun",
    "sm11": "HuoYanBao",
    "sm13": "HuoQiu",
    "sm14": "MoFaKangXing",
    "sm15": "YunShiYu",
    "sm16": "GuangMingZhiDun",
    "sm18": "ZhuFu",
    "sm19": "FuHuo",
    "sm20": "KuWei",
    "sm22": "FuSheng",
    "sm23": "TanSuo",
    "sm24": "YinShen",
    "sm25": "ShanDian",
    "sm26": "FanMoFa",
    "sm27": "ShanDianFengBao",
    "sm28": "ChaoJiChongNeng",
    "sm29": "KeLuoMuZhiNu",
    "smScores": "JiFen",
    "smSelectMission": "XuanZeRenWu",
    "smLockedMission": "GuanQiaWeiJieSuo.QingXianWanChengQianYiGuan.",
    "smUseMagicKey": "HuoYongMoFaYaoShiJieSuoQuanBuGuanQia.",
    # ================= 建筑/单位 h* =================
    "hAgrella": "AGeLieLaShenMiao",
    "hAwExpl": "ZhenChaQi",
    "hAwKill": "GongJiQi",
    "hAws": "JiangZhang",
    "hBlcksmth": "TieJiangPu",
    "hCanaliz": "XiaShuiDaoKou",
    "hCrypta": "KeLiPuTaShenMiao",
    "hDrgnFrzn": "BingFengJuLong",
    "hDwarfT": "AiRenTa",
    "hDwarfW": "AiRenYaoSai",
    "hElfBung": "JingLingXiaoWu",
    "hFontan": "PenQuan",
    "hGnomeH": "ZhuRuXiaoWu",
    "hGobHouse": "GeBuLinXiaoWu",
    "hGobVill": "GeBuLinCun",
    "hGraveY": "MuDi",
    "hGuardT": "JianTa",
    "hHouse": "YingXiongZhiJia",
    "hKrolmT": "KeLuoMuShenMiao",
    "hLibrary": "TuShuGuan",
    "hMLair": "GuaiWuChaoXue",
    "hMarket": "JiShi",
    "hMnstrHous": "NongMinWu",
    "hRangerG": "YouXiaGongHui",
    "hStatue": "DiaoXiang",
    "hTowerOfMadWizard": "FengKuangWuShi^ZhiTa",
    "hUBararian": "YeManRen",
    "hUBlackDragon": "JuLong",
    "hUDWarrior": "BuHeZhiZhanShi",
    # ================= 生命条 / 标题 =================
    "sLifeBar": "ShengMing",
    "sTaskHead": "MuBiao",
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
    hit, miss = 0, set(PY2)
    out = []
    for r in recs:
        k, sep, v = r.partition(": ")
        if sep:
            stem, _, lang = k.rpartition("_")
            if stem in PY2 and lang in ("en", "de"):
                miss.discard(stem)
                r = f"{k}: {PY2[stem]}"
                hit += 1
        out.append(r)
    buf = bytearray()
    for r in out:
        b = r.encode("utf-8")
        buf += len(b).to_bytes(2, "big") + b
    TDAT.write_bytes(bytes(buf))
    print(f"改写 {hit} 条  (映射表 {len(PY2)} 条, 未命中 {len(miss)}: {sorted(miss)})")
    print(f"写出 {len(buf)} bytes")


if __name__ == "__main__":
    main()
