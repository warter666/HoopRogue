"""球员原型（三选一起始）与对手生成。"""

from __future__ import annotations

import random
from dataclasses import dataclass


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


@dataclass(frozen=True)
class Archetype:
    id: str
    name: str
    icon: str
    desc: str
    three: float          # 三分命中率
    two: float            # 两分命中率
    tov: float            # 基础失误率
    defense: float        # 防守强度（0~1，压制对方命中率）
    off_reb: float        # 进攻篮板率（打铁后夺回球权）
    three_tendency: float # 三分出手倾向


ARCHETYPES = [
    Archetype("sharp", "神射手", "🎯", "三分精准，防守一般",
              three=0.40, two=0.46, tov=0.11, defense=0.55,
              off_reb=0.20, three_tendency=0.48),
    Archetype("slasher", "突破手", "💪", "冲框机器，防守硬朗",
              three=0.29, two=0.56, tov=0.13, defense=0.70,
              off_reb=0.26, three_tendency=0.22),
    Archetype("twoway", "双能卫", "🧠", "攻防一体的均衡选择",
              three=0.34, two=0.51, tov=0.12, defense=0.80,
              off_reb=0.23, three_tendency=0.33),
]

OPP_NAMES = [
    "夜市球王队", "公园野老虎队", "健身房猛男队", "高中生闪电队",
    "退休大叔队", "外卖骑手队", "程序员远投队", "街球艺术家队",
    "瑜伽教练队", "烧烤摊联队", "晨练大爷队", "大学生联队",
]

# 每 5 关一个 Boss，循环使用特性
BOSS_TRAITS = [
    ("zone", "区域联防", "己方三分命中率 -8%"),
    ("press", "全场紧逼", "己方失误率 +60%"),
    ("towers", "双塔阵容", "己方两分命中率 -8%，对方进攻篮板 +10%"),
    ("mvp", "MVP 队", "己方命中率 -5%，对方命中率 +3%"),
]


@dataclass
class Opponent:
    name: str
    rating: float
    is_boss: bool = False
    trait_id: str = ""
    trait_name: str = ""
    trait_desc: str = ""


def make_opponent(round_no: int, rng: random.Random) -> Opponent:
    # 平衡性标定（tools/balance.py）：开局热身、中期吃紧、后期高压。
    # 幂律曲线前缓后陡——玩家卡牌雪球后期变强，对手必须涨得更快。
    rating = 30 + 9.0 * (round_no ** 0.85) + rng.uniform(-2.0, 2.0)
    is_boss = round_no % 5 == 0
    if is_boss:
        rating += 4.0
        trait_id, trait_name, trait_desc = BOSS_TRAITS[(round_no // 5 - 1) % len(BOSS_TRAITS)]
        name = f"☠ BOSS·{trait_name}队"
    else:
        trait_id = trait_name = trait_desc = ""
        name = rng.choice(OPP_NAMES)
    return Opponent(name=name, rating=round(rating, 1), is_boss=is_boss,
                    trait_id=trait_id, trait_name=trait_name, trait_desc=trait_desc)


def opp_stats(opp: Opponent) -> dict:
    """由评分推导对方的比赛数据。"""
    d = opp.rating - 45.0
    return {
        "three": clamp(0.29 + d * 0.0028, 0.20, 0.42),
        "two": clamp(0.45 + d * 0.0022, 0.38, 0.58),
        "tov": clamp(0.135 - d * 0.0009, 0.07, 0.16),
        "off_reb": clamp(0.19 + d * 0.002, 0.15, 0.33),
    }


def opp_defense(opp: Opponent) -> float:
    """对方防守对我方命中率的削减。"""
    return clamp((opp.rating - 45.0) / 200.0, 0.0, 0.35)
