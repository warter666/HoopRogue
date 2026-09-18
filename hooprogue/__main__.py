"""CLI 入口：python -m hooprogue [--auto] [--seed N] [--quiet] [--manual]"""

from __future__ import annotations

import argparse
import sys

from .run import TacticianRun, show_manual


def main(argv=None) -> int:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stdin.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(
        prog="hooprogue", description="HoopRogue v0.2 · 战术大师 TACTICIAN")
    ap.add_argument("--seed", type=int, default=None, help="随机种子（同种子同对局）")
    ap.add_argument("--auto", action="store_true",
                    help="自动模式：AI 按播报期望值决策（测试/观战）")
    ap.add_argument("--quiet", action="store_true", help="只输出结果，不输出逐回合日志")
    ap.add_argument("--manual", action="store_true", help="查看战术手册后退出")
    args = ap.parse_args(argv)

    if args.manual:
        show_manual(print)
        return 0
    run = TacticianRun(seed=args.seed, auto=args.auto, quiet=args.quiet)
    run.start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
