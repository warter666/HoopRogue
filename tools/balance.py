"""平衡性抽查：批量 auto 跑局，统计每场胜率与夺冠率。

用法: python tools/balance.py [局数]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hooprogue.run import TacticianRun  # noqa: E402


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    reach = [0] * 6      # 到达第 k 场的局数（下标 1~5）
    won = [0] * 6        # 在第 k 场获胜的局数
    champ = 0
    total_wins = 0
    ends = [0] * 6       # 在第 k 场出局的局数
    for seed in range(1, n + 1):
        r = TacticianRun(seed=seed, auto=True, quiet=True)
        r.log = lambda *_: None
        s = r.start()
        total_wins += s.wins
        champ += int(s.champion)
        for k in range(1, 6):
            if s.game_idx + 1 >= k or s.champion:
                reach[k] += 1
            if s.wins >= k:
                won[k] += 1
        if not s.champion:
            ends[s.game_idx + 1] += 1
    print(f"局数 {n} · 平均胜场 {total_wins / n:.2f} · 夺冠 {champ} ({champ / n:.0%})")
    for k in range(1, 6):
        rate = (won[k] / reach[k]) if reach[k] else 0.0
        print(f"  第{k}场  到达 {reach[k]:>4}  胜率 {rate:.0%}  出局 {ends[k]}")


if __name__ == "__main__":
    main()
