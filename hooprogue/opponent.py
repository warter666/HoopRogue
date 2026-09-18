"""对手：5 场成长弧线 + 意图播报（含演技/伪装）+ 自适应针对。

成长维度不是单纯 +命中率，而是让"读人"越来越难：
  第1~2场 诚实播报 → 第3场 15% 演戏 → 第4场 20% 演戏 + 针对你的常用战术
  → 第5场 BOSS 30% 演戏 + 每节多 1 点体能 + 先到 15 分。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .plays import OFFENSE, PLAY_BY_ID, SCHEME_BY_ID, counters_of

GAMES = [
    dict(name="公园联队", rating=42, bluff=0.00, adapt=0.15, stamina=5, target=11),
    dict(name="健身房猛男", rating=52, bluff=0.00, adapt=0.25, stamina=5, target=11),
    dict(name="街球艺术家", rating=61, bluff=0.15, adapt=0.35, stamina=5, target=11),
    dict(name="城市冠军队", rating=69, bluff=0.20, adapt=0.45, stamina=5, target=11),
    dict(name="战术大师", rating=76, bluff=0.30, adapt=0.55, stamina=6, target=15),
]
GAME_TITLES = ["热身赛", "地区赛", "挑战赛", "半决赛", "☠ BOSS 决战"]

# 对手 personalities：进攻战术倾向模板
PERSONALITIES = {
    "outside": {"perim": 0.34, "motion": 0.20, "pnr": 0.16, "push": 0.12,
                "backdoor": 0.08, "iso": 0.06, "post": 0.04},
    "inside": {"post": 0.28, "push": 0.24, "pnr": 0.20, "backdoor": 0.12,
               "iso": 0.10, "perim": 0.04, "motion": 0.02},
    "balanced": {"pnr": 0.20, "push": 0.18, "perim": 0.16, "post": 0.16,
                 "backdoor": 0.12, "motion": 0.12, "iso": 0.06},
}

# AI 防守方案的基础权重（按便宜好用程度）
DEF_WEIGHTS = {"stock": 2.0, "man": 2.0, "switch": 1.5, "zone": 1.5,
               "double": 1.0, "press": 0.8}


@dataclass
class Opponent:
    game_idx: int
    name: str
    rating: float
    bluff_p: float
    adapt_p: float
    stamina_per_q: int
    target: int
    is_boss: bool
    offense_weights: dict
    player_usage: dict = field(default_factory=dict)   # 我方战术使用统计
    last_player_scheme: str | None = None

    @property
    def base_mult(self) -> float:
        """对手成功率随评分的成长。"""
        return 1.0 + (self.rating - 42.0) * 0.008

    def record_player_play(self, play_id: str):
        self.player_usage[play_id] = self.player_usage.get(play_id, 0) + 1

    # ------------------------------------------------------------ 决策
    def choose_offense_play(self, stamina: int, is_last: bool,
                            rng: random.Random):
        """对手进攻：按 personality 选战术。

        体能预算：非本节最后一回合会预留 1 点体能，避免"第三回合枯竭"。
        """
        budget = stamina if is_last else max(0, stamina - 1)
        affordable = {k: v for k, v in self.offense_weights.items()
                      if PLAY_BY_ID[k].cost <= budget}
        if not affordable:
            affordable = {k: v for k, v in self.offense_weights.items()
                          if PLAY_BY_ID[k].cost <= stamina}
        if not affordable:
            return None
        if self.last_player_scheme and rng.random() < 0.30:
            counters = counters_of(
                max(self.offense_weights, key=self.offense_weights.get))
            if self.last_player_scheme in [s.id for s in counters]:
                # 头号战术会被克：换第二选择
                ordered = sorted(affordable.items(), key=lambda kv: -kv[1])
                if len(ordered) > 1:
                    return PLAY_BY_ID[ordered[1][0]]
        ids = list(affordable)
        return PLAY_BY_ID[rng.choices(ids, weights=[affordable[i] for i in ids], k=1)[0]]

    def choose_defense_scheme(self, stamina: int, rng: random.Random):
        """对手防守：adapt_p 概率针对我方最常用战术，否则按基础权重。"""
        affordable = [s for s in SCHEME_BY_ID.values() if s.cost <= stamina]
        if not affordable:
            return SCHEME_BY_ID["stock"]
        if self.player_usage and rng.random() < self.adapt_p:
            top_play = max(self.player_usage, key=self.player_usage.get)
            cs = [s for s in counters_of(top_play) if s.cost <= stamina]
            if cs:
                return rng.choice(cs)
        ids = [s.id for s in affordable]
        weights = [DEF_WEIGHTS[i] for i in ids]
        return SCHEME_BY_ID[rng.choices(ids, weights=weights, k=1)[0]]

    # ------------------------------------------------------------ 意图播报
    def telegraph(self, true_dist: dict, rng: random.Random,
                  noise: float = 0.12) -> dict:
        """把真实分布变成玩家看到的播报：加噪声，可能演戏（伪装）。"""
        items = list(true_dist.items())
        ids = [k for k, _ in items]
        vals = [max(0.01, v + rng.gauss(0.0, noise)) for _, v in items]
        total = sum(vals)
        dist = {k: v / total for k, v in zip(ids, vals)}
        if rng.random() < self.bluff_p:
            top2 = sorted(dist, key=dist.get, reverse=True)
            if len(top2) >= 2:
                a, b = top2[0], top2[1]
                dist[a], dist[b] = dist[b], dist[a]   # 交换最可能的两个
        return dist


def make_opponent(game_idx: int, rng: random.Random) -> Opponent:
    g = GAMES[game_idx]
    style = rng.choice(list(PERSONALITIES))
    weights = dict(PERSONALITIES[style])
    return Opponent(
        game_idx=game_idx,
        name=f"{GAME_TITLES[game_idx]} · {g['name']}",
        rating=float(g["rating"]), bluff_p=g["bluff"], adapt_p=g["adapt"],
        stamina_per_q=g["stamina"], target=g["target"],
        is_boss=(game_idx == 4), offense_weights=weights,
    )
