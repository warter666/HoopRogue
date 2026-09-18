"""技能卡池与强化效果计算。"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

COMMON, EPIC, LEGENDARY = 1, 2, 3
RARITY_NAME = {COMMON: "普通", EPIC: "史诗", LEGENDARY: "传说"}
RARITY_WEIGHT = {COMMON: 5, EPIC: 3, LEGENDARY: 1}


@dataclass(frozen=True)
class Card:
    id: str
    name: str
    icon: str
    rarity: int
    desc: str


CARDS = [
    Card("sharpshooter", "三分机器", "🎯", COMMON, "三分命中率 +10%"),
    Card("court_vision", "Court Vision", "🧠", COMMON, "失误率 -35%"),
    Card("iron_wall", "Iron Wall", "🧱", COMMON, "防守成功充能护盾(上限3)，抵挡对方一次得分"),
    Card("fast_break", "Fast Break", "⚡", COMMON, "防守成功后 25% 打成快攻"),
    Card("rebound_beast", "Rebound Beast", "💪", COMMON, "进攻篮板率 +14%，抢到即获额外球权"),
    Card("heat_check", "Heat Check", "🔥", EPIC, "连续命中每球 +3%（上限 +15%），打铁重置"),
    Card("clutch_gene", "Clutch Gene", "⏱️", EPIC, "第四节最后 4 回合命中率 +12%"),
    Card("ankle_breaker", "Ankle Breaker", "🌀", EPIC, "18% 回合晃倒防守人，该回合命中率 +18%"),
    Card("deep_range", "Deep Range", "🚀", EPIC, "三分倾向 +25%，三分命中率 +4%"),
    Card("goat_mode", "Goat Mode", "🐐", LEGENDARY, "命中率 +6%，失误率再 -30%"),
]

CARD_BY_ID = {c.id: c for c in CARDS}


@dataclass
class Mods:
    """一张卡 = 一组对比赛引擎的数值修正。"""

    three_bonus: float = 0.0
    two_bonus: float = 0.0
    all_bonus: float = 0.0
    tov_mult: float = 1.0
    fb_chance: float = 0.0
    shield_on: bool = False
    off_reb_bonus: float = 0.0
    heat_on: bool = False
    clutch_bonus: float = 0.0
    ankle_chance: float = 0.0
    ankle_bonus: float = 0.0
    tendency_bonus: float = 0.0


def compute_mods(cards) -> Mods:
    ids = {c.id for c in cards}
    m = Mods()
    if "sharpshooter" in ids:
        m.three_bonus += 0.10
    if "court_vision" in ids:
        m.tov_mult *= 0.65
    if "iron_wall" in ids:
        m.shield_on = True
    if "fast_break" in ids:
        m.fb_chance += 0.25
    if "rebound_beast" in ids:
        m.off_reb_bonus += 0.14
    if "heat_check" in ids:
        m.heat_on = True
    if "clutch_gene" in ids:
        m.clutch_bonus = 0.12
    if "ankle_breaker" in ids:
        m.ankle_chance, m.ankle_bonus = 0.18, 0.18
    if "deep_range" in ids:
        m.tendency_bonus += 0.25
        m.three_bonus += 0.04
    if "goat_mode" in ids:
        m.all_bonus += 0.06
        m.tov_mult *= 0.70
    return m


def draw_three(rng: random.Random, owned_ids) -> list:
    """按稀有度权重抽 3 张不重复且未拥有的卡。"""
    owned = set(owned_ids)
    pool = [c for c in CARDS if c.id not in owned]
    picks = []
    while len(picks) < 3 and pool:
        weights = [RARITY_WEIGHT[c.rarity] for c in pool]
        c = rng.choices(pool, weights=weights, k=1)[0]
        picks.append(c)
        pool.remove(c)
    return picks
