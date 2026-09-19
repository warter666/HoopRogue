"""CLI 入口：python -m hooprogue [--auto] [--seed N] [--speed X] [--manual]

终端流式模式是唯一前端：所有输出打字机化，节奏随得分/失分变化。
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
        prog="hooprogue", description="HoopRogue v0.5 · 战术大师 TACTICIAN")
    ap.add_argument("--auto", action="store_true",
                    help="自动模式：AI 教练流式解说并决策（观战）")
    ap.add_argument("--quiet", action="store_true",
                    help="只输出结果，不逐回合直播")
    ap.add_argument("--seed", type=int, default=None, help="随机种子（同种子同对局）")
    ap.add_argument("--speed", type=float, default=1.0,
                    help="流式输出速度倍率（0.3 快进 / 0 瞬时）")
    ap.add_argument("--manual", action="store_true", help="查看战术手册后退出")
    args = ap.parse_args(argv)

    if args.manual:
        from .plays import manual_lines
        for line in manual_lines():
            print(line)
        return 0

    from .run import TacticianRun, attach_coach
    from .streamer import TermStreamer

    streamer = TermStreamer(speed=args.speed)
    run = TacticianRun(seed=args.seed, auto=args.auto, quiet=args.quiet)
    if not args.quiet:
        run.log = streamer.write
        run.match_log = streamer.write
        if args.auto:
            attach_coach(run, streamer.say)
    run.start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
