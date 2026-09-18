"""Roguelike 主循环：选人 → 比赛 → 胜利三选一强化 → Boss → 12 胜夺冠。

随机数说明：本模块使用 `random.Random(seed)`，为的是"同种子 = 同一局"
（可复现、可测试）。这是游戏逻辑的确定性需求，不是加密用途。

v0.1 不做文件存档：Game 预留 records_fn 回调（接收 wins 与是否夺冠），
未来版本再接持久化实现。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .cards import compute_mods, draw_three
from .match import TEMPOS, Match
from .player import ARCHETYPES, make_opponent
from .ui import LINE, TEMPO_BY_KEY, banner, box_table, card_line, run_status, tempo_menu

WIN_TARGET = 12   # 12 胜夺冠
ROUND_CAP = 20


@dataclass
class RunState:
    arch: object
    cards: list = field(default_factory=list)
    mods: object = None
    round: int = 0
    wins: int = 0
    total_pts: int = 0
    extra_bonus: float = 0.0
    champion: bool = False

    def card_ids(self):
        return [c.id for c in self.cards]


class Game:
    def __init__(self, seed=None, auto=False, quiet=False,
                 records_fn=None, input_fn=input):
        self.rng = random.Random(seed)  # 游戏 RNG：可复现，非加密用途
        self.auto = auto
        self.log = print  # 结构性输出（场次/结果/总结）始终保留
        # quiet = 浓缩观战：静默逐回合日志，只看每场结果
        self.match_log = (lambda *_: None) if quiet else print
        self.records_fn = records_fn
        self.input_fn = input_fn
        self.run = None

    # ------------------------------------------------------------------ 交互
    def _ask(self, prompt, valid):
        while True:
            raw = self.input_fn(prompt).strip()
            if raw in valid:
                return raw
            print(f"  请输入 {'/'.join(sorted(valid))}")

    def _pick_archetype(self):
        if self.auto:
            return self.rng.choice(ARCHETYPES)
        self.log("\n  选择你的球员原型：")
        for i, a in enumerate(ARCHETYPES, 1):
            self.log(f"  [{i}] {a.icon} {a.name} — {a.desc}")
            self.log(f"       三分 {a.three:.0%} / 两分 {a.two:.0%} / "
                     f"失误 {a.tov:.0%} / 防守 {a.defense:.2f} / "
                     f"三分倾向 {a.three_tendency:.0%}")
        raw = self._ask("  输入 1-3: ", {"1", "2", "3"})
        return ARCHETYPES[int(raw) - 1]

    def _pick_tempo(self):
        if self.auto:
            return self.rng.choice(TEMPOS)
        self.log("")
        self.log(tempo_menu())
        return TEMPO_BY_KEY[self._ask("  输入 1-3: ", {"1", "2", "3"})]

    def _pick_card(self, picks):
        if not picks:
            self.run.extra_bonus += 0.05
            self.log("  💫 卡池已抽空：全队士气高涨，命中率永久 +5%")
            return
        if self.auto:
            pick = self.rng.choice(picks)
        else:
            self.log("\n  🎁 胜利奖励！三选一强化：")
            for i, c in enumerate(picks, 1):
                self.log(card_line(c, i))
            pick = picks[int(self._ask("  输入 1-3: ", {"1", "2", "3"})) - 1]
        self.run.cards.append(pick)
        self.run.mods = compute_mods(self.run.cards)
        self.log(f"  ✨ 获得 {pick.icon} {pick.name}")

    # ------------------------------------------------------------------ 流程
    def start(self) -> RunState:
        banner(self.log)
        arch = self._pick_archetype()
        self.run = RunState(arch=arch, mods=compute_mods([]))
        self.log(f"\n  你选择了 {arch.icon} {arch.name} —— {arch.desc}")
        result = None
        while True:
            self.run.round += 1
            opp = make_opponent(self.run.round, self.rng)
            tempo = self._pick_tempo()
            result = self._play_match(opp, tempo)
            self.run.total_pts += result.us.pts
            if result.won:
                self.run.wins += 1
                self.log(f"\n  ✅ 胜利！（净胜 {result.margin:+d}）  "
                         + run_status(self.run).strip())
                if self.run.wins >= WIN_TARGET:
                    self.run.champion = True
                    self._championship()
                    break
                self._award_card()
            else:
                self._game_over(result)
                break
            if self.run.round >= ROUND_CAP:
                self.log("\n  🏁 赛季结束（20 场上限）")
                break
        if self.records_fn is not None:
            try:
                self.records_fn(self.run.wins, self.run.champion)
            except Exception:
                pass
        return self.run

    def _award_card(self):
        picks = draw_three(self.rng, self.run.card_ids())
        self._pick_card(picks)

    def _play_match(self, opp, tempo) -> "MatchResult":
        self.log(f"\n{LINE}")
        self.log(f"  🏀 第 {self.run.round} 场  ·  对手：{opp.name}"
                 f"（评分 {opp.rating}）")
        if opp.is_boss:
            self.log(f"  ☠ BOSS 特性【{opp.trait_name}】：{opp.trait_desc}")

        def halftime_fn(m):
            if self.auto:
                return self.rng.choice(["offense", "defense"])
            self.log("\n  📣 中场暂停：选择下半场布置")
            self.log("  [1] 加强进攻（己方命中率 +5%）  "
                     "[2] 收缩防守（对方命中率 -5%）")
            return ("offense" if self._ask("  输入 1-2: ", {"1", "2"}) == "1"
                    else "defense")

        match = Match(arch=self.run.arch, mods=self.run.mods,
                      extra_bonus=self.run.extra_bonus, opp=opp, rng=self.rng,
                      tempo=tempo, log=self.match_log, halftime_fn=halftime_fn)
        result = match.play()
        self.log("  " + box_table(result.us, result.them).strip())
        return result

    def _championship(self):
        self.log(f"\n{LINE}")
        self.log("  🏆🏆🏆  C H A M P I O N  🏆🏆🏆")
        self.log(f"  以 {self.run.wins} 连胜夺得街球生存赛冠军！")
        self.log(f"  总得分 {self.run.total_pts} · "
                 f"卡牌 {' '.join(c.icon for c in self.run.cards)}")
        self.log(LINE)

    def _game_over(self, result):
        self.log(f"\n{LINE}")
        self.log(f"  💀 RUN OVER —— 第 {self.run.round} 场落败"
                 f"（净负 {result.margin:+d}）")
        self.log(f"  战绩 {self.run.wins} 胜 · 总得分 {self.run.total_pts}")
        self.log("  本局收集的卡牌：")
        for c in self.run.cards:
            self.log(card_line(c))
        self.log(LINE)
