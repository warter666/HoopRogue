"""战术库：进攻战术、防守方案、克制矩阵。

设计规则（策划书 §4）：每个战术恰好被 1~2 个方案克制、也恰好克制别人；
矩阵完全公开，深度来自"猜对方会不会演"。没有技能卡，只有战术板。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Play:
    id: str
    name: str
    icon: str
    cost: int          # 体能消耗
    pts: int           # 街球分值（1分/2分）
    base: float        # 基础成功率
    tov: float         # 基础失误率
    desc: str


@dataclass(frozen=True)
class Scheme:
    id: str
    name: str
    icon: str
    cost: int
    to_mod_all: float  # 对所有战术的失误率加成
    desc: str


OFFENSE = [
    Play("push", "推快上篮", "🏃", 1, 1, 0.58, 0.10, "抢下篮板直接冲击篮下"),
    Play("perim", "外线远投", "🎯", 1, 2, 0.42, 0.08, "弧顶三分，一锤定音"),
    Play("post", "低位强打", "🧱", 2, 1, 0.62, 0.10, "背身碾压到篮下"),
    Play("pnr", "挡拆发起", "🔄", 2, 1, 0.55, 0.08, "高位挡拆找错位"),
    Play("backdoor", "空切反跑", "⚡", 2, 1, 0.60, 0.09, "阅读防守，打身后"),
    Play("motion", "传切体系", "🎪", 2, 2, 0.47, 0.07, "连续传导撕裂防线"),
    Play("iso", "巨星球的", "🌟", 3, 1, 0.50, 0.06, "巨星单打，无法被克制"),
]
HEAVE = Play("heave", "勉强出手", "😮", 0, 1, 0.30, 0.14, "体能耗尽的被迫选择")

DEFENSE = [
    Scheme("stock", "普通退防", "😴", 0, 0.02, "不犯错也不赌"),
    Scheme("man", "盯人", "🛡", 1, 0.00, "贴身缠斗，扑外线"),
    Scheme("switch", "换防", "🔄", 1, 0.00, "无限换防"),
    Scheme("zone", "联防", "🚫", 1, 0.00, "收缩禁区"),
    Scheme("double", "包夹", "📦", 2, 0.00, "双人围堵强点"),
    Scheme("press", "紧逼", "⚡", 2, 0.08, "全场施压赌失误"),
]

PLAY_BY_ID = {p.id: p for p in OFFENSE}
SCHEME_BY_ID = {s.id: s for s in DEFENSE}
START_PLAYBOOK = ["push", "perim", "pnr", "post"]

# (play_id, scheme_id) -> (make_mod, tov_mod)，进攻方视角。
# iso 不吃 make_mod（巨星不讲理），press 的 to_mod_all 对谁都生效。
MATCHUP = {
    ("push", "stock"): (-0.10, 0.00),
    ("perim", "man"): (-0.10, 0.00),
    ("motion", "man"): (-0.12, 0.00),
    ("pnr", "man"): (+0.10, 0.00),
    ("post", "double"): (-0.14, +0.12),
    ("perim", "double"): (+0.10, 0.00),
    ("motion", "double"): (+0.10, 0.00),
    ("pnr", "switch"): (-0.12, 0.00),
    ("backdoor", "switch"): (+0.12, 0.00),
    ("backdoor", "zone"): (-0.12, 0.00),
    ("post", "zone"): (-0.10, 0.00),
    ("perim", "zone"): (+0.12, 0.00),
    ("motion", "zone"): (+0.08, 0.00),
    ("backdoor", "press"): (+0.12, 0.00),
}


def matchup(play_id: str, scheme_id: str) -> tuple[float, float]:
    if play_id == "iso":
        return (0.0, 0.02 if scheme_id == "press" else 0.0)
    return MATCHUP.get((play_id, scheme_id), (0.0, 0.0))


def counters_of(play_id: str) -> list:
    """克制该战术的防守方案（供 AI 与战术手册）。"""
    return [s for s in DEFENSE if matchup(play_id, s.id)[0] < -0.05]


def weaknesses_of(scheme_id: str) -> list:
    """该方案防不住的战术（进攻方占优）。"""
    return [p for p in OFFENSE if matchup(p.id, scheme_id)[0] > 0.05]


def level_bonus(level: int) -> float:
    """战术等级加成：Lv1 0% / Lv2 +6% / Lv3 +12%。"""
    return 0.06 * (level - 1)


def manual_lines() -> list:
    """《战术手册》：完整克制表。"""
    lines = ["《战术手册》—— 克制矩阵（进攻方视角）"]
    for p in OFFENSE:
        cs = counters_of(p.id)
        ws = [s.name for s in DEFENSE if matchup(p.id, s.id)[0] > 0.05]
        lines.append(
            f"  {p.name}（{p.pts}分/{p.cost}体能/{p.base:.0%}）"
            f"  被【{'、'.join(s.name for s in cs) or '—'}】克制"
            f"  强吃【{'、'.join(ws) or '—'}】")
    for s in DEFENSE:
        lines.append(f"  {s.name}（{s.cost}体能）{s.desc}"
                     + (f"  对方失误率 +{s.to_mod_all:.0%}" if s.to_mod_all else ""))
    return lines
