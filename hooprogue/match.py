"""一场比赛：街球规则先到 N 分，4 节 × 每节 3 个攻防回合。

核心循环（每回合一次决策）：
  意图播报（含演技）→ 玩家选战术/方案（受体能约束）→ 概率公开结算。
所有概率在决策前完全公开——胜负取决于决策质量，不是抽卡。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .opponent import DEF_WEIGHTS, Opponent
from .plays import (DEFENSE, HEAVE, OFFENSE, PLAY_BY_ID, SCHEME_BY_ID,
                    level_bonus, matchup)

QTRS = 4
POSS_PER_Q = 3
PLAYER_STAMINA = 5   # 攻防共用的每节体能池（3次进攻+3次防守 ≈ 4.6 点消耗）
ORB_BASE = 0.25       # 进攻篮板率（打铁后夺回球权 → 自动补篮）
PUTBACK_P = 0.55
SUDDEN_DEATH_CAP = 12  # 骤死回合对数上限（之后掷签）
_TOTAL_DEF_W = sum(DEF_WEIGHTS.values())
DEF_WEIGHTS_NORM = {k: v / _TOTAL_DEF_W for k, v in DEF_WEIGHTS.items()}


@dataclass
class SideState:
    pts: int = 0
    q_pts: list = field(default_factory=list)
    stamina: int = 3
    turnovers: int = 0


@dataclass
class MatchResult:
    won: bool
    player_pts: int
    opp_pts: int
    log: list
    opp_usage: dict = field(default_factory=dict)   # 对手战术使用统计（侦察备忘）


class Match:
    def __init__(self, playbook: dict, perks: dict, opp: Opponent,
                 rng: random.Random, boons: dict | None = None,
                 log=print, chooser=None):
        """chooser(phase: dict) -> dict  决策回调（交互/Auto 各自实现）。

        phase(kind="offense"): {"plays": [(play, p_make, p_to, afford)...],
                                "telegraph": {scheme_id: p}, "stamina": int}
        phase(kind="defense"): {"schemes": [...], "telegraph": {play_id: p},
                                "stamina": int}
        返回 {"id": play_id/scheme_id}
        """
        self.playbook = playbook          # {play_id: level}
        self.perks = perks                # {"orb":0,"clutch":0,"insight":0}
        self.opp = opp
        self.rng = rng
        self.boons = boons or {}          # {"rest":bool,"intel":bool,"home":bool}
        self.log = log
        self.chooser = chooser
        self.us = SideState()
        self.them = SideState()
        self.opp_usage: dict = {}    # 对手实际使用的战术统计（侦察备忘用）
        self._q = 1

    # ------------------------------------------------------------------ 主流程
    def play(self) -> MatchResult:
        self.log(f"\n  对阵 {self.opp.name}（评分 {self.opp.rating}）"
                 f"  ·  街球规则：先到 {self.opp.target} 分")
        if self.opp.is_boss:
            self.log("  BOSS：会演戏的播报 + 每节多 1 点体能")
        for q in range(1, QTRS + 1):
            self._q = q
            self.us.stamina = PLAYER_STAMINA + (1 if self.boons.get("rest") else 0)
            self.them.stamina = self.opp.stamina_per_q
            self.us.q_pts.append(0)
            self.them.q_pts.append(0)
            if q == QTRS:
                self.log("  末节：关键时刻")
            player_first = q % 2 == 1
            self._def_poss_in_q = 0
            for i in range(POSS_PER_Q):
                self._def_poss_in_q = i
                if player_first:
                    self.poss_player_offense()
                    self.poss_player_defense()
                else:
                    self.poss_player_defense()
                    self.poss_player_offense()
                if self.us.pts >= self.opp.target or self.them.pts >= self.opp.target:
                    break
            self.log(f"  ── Q{q} 结束 ──  我方 {self.us.pts} : {self.them.pts} 对方"
                     f"  （目标 {self.opp.target}）")
            if self.us.pts >= self.opp.target or self.them.pts >= self.opp.target:
                break
        # 回合耗尽未达标：比分高者胜；平分 → 骤死回合（有上限保险）
        pairs = 0
        while self.us.pts == self.them.pts:
            pairs += 1
            if pairs > SUDDEN_DEATH_CAP:
                self.log("  连续骤死未分胜负，掷签决定球权归属")
                if self.rng.random() < 0.5:
                    self._score_us(1, "  ▶ 掷签得手 +1")
                else:
                    self._score_them(1, "  ◀ 掷签得手 +1")
                break
            self.log("  骤死回合！")
            self.poss_player_defense()
            if self.us.pts != self.them.pts:
                break
            self.poss_player_offense()
        won = self.us.pts > self.them.pts
        return MatchResult(won=won, player_pts=self.us.pts, opp_pts=self.them.pts,
                           log=[], opp_usage=self.opp_usage)

    # ------------------------------------------------------------------ 我方进攻
    def poss_player_offense(self):
        # 对手先暗中选定防守方案，并给出（可能失真的）播报
        scheme = self.opp.choose_defense_scheme(self.them.stamina, self.rng)
        self.them.stamina -= scheme.cost
        shown = self._shown_defense_dist(scheme)
        clutch = self.perks.get("clutch", 0.0) if self._q == QTRS else 0.0

        opts = []
        for p in OFFENSE:
            if self.playbook.get(p.id):
                lv = self.playbook[p.id]
            else:
                continue
            afford = p.cost <= self.us.stamina
            mm, tm = matchup(p.id, scheme.id) if p.id != "iso" else (0.0, 0.0)
            p_make = min(0.95, max(0.03, p.base + level_bonus(lv) + mm
                                   + (0.04 if self.boons.get("home") else 0.0)
                                   + clutch))
            p_to = min(0.5, p.tov + tm + scheme.to_mod_all)
            opts.append((p, p_make, p_to, afford))
        if not any(o[3] for o in opts):
            opts = [(HEAVE, HEAVE.base, HEAVE.tov, True)]
        phase = dict(kind="offense", plays=opts, telegraph=shown,
                     stamina=self.us.stamina)
        pick = self.chooser(phase)
        play = PLAY_BY_ID.get(pick["id"], HEAVE)
        assert play.cost <= self.us.stamina or play.id == "heave"
        self.us.stamina -= play.cost
        self.opp.record_player_play(play.id)

        entry = next(o for o in opts if o[0].id == play.id)
        _, p_make, p_to, _ = entry
        roll = self.rng.random()
        if roll < p_to:
            self.us.turnovers += 1
            self.log(f"  ▶ {play.name} ✗ 失误！球权转换")
            return
        if roll < p_to + p_make:
            self._score_us(play.pts, f"▶ {play.name} ✓ +{play.pts}")
            return
        # 打铁 → 进攻篮板 → 自动补篮
        if self.rng.random() < ORB_BASE + self.perks.get("orb", 0.0):
            self.log(f"  ▶ {play.name} ✗ 打铁… 前场篮板！")
            if self.rng.random() < PUTBACK_P:
                self._score_us(1, "  ▶ 补篮得手 +1")
            else:
                self.log("  ▶ 补篮不中")
        else:
            self.log(f"  ▶ {play.name} ✗ 打铁，对方篮板")

    def _shown_defense_dist(self, actual) -> dict:
        """对手防守方案播报：播报其防守策略权重（带噪声/演技）。

        情报 boon（intel）直接揭示本回合的实际方案；
        「识破演技」特质把播报噪声减半。
        """
        if self.boons.get("intel"):
            return {actual.id: 1.0}
        noise = 0.06 if self.perks.get("insight") else 0.12
        return self.opp.telegraph(DEF_WEIGHTS_NORM, self.rng, noise=noise)

    # ------------------------------------------------------------------ 我方防守
    def poss_player_defense(self):
        # 对手先选定进攻战术并（失真地）播报；AI 会为非末回合预留体能
        is_last = (self._def_poss_in_q >= POSS_PER_Q - 1)
        play = self.opp.choose_offense_play(self.them.stamina, is_last, self.rng)
        if play is None:
            self.log("  ◀ 对方体能枯竭，勉强出手")
            play = HEAVE
        self.them.stamina -= play.cost
        self.opp_usage[play.name] = self.opp_usage.get(play.name, 0) + 1
        telegraph = self._shown_offense_dist(play)
        clutch_opp = 0.05 if (self.opp.is_boss and self._q == QTRS) else 0.0

        opts = []
        for s in DEFENSE:
            afford = s.cost <= self.us.stamina
            mm, tm = matchup(play.id, s.id)
            opp_make = min(0.95, max(0.03,
                          play.base * self.opp.base_mult + mm + clutch_opp))
            opp_to = min(0.5, play.tov + tm + s.to_mod_all)
            opts.append((s, opp_make, opp_to, afford))
        phase = dict(kind="defense", schemes=opts, telegraph=telegraph,
                     stamina=self.us.stamina)
        pick = self.chooser(phase)
        scheme = SCHEME_BY_ID[pick["id"]]
        assert scheme.cost <= self.us.stamina
        self.us.stamina -= scheme.cost
        self.opp.last_player_scheme = scheme.id

        entry = next(o for o in opts if o[0].id == scheme.id)
        _, opp_make, opp_to, _ = entry
        roll = self.rng.random()
        if roll < opp_to:
            self.log(f"  ◀ {scheme.name} ★ 逼出对方失误！")
            return
        if roll < opp_to + opp_make:
            self._score_them(play.pts,
                             f"◀ ✗ 对方 {play.name} 得手 +{play.pts}")
            return
        if self.rng.random() < ORB_BASE - 0.02 + (self.opp.rating - 42) * 0.002:
            self.log(f"  ◀ {scheme.name} 打铁… 对方前场篮板")
            if self.rng.random() < PUTBACK_P - 0.05:
                self._score_them(1, "  ◀ 对方补篮 +1")
        else:
            self.log(f"  ◀ {scheme.name} 防守成功！")

    def _shown_offense_dist(self, actual) -> dict:
        if self.boons.get("intel"):
            return {actual.id: 1.0}
        noise = 0.06 if self.perks.get("insight") else 0.12
        return self.opp.telegraph(self.opp.offense_weights, self.rng, noise=noise)

    # ------------------------------------------------------------------ 记分
    def _score_us(self, pts, text):
        self.us.pts += pts
        self.us.q_pts[-1] += pts
        self.log(f"{text}   【{self.us.pts}:{self.them.pts}】")

    def _score_them(self, pts, text):
        self.them.pts += pts
        self.them.q_pts[-1] += pts
        self.log(f"{text}   【{self.us.pts}:{self.them.pts}】")
