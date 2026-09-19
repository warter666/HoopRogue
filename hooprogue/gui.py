"""《战术大师》tkinter 图形界面。

线程模型（策划书 §7.1）：比赛逻辑跑在后台线程；tkinter 主线程只渲染；
Queue 通信。交互模式的决策请求会阻塞工作线程，等待界面按钮点击；
观战模式由 AI 教练（narrate.py，零 API）流式解说并决策。

逻辑模块零改动——GUI 只是另一个"前端"。
"""

from __future__ import annotations

import queue
import re
import threading
import time
import tkinter as tk
from tkinter import font as tkfont

from .run import TacticianRun

from .narrate import narrate_choice, narrate_defense, narrate_offense

# 调色板
C_BG = "#0e1420"
C_PANEL = "#161d2b"
C_PANEL2 = "#1b2430"
C_TEXT = "#e6edf3"
C_DIM = "#7d8b9d"
C_ACCENT = "#7fd4ff"
C_GOLD = "#ffd479"
C_ORANGE = "#ff9f43"
C_BLUE = "#7fb3ff"
C_GREEN = "#7ce38b"
C_RED = "#ff7b72"

SCORE_RE = re.compile(r"【(\d+):(\d+)】")
MENU_RE = re.compile(r"\s*\[(\d+)\]\s+(.*)")


class MatchWorker(threading.Thread):
    """比赛逻辑工作线程：所有界面交互经由队列。"""

    def __init__(self, q: queue.Queue, auto: bool, seed=None, fast=False):
        super().__init__(daemon=True)
        self.q = q
        self.auto = auto
        self.seed = seed
        self.fast = fast          # 自检/快速模式：流式延迟归零
        self.answer = None
        self.ev = threading.Event()
        self._menu_buf: list[str] = []
        self.tactician: TacticianRun | None = None

    # ---------------------------------------------------------------- 回调
    def _log(self, *a):
        line = " ".join(str(x) for x in a)
        self.q.put(("log", line))
        if MENU_RE.match(line):
            self._menu_buf.append(line.strip())

    def _input(self, prompt=""):
        """通用编号输入：把收集到的菜单行发给界面渲染成按钮并等待点击。"""
        self.q.put(("prompt", prompt, list(self._menu_buf)))
        self._menu_buf = []
        self.ev.clear()
        self.ev.wait()
        return self.answer

    def _stream(self, lines: list):
        """AI 教练打字机输出（fast 模式零延迟）。"""
        for line in lines:
            step = 3 if self.fast else 2
            for k in range(0, len(line), step):
                self.q.put(("ai", line[k:k + step]))
                if not self.fast:
                    time.sleep(0.024)
            self.q.put(("ai_line", None))
            if not self.fast:
                time.sleep(0.18)

    # ---------------------------------------------------------------- 决策包装
    def _wrap_decision(self, run: TacticianRun):
        """观战模式：AI 教练先流式思考，再用与终端版一致的期望值函数决策。"""

        def choose(phase: dict) -> dict:
            if phase["kind"] == "offense":
                self._stream(narrate_offense(phase))
            else:
                self._stream(narrate_defense(phase))
            return run._auto_action(phase)

        orig_pick = run._pick

        def pick(options: list, header: str) -> int:
            idx = orig_pick(options, header)
            self._stream(narrate_choice(header, options, idx))
            return idx

        run._choose_action = choose
        run._pick = pick

    # ---------------------------------------------------------------- 主流程
    def run(self):
        try:
            run = TacticianRun(seed=self.seed, auto=self.auto, quiet=False,
                               input_fn=self._input)
            run.log = self._log
            if self.auto:
                self._wrap_decision(run)
                self.q.put(("ai_line", None))
                self._stream(["AI 教练上线。观测比赛，权衡每一回合…"])
            self.tactician = run
            state = run.start()
            self.q.put(("run_end", state))
        except Exception as e:  # 任何异常都要让界面脱离等待状态
            self.q.put(("error", f"{type(e).__name__}: {e}"))
            self.q.put(("run_end", None))


class TacticianGUI:
    def __init__(self, root: tk.Tk, seed=None, selftest=False):
        self.root = root
        self.seed = seed
        self.selftest = selftest
        self.q: queue.Queue = queue.Queue()
        self.worker: MatchWorker | None = None
        self.finished = False

        root.title("HoopRogue · 战术大师 TACTICIAN")
        root.configure(bg=C_BG)
        header = ("Microsoft YaHei UI", 13, "bold")
        body = ("Microsoft YaHei UI", 11)
        mono = ("Consolas", 11)
        self._fonts = (header, body, mono)

        top = tk.Frame(root, bg=C_PANEL)
        top.pack(fill="x")
        self.lbl_title = tk.Label(top, text="战 术 大 师 · TACTICIAN",
                                  fg=C_GOLD, bg=C_PANEL, font=header)
        self.lbl_title.pack(side="left", padx=14, pady=8)
        self.lbl_match = tk.Label(top, text="准备就绪", fg=C_TEXT,
                                  bg=C_PANEL, font=body)
        self.lbl_match.pack(side="left", padx=14)
        self.lbl_score = tk.Label(top, text="0 : 0", fg=C_ACCENT, bg=C_PANEL,
                                  font=("Consolas", 16, "bold"))
        self.lbl_score.pack(side="right", padx=14)

        mid = tk.Frame(root, bg=C_BG)
        mid.pack(fill="both", expand=True)
        # 左：AI 教练 + 日志
        left = tk.Frame(mid, bg=C_BG)
        left.pack(side="left", fill="both", expand=True, padx=(10, 4), pady=8)
        tk.Label(left, text="AI 教练（实时思考）", fg=C_ACCENT, bg=C_BG,
                 font=body, anchor="w").pack(fill="x")
        self.txt_ai = tk.Text(left, height=10, bg=C_PANEL, fg=C_TEXT,
                              font=mono, relief="flat", state="disabled",
                              wrap="word")
        self.txt_ai.pack(fill="both", expand=False, pady=(2, 8))
        tk.Label(left, text="比赛日志", fg=C_DIM, bg=C_BG,
                 font=body, anchor="w").pack(fill="x")
        self.txt_log = tk.Text(left, bg=C_PANEL2, fg=C_TEXT, font=mono,
                               relief="flat", state="disabled", wrap="word")
        self.txt_log.pack(fill="both", expand=True, pady=(2, 0))
        for tag, color in (("p", C_ORANGE), ("o", C_BLUE), ("good", C_GREEN),
                           ("bad", C_RED), ("dim", C_DIM), ("gold", C_GOLD)):
            self.txt_log.tag_configure(tag, foreground=color)
        self.txt_ai.tag_configure("gold", foreground=C_GOLD,
                                  font=("Consolas", 11, "bold"))

        # 右：决策面板
        right = tk.Frame(mid, bg=C_BG, width=330)
        right.pack(side="right", fill="both", padx=(4, 10), pady=8)
        right.pack_propagate(False)
        self.lbl_decide = tk.Label(right, text="决策台", fg=C_GOLD, bg=C_BG,
                                   font=header, anchor="w")
        self.lbl_decide.pack(fill="x", pady=(0, 6))
        self.decide_area = tk.Frame(right, bg=C_BG)
        self.decide_area.pack(fill="both", expand=True)

        self._start_screen()

    # ------------------------------------------------------------------ 屏幕
    def _clear_decide(self):
        for w in self.decide_area.winfo_children():
            w.destroy()

    def _start_screen(self):
        self.lbl_match.config(text="准备就绪")
        self.lbl_score.config(text="0 : 0")
        self._clear_decide()
        header, body, _ = self._fonts
        tk.Label(self.decide_area,
                 text="5 场成长弧线\n没有技能卡\n只有战术板",
                 fg=C_TEXT, bg=C_BG, font=body, justify="left").pack(pady=18)
        tk.Button(self.decide_area, text="我来指挥（交互）", fg=C_BG, bg=C_ACCENT,
                  font=header, relief="flat", padx=18, pady=8,
                  command=lambda: self.start_run(auto=False)).pack(fill="x", pady=6)
        tk.Button(self.decide_area, text="观看 AI 教练（观战）", fg=C_TEXT,
                  bg=C_PANEL2, font=header, relief="flat", padx=18, pady=8,
                  command=lambda: self.start_run(auto=True)).pack(fill="x", pady=6)
        tk.Button(self.decide_area, text="退出", fg=C_DIM, bg=C_BG,
                  font=body, relief="flat",
                  command=self.root.destroy).pack(fill="x", pady=6)

    def start_run(self, auto: bool):
        self._clear_decide()
        self.lbl_decide.config(text="决策台")
        self.lbl_match.config(text="比赛进行中…")
        self._append_log_clear()
        self.finished = False
        self.worker = MatchWorker(self.q, auto=auto, seed=self.seed,
                                  fast=self.selftest)
        self.worker.start()
        self._poll()

    # ------------------------------------------------------------------ 队列
    def _poll(self):
        if self.selftest:
            return  # 自检模式直接调 process_queue
        try:
            self.process_queue()
        finally:
            self.root.after(40, self._poll)

    def process_queue(self):
        while True:
            try:
                kind, payload = self.q.get_nowait()
            except queue.Empty:
                return
            if kind == "log":
                self._append_log(payload)
            elif kind == "ai":
                self._append_ai(payload)
            elif kind == "ai_line":
                self._append_ai("\n")
            elif kind == "prompt":
                self._show_prompt(*payload)
            elif kind == "run_end":
                self.finished = True
                self._end_screen(payload)
            elif kind == "error":
                self._append_log(f"‼ {payload}")

    # ------------------------------------------------------------------ 渲染
    def _append_log_clear(self):
        self.txt_log.config(state="normal")
        self.txt_log.delete("1.0", "end")
        self.txt_log.config(state="disabled")
        self.txt_ai.config(state="normal")
        self.txt_ai.delete("1.0", "end")
        self.txt_ai.config(state="disabled")

    def _append_log(self, line: str):
        tag = "dim"
        s = line.strip()
        if s.startswith("▶"):
            tag = "p"
        elif s.startswith("◀"):
            tag = "o"
        elif "拿下" in s or "冠军" in s:
            tag = "good"
        elif "RUN OVER" in s:
            tag = "bad"
        elif "篮球" in s or "第" in s and "场" in s:
            tag = "gold"
        self.txt_log.config(state="normal")
        self.txt_log.insert("end", line + "\n", tag)
        self.txt_log.see("end")
        self.txt_log.config(state="disabled")
        m = SCORE_RE.search(line)
        if m:
            self.lbl_score.config(text=f"{m.group(1)} : {m.group(2)}")
        if "🏀 第" in line:
            self.lbl_match.config(text=line.strip().lstrip("🏀 ").strip())

    def _append_ai(self, chunk: str):
        self.txt_ai.config(state="normal")
        if chunk == "\n":
            self.txt_ai.insert("end", "\n")
        else:
            self.txt_ai.insert("end", chunk)
        self.txt_ai.see("end")
        self.txt_ai.config(state="disabled")

    def _show_prompt(self, prompt: str, options: list):
        self._clear_decide()
        header, body, _ = self._fonts
        title = prompt.strip() or "请选择"
        self.lbl_decide.config(text=title[:24])
        if not options:
            tk.Label(self.decide_area, text=title, fg=C_TEXT, bg=C_BG,
                     font=body, wraplength=300).pack(pady=10)
            return
        for line in options:
            m = MENU_RE.match(line)
            if not m:
                continue
            num, text = m.group(1), m.group(2)
            tk.Button(self.decide_area, text=f"[{num}] {text}",
                      fg=C_TEXT, bg=C_PANEL2, font=body, relief="flat",
                      anchor="w", padx=10, pady=6,
                      activebackground=C_ACCENT, activeforeground=C_BG,
                      command=lambda n=num: self._answer_prompt(n)
                      ).pack(fill="x", pady=4)

    def _answer_prompt(self, num: str):
        if self.worker is None or not self.worker.is_alive():
            return
        self._clear_decide()
        self.lbl_decide.config(text="决策已下达 ✓")
        self.worker.answer = num
        self.worker.ev.set()

    def _end_screen(self, state):
        header, body, _ = self._fonts
        self._clear_decide()
        if state is None:
            self.lbl_decide.config(text="运行出错")
            tk.Label(self.decide_area, fg=C_RED, bg=C_BG, font=body,
                     text="工作线程异常，详见日志").pack(pady=10)
        else:
            if state.champion:
                self.lbl_decide.config(text="冠军！")
                sub = f"5 场全胜封王！总胜场 {state.wins}"
            else:
                self.lbl_decide.config(text="💀 RUN OVER")
                sub = f"止步第 {state.game_idx + 1} 场 · {state.wins} 胜"
            tk.Label(self.decide_area, text=sub, fg=C_TEXT, bg=C_BG,
                     font=body, wraplength=300).pack(pady=10)
        tk.Button(self.decide_area, text="再来一局", fg=C_BG, bg=C_ACCENT,
                  font=header, relief="flat", padx=14, pady=6,
                  command=self._start_screen).pack(fill="x", pady=6)
        tk.Button(self.decide_area, text="退出", fg=C_DIM, bg=C_BG,
                  font=body, relief="flat",
                  command=self.root.destroy).pack(fill="x", pady=6)


def run_gui(seed=None):
    root = tk.Tk()
    root.geometry("1080x680")
    TacticianGUI(root, seed=seed)
    root.mainloop()


def run_selftest() -> bool:
    """无头自检：AI 观战模式全流程（fast 模式，流式延迟归零）。"""
    import sys as _sys
    root = tk.Tk()
    root.withdraw()
    app = TacticianGUI(root, seed=7, selftest=True)
    app.start_run(auto=True)
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        app.process_queue()
        root.update()
        if app.finished:
            break
        time.sleep(0.001)
    ok = app.finished and app.worker is not None and app.worker.tactician is not None \
        and app.worker.tactician.run is not None
    wins = app.worker.tactician.run.wins if ok else -1
    root.destroy()
    if not ok:
        print("SELFTEST FAILED")
        return False
    print(f"SELFTEST OK · AI 观战模式跑完整局 · {wins} 胜")
    _sys.stdout.flush()
    return True
