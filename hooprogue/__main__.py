"""CLI 入口：python -m hooprogue [--auto] [--seed N] [--quiet]"""

from __future__ import annotations

import argparse
import sys

from .game import Game


def main(argv=None) -> int:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stdin.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(
        prog="hooprogue", description="HoopRogue — 原创篮球 Roguelike")
    ap.add_argument("--seed", type=int, default=None, help="随机种子（同种子同对局）")
    ap.add_argument("--auto", action="store_true",
                    help="自动模式：随机选人/抽卡，打满一整局（用于测试/观战）")
    ap.add_argument("--quiet", action="store_true", help="只输出结果，不输出逐回合日志")
    args = ap.parse_args(argv)

    game = Game(seed=args.seed, auto=args.auto, quiet=args.quiet)
    game.start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
