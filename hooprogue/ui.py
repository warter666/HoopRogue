"""文本 UI 工具（对齐友好：不使用闭合右边框）。"""

from __future__ import annotations

from .cards import RARITY_NAME
from .match import TEMPO_NAME

LINE = "  " + "═" * 52


def banner(log):
    log(LINE)
    log("   H O O P · R O G U E    🏀 街球生存赛")
    log("   选人 → 打球 → 赢了抽卡 → 变强 → 干翻 BOSS")
    log(LINE)


def card_line(card, idx=None):
    head = f"  [{idx}] " if idx is not None else "  "
    return (f"{head}{card.icon} {card.name} "
            f"({'★' * card.rarity} {RARITY_NAME[card.rarity]}) — {card.desc}")


def box_table(us, them) -> str:
    qs = len(us.q_pts)
    lines = ["  " + " " * 10 + "".join(f"Q{i+1:<4}" for i in range(qs)) + "总计"]
    lines.append("  " + "我方".ljust(8) + "".join(f"{p:<5}" for p in us.q_pts) + f"{us.pts}")
    lines.append("  " + "对方".ljust(8) + "".join(f"{p:<5}" for p in them.q_pts) + f"{them.pts}")
    return "\n".join(lines)


def run_status(run) -> str:
    cards = " ".join(c.icon for c in run.cards) or "（无）"
    return (f"  📊 第{run.round}轮 · {run.wins}胜 · 总得分 {run.total_pts} · "
            f"卡牌: {cards}")


def tempo_menu() -> str:
    return "  节奏选择 [1]稳扎稳打(少失误) [2]均衡 [3]极速跑轰(多回合/多失误)"


TEMPO_BY_KEY = {"1": "slow", "2": "balanced", "3": "fast", "slow": "slow",
                "balanced": "balanced", "fast": "fast"}
TEMPO_TITLE = {v: TEMPO_NAME[v] for v in TEMPO_NAME}
