"""《战术大师》测试：克制矩阵 / 播报演技 / 体能约束 / 完整 Run。"""

import io
import random
import unittest

from hooprogue.match import Match
from hooprogue.opponent import GAMES, Opponent, make_opponent
from hooprogue.plays import (DEFENSE, OFFENSE, PLAY_BY_ID, SCHEME_BY_ID,
                             counters_of, matchup, manual_lines, weaknesses_of)
from hooprogue.run import TacticianRun


class TestMatrix(unittest.TestCase):
    def test_every_play_has_counter_and_weakness(self):
        for p in OFFENSE:
            if p.id == "iso":
                continue  # 巨星球设计上不可被克制
            self.assertTrue(counters_of(p.id), msg=f"{p.id} 无克制")
        for s in DEFENSE:
            if s.cost == 0:
                continue  # 普通退防：免费中性方案，设计上无弱点
            self.assertTrue(weaknesses_of(s.id), msg=f"{s.id} 无弱点")

    def test_manual_lists_all(self):
        text = "\n".join(manual_lines())
        for p in OFFENSE:
            self.assertIn(p.name, text)

    def test_iso_immune_to_make_mod(self):
        self.assertEqual(matchup("iso", "double")[0], 0.0)
        self.assertEqual(matchup("iso", "zone")[0], 0.0)


class TestTelegraph(unittest.TestCase):
    def _opp(self, game_idx=0):
        return make_opponent(game_idx, random.Random(0))

    def test_no_bluff_early(self):
        opp = self._opp(0)
        self.assertEqual(opp.bluff_p, 0.0)
        # 诚实播报：argmax 应与真实权重 argmax 一致（统计上）
        rng = random.Random(1)
        true_top = max(opp.offense_weights, key=opp.offense_weights.get)
        hits = 0
        for _ in range(60):
            dist = opp.telegraph(opp.offense_weights, rng)
            if max(dist, key=dist.get) == true_top:
                hits += 1
        self.assertGreater(hits, 30)

    def test_boss_bluffs_sometimes(self):
        opp = self._opp(4)
        self.assertGreaterEqual(opp.bluff_p, 0.30)
        self.assertEqual(opp.stamina_per_q, 6)
        self.assertEqual(opp.target, 15)

    def test_five_games_scaling(self):
        ratings = [make_opponent(i, random.Random(0)).rating for i in range(5)]
        self.assertEqual(ratings, sorted(ratings))


class TestMatch(unittest.TestCase):
    def _play(self, seed=1, **kw):
        rng = random.Random(seed)
        opp = make_opponent(0, rng)
        picks = {"off": [], "def": []}

        def chooser(phase):
            key = "off" if phase["kind"] == "offense" else "def"
            picks[key].append(phase)
            # 永远选第一个可选项（确定性）
            if phase["kind"] == "offense":
                return {"id": next(o[0].id for o in phase["plays"] if o[3])}
            return {"id": next(o[0].id for o in phase["schemes"] if o[3])}

        logs = []
        m = Match(playbook={"push": 1, "perim": 1, "pnr": 1, "post": 1},
                  perks={"orb": 0.0, "clutch": 0.0, "insight": False},
                  opp=opp, rng=rng, log=logs.append, chooser=chooser, **kw)
        result = m.play()
        return m, result, picks

    def test_deterministic(self):
        a = self._play(seed=7)
        b = self._play(seed=7)
        self.assertEqual((a[1].won, a[1].player_pts, a[1].opp_pts),
                         (b[1].won, b[1].player_pts, b[1].opp_pts))

    def test_scores_within_bounds(self):
        _m, r, _p = self._play(seed=3)
        self.assertLessEqual(r.player_pts, 24)
        self.assertLessEqual(r.opp_pts, 30)
        self.assertNotEqual(r.player_pts, r.opp_pts)  # 骤死保证无平局

    def test_stamina_enforced(self):
        _m, r, picks = self._play(seed=5)
        # 每个进攻回合的选择都在体能预算内（chooser 只选可负担项）
        for phase in picks["off"]:
            self.assertTrue(any(o[3] for o in phase["plays"]))

    def test_opponent_usage_tracked(self):
        _m, r, _p = self._play(seed=6)
        # 对手 12+ 个防守回合都有实际战术记录（侦察备忘的数据源）
        self.assertGreaterEqual(sum(r.opp_usage.values()), 10)


class TestRun(unittest.TestCase):
    def test_auto_run_completes(self):
        run = TacticianRun(seed=1, auto=True, quiet=True)
        run.log = lambda *_: None
        state = run.start()
        self.assertLessEqual(state.wins, 5)
        self.assertGreaterEqual(state.game_idx, 0)

    def test_auto_run_deterministic(self):
        def play(seed):
            r = TacticianRun(seed=seed, auto=True, quiet=True)
            r.log = lambda *_: None
            s = r.start()
            return (s.wins, s.game_idx, s.champion, dict(s.playbook))
        self.assertEqual(play(42), play(42))

    def test_quiet_no_possession_lines(self):
        buf = io.StringIO()
        r = TacticianRun(seed=2, auto=True, quiet=True)
        r.log = buf.write
        r.start()
        self.assertNotIn("▶", buf.getvalue())

    def test_interactive_practice_input(self):
        inputs = iter(["1", "1", "1", "1", "1", "1", "1", "1", "1", "1",
                       "1", "1", "1", "1", "1", "1", "1", "1", "1", "1",
                       "1", "1", "1", "1", "1", "1", "1", "1", "1", "1",
                       "1", "1", "1", "1", "1", "1", "1", "1", "1", "1"])
        r = TacticianRun(seed=9, auto=False,
                         input_fn=lambda *_a, **_k: next(inputs))
        r.log = lambda *_: None
        state = r.start()
        self.assertIsInstance(state.wins, int)


class TestNarrate(unittest.TestCase):
    """AI 教练：决策与解说共享同一期望值排序。"""

    def _offense_phase(self):
        from hooprogue.plays import PLAY_BY_ID
        return dict(
            kind="offense", stamina=5,
            plays=[(PLAY_BY_ID["push"], 0.58, 0.10, True),
                   (PLAY_BY_ID["perim"], 0.32, 0.08, True)],
            telegraph={"man": 0.6, "zone": 0.4})

    def test_rank_and_decision_consistent(self):
        from hooprogue.narrate import narrate_offense, rank_offense
        phase = self._offense_phase()
        ranked = rank_offense(phase)
        # perim vs 盯人: (0.42-0.10)*2 - 0.048 = 0.592 > push 0.52
        self.assertEqual(ranked[0][0].id, "perim")
        lines = narrate_offense(phase)
        self.assertIn("▶ 决策：外线远投", lines[-1])

    def test_empty_rank_falls_back(self):
        from hooprogue.narrate import narrate_defense, rank_defense
        phase = dict(kind="defense", stamina=0, schemes=[],
                     telegraph={"push": 1.0})
        self.assertEqual(rank_defense(phase), [])
        self.assertIn("普通退防", narrate_defense(phase)[-1])


class TestStreamer(unittest.TestCase):
    """终端流式输出：节奏由内容推断（纯函数，不做真实 sleep）。"""

    def setUp(self):
        from hooprogue.streamer import TermStreamer
        self.st = TermStreamer(speed=0.0)

    def test_score_lines_are_slowest(self):
        menu = self.st.pace("   [1] 外线远投（1体能/2分）命中≈42% 失误≈8%")
        us = self.st.pace("  ▶ 外线远投 ✓ +2   【6:4】")
        them = self.st.pace("  ◀ ✗ 对方 传切体系 得手 +2   【5:6】")
        self.assertGreater(us[0], menu[0])          # 得分揭晓比菜单慢
        self.assertGreater(them[0], us[0])          # 对方得分比我方更沉重
        self.assertGreater(them[1], us[1])          # 停顿也更长

    def test_rules_and_dividers_are_instant(self):
        divider = self.st.pace("═" * 58)
        menu = self.st.pace("   [2] 换防（1体能）对方命中≈40%")
        self.assertEqual(divider[0], 0.0)
        self.assertEqual(menu[1], 0.0)

    def test_write_streams_to_buffer(self):
        import io
        buf = io.StringIO()
        from hooprogue.streamer import TermStreamer
        st = TermStreamer(file=buf, speed=0.0)
        st.write("  ▶ 外线远投 ✓ +2")
        st.say(["决策：外线远投"])
        text = buf.getvalue()
        self.assertIn("外线远投", text)
        self.assertIn("决策", text)


if __name__ == "__main__":
    unittest.main()
