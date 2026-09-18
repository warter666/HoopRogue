"""平衡性抽查：批量自动跑局，统计胜场分布。

用法: python tools/balance.py [局数]
"""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hooprogue.game import Game  # noqa: E402


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    hist = Counter()
    champ = 0
    total_wins = 0
    for seed in range(1, n + 1):
        g = Game(seed=seed, auto=True, quiet=True)
        g.log = lambda *_: None
        run = g.start()
        hist[run.wins] += 1
        total_wins += run.wins
        champ += int(run.wins >= 12)
    print(f"局数 {n} · 平均胜场 {total_wins / n:.2f} · 夺冠 {champ}")
    for wins in range(0, 13):
        if hist[wins]:
            bar = "█" * hist[wins]
            print(f"  {wins:>2} 胜  {bar} {hist[wins]}")


if __name__ == "__main__":
    main()
