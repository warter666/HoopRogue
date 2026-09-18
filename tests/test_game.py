"""HoopRogue 测试：确定性、卡牌效果、护盾、Boss、完整 run。"""

import io
import unittest

from hooprogue.cards import CARDS, CARD_BY_ID, compute_mods, draw_three
from hooprogue.game import Game, RunState
from hooprogue.match import Match
from hooprogue.player import ARCHETYPES, make_opponent

import random


def silent_run(seed, quiet=True, records_fn=None):
    g = Game(seed=seed, auto=True, quiet=quiet, records_fn=records_fn)
    g.log = lambda *_: None
    return g.start()


class TestCards(unittest.TestCase):
    def test_compute_mods(self):
        m = compute_mods([CARD_BY_ID["court_vision"], CARD_BY_ID["iron_wall"]])
        self.assertAlmostEqual(m.tov_mult, 0.65)
        self.assertTrue(m.shield_on)

    def test_draw_three_no_duplicates_or_owned(self):
        rng = random.Random(0)
        owned = {c.id for c in CARDS[:6]}
        for _ in range(30):
            picks = draw_three(rng, owned)
            self.assertLessEqual(len(picks), 3)
            ids = [c.id for c in picks]
            self.assertEqual(len(ids), len(set(ids)))
            self.assertTrue(all(c.id not in owned for c in picks))


class TestMatch(unittest.TestCase):
    def _match(self, card_ids=(), seed=1, tempo="balanced"):
        rng = random.Random(seed)
        mods = compute_mods([CARD_BY_ID[i] for i in card_ids])
        opp = make_opponent(1, rng)
        logs = []
        m = Match(arch=ARCHETYPES[0], mods=mods, extra_bonus=0.0, opp=opp,
                  rng=rng, tempo=tempo, log=logs.append)
        return m, m.play(), logs

    def test_deterministic(self):
        r1 = self._match(seed=7)[1]
        r2 = self._match(seed=7)[1]
        self.assertEqual((r1.us.pts, r1.them.pts, r1.won),
                         (r2.us.pts, r2.them.pts, r2.won))

    def test_court_vision_reduces_turnovers(self):
        tov_plain = sum(self._match(seed=s)[1].us.tov for s in range(30))
        tov_cv = sum(self._match(card_ids=("court_vision",), seed=s)[1].us.tov
                     for s in range(30))
        self.assertLess(tov_cv, tov_plain,
                        msg=f"court_vision 后失误 {tov_cv} 应少于基础 {tov_plain}")

    def test_shield_blocks_scores(self):
        m, res, logs = self._match(card_ids=("iron_wall",), seed=11)
        text = "\n".join(logs)
        self.assertIn("护盾", text)

    def test_boss_every_fifth_round(self):
        rng = random.Random(0)
        self.assertFalse(make_opponent(3, rng).is_boss)
        self.assertTrue(make_opponent(5, rng).is_boss)
        self.assertEqual(make_opponent(5, random.Random(0)).trait_id, "zone")


class TestGame(unittest.TestCase):
    def test_auto_run_completes(self):
        run = silent_run(seed=1)
        self.assertGreaterEqual(run.round, 1)
        self.assertLessEqual(run.wins, 12)
        self.assertGreaterEqual(run.round, run.wins)  # 至少打了 wins 场

    def test_auto_run_deterministic(self):
        a, b = silent_run(seed=42), silent_run(seed=42)
        self.assertEqual((a.wins, a.round, a.total_pts, a.card_ids()),
                         (b.wins, b.round, b.total_pts, b.card_ids()))

    def test_quiet_mode_silences_possessions_only(self):
        buf = io.StringIO()
        game = Game(seed=3, auto=True, quiet=True, records_fn=None)
        game.log = buf.write
        game.start()
        out = buf.getvalue()
        self.assertNotIn("▶", out)   # 逐回合日志被静默
        self.assertNotIn("◀", out)
        self.assertIn("第 1 场", out)  # 场次结构保留

    def test_records_callback_called(self):
        calls = []
        Game(seed=5, auto=True, quiet=True,
             records_fn=lambda w, c: calls.append((w, c))).start()
        self.assertEqual(len(calls), 1)
        wins, champ = calls[0]
        self.assertGreaterEqual(wins, 0)
        self.assertIsInstance(champ, bool)


if __name__ == "__main__":
    unittest.main()
