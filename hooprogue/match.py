"""逐回合攻防的比赛引擎。

一场比赛 = 4 节 × 每节 8 个回合，双方交替球权。
卡牌效果全部在回合级别生效（护盾 / 热手 / 快攻 / 关键时刻…）。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .cards import Mods
from .player import Archetype, Opponent, clamp, opp_defense, opp_stats

POSS_PER_Q = 8
QUARTERS = 4
TEMPOS = ("slow", "balanced", "fast")
TEMPO_NAME = {"slow": "稳扎稳打", "balanced": "均衡节奏", "fast": "极速跑轰"}


@dataclass
class BoxScore:
    pts: int = 0
    fga: int = 0
    fgm: int = 0
    tpa: int = 0
    tpm: int = 0
    tov: int = 0
    reb: int = 0
    q_pts: list = field(default_factory=list)


@dataclass
class MatchResult:
    won: bool
    margin: int
    us: BoxScore
    them: BoxScore


class Match:
    def __init__(self, arch: Archetype, mods: Mods, extra_bonus: float,
                 opp: Opponent, rng: random.Random, tempo: str = "balanced",
                 log=print, halftime_fn=None):
        self.arch = arch
        self.mods = mods
        self.extra_bonus = extra_bonus   # 卡池抽空后的士气加成等
        self.opp = opp
        self.rng = rng
        self.tempo = tempo if tempo in TEMPOS else "balanced"
        self.log = log
        self.halftime_fn = halftime_fn

        self.us = BoxScore()
        self.them = BoxScore()
        self.shield = 0
        self.heat = 0
        self.opp_st = opp_stats(opp)
        self.opp_def = opp_defense(opp)

        # 精英防守：高评分对手会针对性布防——掐断二次进攻与快攻（额外球权），
        # 并部分抵消卡牌加成。这是对抗玩家"卡牌雪球"的主要手段，
        # 否则对手数值被钳制上限封顶后，后期形同虚设。
        self.elite = clamp((opp.rating - 70.0) / 40.0, 0.0, 1.0)
        self.bonus_scale = 1.0 - 0.4 * self.elite
        self.extra_poss_scale = 1.0 - 0.5 * self.elite

        # 节奏修正
        self.tov_mult = {"slow": 0.85, "balanced": 1.0, "fast": 1.25}[self.tempo]
        self.tend_add = {"slow": -0.08, "balanced": 0.0, "fast": 0.10}[self.tempo]
        self.fb_add = {"slow": -0.15, "balanced": 0.0, "fast": 0.10}[self.tempo]

        # Boss 特性修正
        t = opp.trait_id
        self.us_three_mod = -0.08 if t == "zone" else 0.0
        self.us_two_mod = -0.08 if t == "towers" else 0.0
        self.us_all_mod = -0.05 if t == "mvp" else 0.0
        self.tov_press_mult = 1.6 if t == "press" else 1.0
        self.opp_make_bonus = 0.03 if t == "mvp" else 0.0
        self.opp_reb_bonus = 0.10 if t == "towers" else 0.0

        self.second_half_off = 0.0   # 中场暂停选择的效果
        self.second_half_def = 0.0
        self._q = 1
        self._clutch = False
        self._clutch_shown = False

    # ------------------------------------------------------------------ 主流程
    def play(self) -> MatchResult:
        self.log(f"\n  ⚔ 对阵 {self.opp.name}（评分 {self.opp.rating}）"
                 f"  ·  节奏：{TEMPO_NAME[self.tempo]}")
        if self.opp.is_boss:
            self.log(f"  ☠ BOSS 特性【{self.opp.trait_name}】：{self.opp.trait_desc}")
        total = QUARTERS * POSS_PER_Q
        done = 0
        for q in range(1, QUARTERS + 1):
            self._q = q
            self.us.q_pts.append(0)
            self.them.q_pts.append(0)
            if q == 3:
                self._halftime()
            we_start = q % 2 == 1
            for _ in range(POSS_PER_Q):
                done += 1
                self._clutch = (q == QUARTERS and total - done < POSS_PER_Q)
                if self._clutch and not self._clutch_shown:
                    self.log("  ⏱️ 关键时刻！")
                    self._clutch_shown = True
                if we_start:
                    self.poss_us()
                    self.poss_them()
                else:
                    self.poss_them()
                    self.poss_us()
            self.log(f"  ── Q{q} 结束 ──  我方 {self.us.pts} : {self.them.pts} 对方")
        won = self.us.pts > self.them.pts
        return MatchResult(won=won, margin=self.us.pts - self.them.pts,
                           us=self.us, them=self.them)

    def _halftime(self):
        self.log(f"  ── 中场 ──  我方 {self.us.pts} : {self.them.pts} 对方")
        choice = None
        if self.halftime_fn is not None:
            choice = self.halftime_fn(self)
        if choice == "offense":
            self.second_half_off = 0.05
            self.log("  📣 暂停布置：下半场加强进攻（命中率 +5%）")
        elif choice == "defense":
            self.second_half_def = 0.05
            self.log("  📣 暂停布置：下半场收缩防守（对方命中率 -5%）")
        else:
            self.log("  （没有叫暂停）")

    # ------------------------------------------------------------------ 我方回合
    def poss_us(self, fast: bool = False, depth: int = 0):
        m, rng = self.mods, self.rng

        if not fast and rng.random() < self._us_tov_p():
            self.us.tov += 1
            self.log("  ▶ ✗ 失误，球权转换")
            return

        tend = clamp(self.arch.three_tendency + m.tendency_bonus * self.bonus_scale
                     + self.tend_add, 0.05, 0.85)
        is_three = rng.random() < tend

        if is_three:
            p = self.arch.three + (m.three_bonus + self.us_three_mod) * self.bonus_scale
        else:
            p = self.arch.two + (m.two_bonus + self.us_two_mod) * self.bonus_scale
        p += ((m.all_bonus + self.extra_bonus + self.us_all_mod) * self.bonus_scale
              + self.second_half_off)
        p -= self.opp_def
        if m.heat_on and self.heat > 0:
            p += min(self.heat * 0.03, 0.15) * self.bonus_scale
        if self._clutch:
            p += m.clutch_bonus * self.bonus_scale
        hot = ""
        if not fast and m.ankle_chance and rng.random() < m.ankle_chance:
            p += m.ankle_bonus * self.bonus_scale
            hot = "🌀晃倒防守人！"
        p = clamp(p, 0.03, 0.95)

        self.us.fga += 1
        if is_three:
            self.us.tpa += 1
        made = rng.random() < p
        if made:
            self.us.fgm += 1
            if is_three:
                self.us.tpm += 1
            pts = 3 if is_three else 2
            self.us.pts += pts
            self.us.q_pts[-1] += pts
            self.heat += 1
            tag = "🔥" if m.heat_on and self.heat >= 3 else ""
            self.log(f"  ▶ {'⚡快攻' if fast else ''}{hot}"
                     f"{'三分命中' if is_three else '两分命中'} +{pts} {tag}"
                     f"   【{self.us.pts}:{self.them.pts}】")
        else:
            self.heat = 0
            self.log(f"  ▶ ✗ 打铁{'（快攻上丢）' if fast else ''}")
            if depth < 3 and rng.random() < (self.arch.off_reb + m.off_reb_bonus) * self.extra_poss_scale:
                self.us.reb += 1
                self.log("  ▶ ↻ 进攻篮板！额外球权")
                self.poss_us(depth=depth + 1)

    def _us_tov_p(self) -> float:
        m = self.mods
        return clamp(self.arch.tov * m.tov_mult * self.tov_mult * self.tov_press_mult,
                     0.01, 0.45)

    # ------------------------------------------------------------------ 对方回合
    def poss_them(self, depth: int = 0):
        m, rng = self.mods, self.rng
        st = self.opp_st

        if rng.random() < st["tov"] / self.tov_press_mult:
            self.them.tov += 1
            self.log("  ◀ ★ 逼出对方失误！")
            self._fast_break_chance()
            return

        is_three = rng.random() < 0.32
        p = ((st["three"] if is_three else st["two"]) + self.opp_make_bonus
             - (self.arch.defense - 0.55) * 0.05 - self.second_half_def)
        p = clamp(p, 0.03, 0.95)

        if rng.random() < p:
            pts = 3 if is_three else 2
            if m.shield_on and self.shield > 0:
                self.shield -= 1
                self.log(f"  ◀ 🧱 护盾抵挡对方 +{pts}！（剩余 {self.shield}）"
                         f"   【{self.us.pts}:{self.them.pts}】")
            else:
                self.them.pts += pts
                self.them.q_pts[-1] += pts
                self.log(f"  ◀ ✗ 对方{'三分' if is_three else '两分'}命中 +{pts}"
                         f"   【{self.us.pts}:{self.them.pts}】")
        else:
            self.log("  ◀ 🛡 防守成功")
            if m.shield_on and self.shield < 3:
                self.shield += 1
                self.log(f"  ◀ 🧱 护盾充能 +1（{self.shield}/3）")
            if depth < 3 and rng.random() < st["off_reb"] + self.opp_reb_bonus:
                self.them.reb += 1
                self.log("  ◀ ✗ 对方抢到进攻篮板")
                self.poss_them(depth=depth + 1)
            else:
                self._fast_break_chance()

    def _fast_break_chance(self):
        chance = (self.mods.fb_chance + self.fb_add) * self.extra_poss_scale
        if chance > 0 and self.rng.random() < chance:
            self.log("  ▶ ⚡ FAST BREAK！防守反击一条龙")
            self.poss_us(fast=True)
