"""《战术大师》Roguelike 主循环：5 场成长弧线。

赢一场 → 赛后加练（升级战术/学新战术/球队特质，全确定性效果）
赛前抉择（第2场起）：休整 / 情报 / 主场 —— 路线选择的 StS 味道。
输任何一场 = RUN OVER。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .match import Match
from .narrate import rank_defense, rank_offense
from .opponent import make_opponent
from .plays import (OFFENSE, PLAY_BY_ID, SCHEME_BY_ID, START_PLAYBOOK,
                    level_bonus, manual_lines)

WIN_TARGET_GAMES = 5


@dataclass
class RunState:
    game_idx: int = 0
    playbook: dict = field(default_factory=lambda: {p: 1 for p in START_PLAYBOOK})
    perks: dict = field(default_factory=lambda: {"orb": 0.0, "clutch": 0.0,
                                                 "insight": False})
    wins: int = 0
    champion: bool = False


class TacticianRun:
    def __init__(self, seed=None, auto=False, quiet=False, input_fn=input):
        self.rng = random.Random(seed)   # 游戏 RNG：可复现，非加密用途
        self.auto = auto
        self.log = print  # 结构性输出（场次/结果/总结）始终保留
        # quiet = 浓缩观战：静默逐回合日志，只看每场结果
        self.match_log = (lambda *_: None) if quiet else print
        self.input_fn = input_fn
        self.run = RunState()

    # ------------------------------------------------------------------ 交互
    def _ask(self, prompt, valid):
        while True:
            raw = self.input_fn(prompt).strip()
            if raw in valid:
                return raw
            print(f"  请输入 {'/'.join(sorted(valid))}")

    def _pick(self, options: list, header: str) -> int:
        """展示编号选项并返回下标；auto 模式随机。"""
        if self.auto:
            return self.rng.randrange(len(options))
        self.log(header)
        for i, o in enumerate(options, 1):
            self.log(f"  [{i}] {o}")
        return int(self._ask("  输入编号: ",
                             {str(i) for i in range(1, len(options) + 1)})) - 1

    # ------------------------------------------------------------------ 决策回调
    def _choose_action(self, phase: dict) -> dict:
        if self.auto:
            return self._auto_action(phase)
        if phase["kind"] == "offense":
            return self._ask_action(phase, "play")
        return self._ask_action(phase, "scheme")

    def _auto_action(self, phase: dict) -> dict:
        """AI 决策：与 AI 教练解说共享同一套期望值排序（narrate.rank_*）。"""
        if phase["kind"] == "offense":
            ranked = rank_offense(phase)
            return {"id": ranked[0][0].id} if ranked else {"id": "heave"}
        ranked = rank_defense(phase)
        return {"id": ranked[0][0].id} if ranked else {"id": "stock"}

    def _ask_action(self, phase: dict, kind: str) -> dict:
        tg = phase["telegraph"]
        top = sorted(tg.items(), key=lambda kv: -kv[1])[:3]
        if kind == "play":
            items = phase["plays"]
            self.log(f"  ┌ 进攻回合 · 体能 {'⚡' * max(phase['stamina'], 0)}"
                     f" · 📡 对方防守倾向: "
                     + "  ".join(f"{SCHEME_BY_ID[k].name} {v:.0%}" for k, v in top))

            def name_of(it):
                tag = "" if it[3] else " ✗体能不足"
                p = it[0]
                return (f"{p.icon} {p.name}（{p.cost}⚡/{p.pts}分）"
                        f"命中≈{it[1]:.0%} 失误≈{it[2]:.0%}{tag}")
        else:
            items = phase["schemes"]
            self.log(f"  ┌ 防守回合 · 体能 {'⚡' * max(phase['stamina'], 0)}"
                     f" · 📡 对方进攻意图: "
                     + "  ".join(f"{PLAY_BY_ID[k].name} {v:.0%}" for k, v in top))

            def name_of(it):
                tag = "" if it[3] else " ✗体能不足"
                s = it[0]
                return (f"{s.icon} {s.name}（{s.cost}⚡）"
                        f"对方命中≈{it[1]:.0%} 造失误≈{it[2]:.0%}{tag}")
        for i, it in enumerate(items, 1):
            self.log(f"   [{i}] {name_of(it)}")
        raw = self._ask("  选择: ", {str(i) for i in range(1, len(items) + 1)})
        return {"id": items[int(raw) - 1][0].id}

    # ------------------------------------------------------------------ 主流程
    def start(self) -> RunState:
        self.log("  ══════════════════════════════════════")
        self.log("   战 术 大 师  ·  TACTICIAN")
        self.log("   5 场成长弧线 · 没有技能卡 · 只有战术板")
        self.log("  ══════════════════════════════════════")
        if not self.auto:
            self.log("\n输入 M 可查看《战术手册》（克制矩阵）")

        for game in range(WIN_TARGET_GAMES):
            self.run.game_idx = game
            boons = {}
            if game > 0:
                boons = self._pregame_choice()
            opp = make_opponent(game, self.rng)
            self.log(f"\n{'═' * 58}")
            self.log(f"  🏀 第 {game + 1} 场 · {opp.name}")
            match = Match(playbook=self.run.playbook, perks=self.run.perks,
                          opp=opp, rng=self.rng, boons=boons,
                          log=self.match_log, chooser=self._choose_action)
            result = match.play()
            if result.won:
                self.run.wins += 1
                self.log(f"  ✅ 拿下第 {game + 1} 场！（{result.player_pts}:"
                         f"{result.opp_pts}）")
                if game == WIN_TARGET_GAMES - 1:
                    self.run.champion = True
                    self._championship()
                    break
                self._practice()
            else:
                self._game_over(result)
                break
        return self.run

    def _pregame_choice(self) -> dict:
        opts = [("rest", "🏥 休整", "本场每节体能 +1"),
                ("intel", "🔍 情报", "本场对方播报 100% 诚实（无演技）"),
                ("home", "🏟 主场", "本场成功率 +4%")]
        chosen = self.rng.sample(opts, 2)
        idx = self._pick([f"{n} — {d}" for _, n, d in chosen],
                         "  🗓 赛前抉择（二选一）：")
        key, name, _ = chosen[idx]
        self.log(f"  ✅ 选择：{name}")
        return {key: True}

    def _practice(self):
        """赛后加练：三选一（全确定性效果）。"""
        offers = []
        upgradable = [pid for pid, lv in self.run.playbook.items() if lv < 3]
        self.rng.shuffle(upgradable)
        for pid in upgradable[:2]:
            p = PLAY_BY_ID[pid]
            lv = self.run.playbook[pid]
            offers.append(("upgrade", pid,
                           f"升级 {p.icon} {p.name} → Lv{lv + 1}"
                           f"（当前成功率加成 +{level_bonus(lv):.0%}）"))
        unowned = [p for p in OFFENSE if p.id not in self.run.playbook]
        if unowned:
            p = self.rng.choice(unowned)
            offers.append(("learn", p.id, f"学习新战术 {p.icon} {p.name} — {p.desc}"))
        if not self.run.perks.get("orb"):
            offers.append(("perk", "orb", "球队特质：进攻篮板 +10%（补篮机会）"))
        if not self.run.perks.get("clutch"):
            offers.append(("perk", "clutch", "球队特质：末节命中率 +8%"))
        if not self.run.perks.get("insight"):
            offers.append(("perk", "insight", "球队特质：识破演技（播报噪声减半）"))
        self.rng.shuffle(offers)
        offers = offers[:3]
        idx = self._pick([o[2] for o in offers], "  🎓 赛后加练（三选一）：")
        kind, key, _ = offers[idx]
        if kind == "upgrade":
            self.run.playbook[key] = self.run.playbook.get(key, 0) + 1
            self.log(f"  ✅ {PLAY_BY_ID[key].name} 升至 Lv{self.run.playbook[key]}")
        elif kind == "learn":
            self.run.playbook[key] = 1
            self.log(f"  ✅ 学会 {PLAY_BY_ID[key].name}")
        elif key == "insight":
            self.run.perks["insight"] = True
            self.log("  ✅ 习得：识破演技")
        else:
            self.run.perks[key] = {"orb": 0.10, "clutch": 0.08}[key]
            self.log("  ✅ 习得球队特质")

    def _championship(self):
        self.log(f"\n{'═' * 58}")
        self.log("  🏆🏆🏆  战 术 大 师  🏆🏆🏆")
        self.log(f"  5 场全胜封王！战术板：{self.run.playbook}")
        self.log("═" * 58)

    def _game_over(self, result):
        self.log(f"\n{'═' * 58}")
        self.log(f"  💀 RUN OVER —— 第 {self.run.game_idx + 1} 场落败"
                 f"（{result.player_pts}:{result.opp_pts}）")
        self.log(f"  战绩 {self.run.wins} 胜")
        self.log("═" * 58)


def show_manual(log):
    for line in manual_lines():
        log(line)
