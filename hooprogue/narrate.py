"""AI 教练：仿 LLM 流式输出的本地叙事引擎（零 API，全部真实对局数据）。

感知（对方倾向）→ 分析（选项×克制）→ 权衡（首选 vs 次选）→ ▶ 决策。
rank_offense / rank_defense 是决策与解说的唯一真相源——
屏幕上"想"的和实际"做"的完全一致（同种子同解说，可测试）。
"""

from __future__ import annotations

from .plays import SCHEME_BY_ID, matchup


def rank_offense(phase: dict) -> list:
    """进攻选项按期望值排序：[(play, val)]，仅可负担项。"""
    cands = [(play, p_make * play.pts - 0.6 * p_to)
             for (play, p_make, p_to, afford) in phase["plays"] if afford]
    return sorted(cands, key=lambda t: -t[1])


def rank_defense(phase: dict) -> list:
    """防守方案按对方期望收益升序：[(scheme, val)]，仅可负担项。"""
    cands = [(scheme, opp_make + 0.5 * opp_to)
             for (scheme, opp_make, opp_to, afford) in phase["schemes"] if afford]
    return sorted(cands, key=lambda t: t[1])


def _top2(dist: dict) -> list:
    return sorted(dist.items(), key=lambda kv: -kv[1])[:2]


def narrate_offense(phase: dict) -> list:
    lines = []
    tg = phase["telegraph"]
    tops = _top2(tg)
    lines.append("对方防守倾向: "
                 + " / ".join(f"{SCHEME_BY_ID[k].name} {v:.0%}" for k, v in tops))
    lines.append(f"体能 {phase['stamina']}，盘点可用的战术…")
    ranked = rank_offense(phase)
    if not ranked:
        return lines + ["体能耗尽，只能勉强出手…", "▶ 决策：😮 勉强出手"]
    best, best_val = ranked[0]
    alt = ranked[1] if len(ranked) > 1 else None
    top_scheme = tops[0][0]
    mm = matchup(best.id, top_scheme)[0]
    if mm < -0.05:
        lines.append(f"⚠ {best.name} 撞在对方 {SCHEME_BY_ID[top_scheme].name} 枪口上")
    elif mm > 0.05:
        lines.append(f"✧ {best.name} 正好强吃对方 {SCHEME_BY_ID[top_scheme].name}")
    if alt is not None:
        lines.append(f"权衡：{best.name} 期望 {best_val:.2f} vs "
                     f"{alt[0].name} {alt[1]:.2f}")
    lines.append(f"▶ 决策：{best.name}")
    return lines


def narrate_defense(phase: dict) -> list:
    lines = []
    tg = phase["telegraph"]
    tops = _top2(tg)
    from .plays import PLAY_BY_ID
    lines.append("对方进攻意图: "
                 + " / ".join(f"{PLAY_BY_ID[k].name} {v:.0%}" for k, v in tops))
    lines.append(f"体能 {phase['stamina']}，考虑防守方案…")
    ranked = rank_defense(phase)
    if not ranked:
        return lines + ["体能耗尽，只能普通退防…", "▶ 决策：😴 普通退防"]
    best, best_val = ranked[0]
    top_play = tops[0][0]
    mm = matchup(top_play, best.id)
    if mm[0] < -0.05:
        lines.append(f"✧ {best.name} 正好克制对方 {PLAY_BY_ID[top_play].name}")
    if mm[1] > 0.05:
        lines.append(f"★ 该方案还能抬高对方失误率")
    lines.append(f"▶ 决策：{best.name}")
    return lines


def narrate_choice(header: str, options: list, picked: int) -> list:
    """通用选择（赛前抉择/加练）的简短解说。"""
    return [f"{header}", f"候选 {len(options)} 项…", f"▶ 决策：{options[picked]}"]
