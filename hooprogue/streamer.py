"""终端流式输出：所有文本打字机化，节奏随比赛事件变化。

节奏规则（策划书 §7 v0.3.1：终端为主线）：
  我方得分揭晓 = 缓慢逐字 + 短停顿（悬念）
  对方得分揭晓 = 更慢 + 更长停顿（沉重）
  打铁/失误/防守 = 中速急促
  菜单/分隔线   = 瞬时
  关键时刻/骤死/BOSS/加练 = 慢速铺垫

节奏全部由行内容推断，比赛逻辑零改动。speed=0 时全部瞬时（测试用）。
"""

from __future__ import annotations

import re
import sys
import time

RE_SCORE_US = re.compile(r"^▶ .+✓ \+\d")
RE_SCORE_THEM = re.compile(r"^◀ .+\+\d")
RE_MENU = re.compile(r"^\s*\[\d+\]")


class TermStreamer:
    def __init__(self, file=None, speed: float = 1.0):
        self.file = file or sys.stdout
        self.speed = max(0.0, speed)

    def pace(self, line: str) -> tuple[float, float]:
        """返回 (每字符延迟秒, 行后停顿秒)。纯函数，可测试。"""
        s = line.strip()
        if not s:
            return (0.0, 0.03)
        if RE_MENU.match(line):
            return (0.002, 0.0)
        if len(set(s)) <= 3 and ("═" in s or "─" in s):
            return (0.0, 0.08)                       # 分隔线瞬时
        if any(k in s for k in ("关键时刻", "骤死", "BOSS", "末节",
                                "赛前抉择", "加练")):
            return (0.03, 0.3)                       # 慢速铺垫
        if RE_SCORE_US.search(s):
            return (0.045, 0.35)                     # 我方得分：悬念揭晓
        if RE_SCORE_THEM.search(s):
            return (0.06, 0.5)                       # 对方得分：沉重
        if "补篮" in s:
            return (0.045, 0.3)
        if "掩护" in s:
            return (0.035, 0.22)
        if any(k in s for k in ("打铁", "失误", "防守成功", "逼出对方失误",
                                "勉强出手")):
            return (0.028, 0.16)
        if any(k in s for k in ("拿下", "RUN OVER", "冠军")):
            return (0.025, 0.4)
        if "结束" in s:
            return (0.02, 0.25)                      # 节末：喘口气
        if any(k in s for k in ("倾向", "意图", "进攻回合", "防守回合")):
            return (0.006, 0.04)                     # 决策面板：快
        return (0.012, 0.05)

    def write(self, *args):
        line = " ".join(str(a) for a in args)
        delay, pause = self.pace(line)
        d = delay * self.speed
        p = pause * self.speed
        if d <= 0:
            self.file.write(line + "\n")
            self.file.flush()
            if p > 0:
                time.sleep(p)
            return
        for ch in line:
            self.file.write(ch)
            self.file.flush()
            time.sleep(d)
        self.file.write("\n")
        self.file.flush()
        time.sleep(p)

    def say(self, lines):
        """AI 教练解说：固定中速流式，竖线侧栏标记与比赛事件区分。"""
        for line in lines:
            text = f"  | {line}" if line.strip() else line
            for ch in text:
                self.file.write(ch)
                self.file.flush()
                time.sleep(0.02 * self.speed)
            self.file.write("\n")
            self.file.flush()
            time.sleep(0.12 * self.speed)
