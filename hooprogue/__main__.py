"""CLI 入口：python -m hooprogue [--cli] [--auto] [--seed N] [--manual] [--selftest]

默认启动 tkinter 图形界面；--cli 进入终端模式（可叠加 --auto/--quiet）。
"""

from __future__ import annotations

import argparse
import sys


def main(argv=None) -> int:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stdin.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(
        prog="hooprogue", description="HoopRogue v0.3 · 战术大师 TACTICIAN")
    ap.add_argument("--cli", action="store_true", help="终端模式（默认图形界面）")
    ap.add_argument("--auto", action="store_true",
                    help="自动模式（终端：AI 按播报决策；图形界面：AI 教练流式解说）")
    ap.add_argument("--quiet", action="store_true", help="终端模式：只输出结果")
    ap.add_argument("--seed", type=int, default=None, help="随机种子（同种子同对局）")
    ap.add_argument("--manual", action="store_true", help="查看战术手册后退出")
    ap.add_argument("--selftest", action="store_true", help="图形界面无头自检")
    args = ap.parse_args(argv)

    if args.selftest:
        from .gui import run_selftest
        return 0 if run_selftest() else 1
    if args.manual:
        from .plays import manual_lines
        for line in manual_lines():
            print(line)
        return 0
    if args.cli:
        from .run import TacticianRun
        TacticianRun(seed=args.seed, auto=args.auto, quiet=args.quiet).start()
        return 0
    try:
        from .gui import run_gui
        run_gui(args.seed)
    except Exception as e:
        print(f"图形界面不可用（{e}），切换到终端模式。\n")
        from .run import TacticianRun
        TacticianRun(seed=args.seed, auto=args.auto, quiet=False).start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
