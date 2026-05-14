"""
cli.py — Terminal UI for SycoUI.

All interactive prompts and visual rendering live here so that
main.py stays focused on orchestration logic.
"""

import getpass
import os
import shutil
import sys
import time
from typing import Optional

# Enable ANSI escape codes on Windows terminals (no-op on macOS/Linux).
if sys.platform == "win32":
    os.system("")

# ── Colours ───────────────────────────────────────────────────────────────────

_R   = "\033[0m"    # reset
_B   = "\033[1m"    # bold
_DIM = "\033[2m"    # dim
_CY  = "\033[96m"   # bright cyan   — logo, borders, prompts
_GR  = "\033[92m"   # bright green  — confirmations
_YL  = "\033[93m"   # bright yellow — menus, warnings
_WH  = "\033[97m"   # bright white  — body text

# ── Startup banner ────────────────────────────────────────────────────────────

# ANSI Shadow rendering of "SycoUI"
_ART = [
    "███████╗ ██╗   ██╗  ██████╗  ██████╗     ██╗   ██╗ ██╗",
    "██╔════╝ ╚██╗ ██╔╝ ██╔════╝ ██╔═══██╗    ██║   ██║ ██║",
    "███████╗  ╚████╔╝  ██║      ██║   ██║    ██║   ██║ ██║",
    "╚════██║   ╚██╔╝   ██║      ██║   ██║    ██║   ██║ ██║",
    "███████║    ██║    ╚██████╗ ╚██████╔╝    ╚██████╔╝ ██║",
    "╚══════╝    ╚═╝     ╚═════╝  ╚═════╝      ╚═════╝  ╚═╝",
]
_SUBTITLE = "AI Sycophancy Research Tool"
_BW = max(len(line) for line in _ART) + 6   # banner box inner width


def print_banner() -> None:
    def _row(text: str = "", style: str = "") -> None:
        print(f"  {_CY}║{_R}{style}{text.center(_BW)}{_R}{_CY}║{_R}")

    print()
    print(f"  {_CY}╔{'═' * _BW}╗{_R}")
    _row()
    for line in _ART:
        _row(line, _B + _CY)
    _row()
    _row(_SUBTITLE, _DIM + _WH)
    _row()
    print(f"  {_CY}╚{'═' * _BW}╝{_R}")
    print()


# ── Shared menu helper ────────────────────────────────────────────────────────

def _numbered_menu(title: str, options: list[str]) -> int:
    """Render a styled numbered menu; return the 0-based index of the choice."""
    mw    = max(len(title) + 4, max(len(o) + 8 for o in options))
    label = f" {title} "
    pad_l = (mw - len(label)) // 2
    pad_r = mw - len(label) - pad_l

    print()
    print(f"  {_YL}╔{'═' * mw}╗{_R}")
    print(f"  {_YL}║{' ' * pad_l}{_B}{_WH}{label}{_R}{_YL}{' ' * pad_r}║{_R}")
    print(f"  {_YL}╠{'═' * mw}╣{_R}")
    for i, opt in enumerate(options, 1):
        prefix = f" [{i}]  "
        pad    = mw - len(prefix) - len(opt)
        print(f"  {_YL}║{_YL}{prefix}{_R}{_WH}{opt}{_R}{' ' * max(0, pad)}{_YL}║{_R}")
    print(f"  {_YL}╚{'═' * mw}╝{_R}")
    print()

    while True:
        choice = input(f"  {_CY}> {_R}Enter number (1-{len(options)}): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            return int(choice) - 1
        print(f"  {_YL}! {_R}Invalid — please enter a number between 1 and {len(options)}.")


# ── Selection functions ───────────────────────────────────────────────────────

def select_mode() -> str:
    """Ask whether to run via browser scraping or direct API. Returns "Browser" or "API"."""
    options  = ["Browser   (scrape commercial UI, requires manual login)",
                "API       (direct provider API call, requires API key)"]
    keys     = ["Browser", "API"]
    selected = keys[_numbered_menu("Select a Mode", options)]
    print(f"  {_GR}> Mode selected:{_R}    {_B}{selected}{_R}")
    print()
    return selected


def select_model(backend_map: dict, mode_map: dict) -> str:
    """Show a model selection menu and return the chosen model name."""
    options  = list(backend_map.keys())
    labels   = [f"{name:<10}(mode: {mode_map[name]})" for name in options]
    selected = options[_numbered_menu("Select a Model", labels)]
    print(f"  {_GR}> Model selected:{_R}   {_B}{selected}{_R}")
    print()
    return selected


def prompt_api_key(provider: str, env_var: str) -> str:
    """
    Resolve an API key for *provider*.

    Order:
      1. Read from environment variable *env_var* if set.
      2. Otherwise, prompt the user with getpass (no terminal echo).

    Keys are never written to disk or logged.
    """
    key = os.environ.get(env_var, "").strip()
    if key:
        print(f"  {_GR}> Using {provider} API key from ${env_var}{_R}")
        print()
        return key

    print()
    print(f"  {_YL}╔{'═' * 46}╗{_R}")
    print(f"  {_YL}║{_R}{_B}{_WH}{f'  {provider} API Key Required'.ljust(46)}{_R}{_YL}║{_R}")
    print(f"  {_YL}╠{'═' * 46}╣{_R}")
    print(f"  {_YL}║{_R}  {_WH}Tip: set ${env_var} to skip this prompt.{_R}{' ' * (46 - 39 - len(env_var))}{_YL}║{_R}")
    print(f"  {_YL}╚{'═' * 46}╝{_R}")
    try:
        key = getpass.getpass(f"  {_CY}> {_R}{provider} API key (input hidden): ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        raise
    if not key:
        raise ValueError(f"No {provider} API key provided.")
    print(f"  {_GR}> {provider} API key accepted.{_R}")
    print()
    return key


def select_dataset(datasets_dir: str) -> tuple[str, str]:
    """Scan datasets_dir for CSVs, show a menu, and return (abs_path, stem)."""
    if not os.path.isdir(datasets_dir):
        raise FileNotFoundError(f"DataSets directory not found: {datasets_dir}")
    csv_files = sorted(f for f in os.listdir(datasets_dir) if f.lower().endswith(".csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {datasets_dir}")

    selected = csv_files[_numbered_menu("Select a Dataset", csv_files)]
    print(f"  {_GR}> Dataset selected:{_R} {_B}{selected}{_R}")
    print()
    stem = os.path.splitext(selected)[0]
    return os.path.join(datasets_dir, selected), stem


def select_subset(total: int) -> int:
    """Ask how many prompts to run; Enter or 0 means all."""
    if total == 0:
        return 0

    mw = 46
    print(f"  {_YL}╔{'═' * mw}╗{_R}")
    print(f"  {_YL}║{_R}{_B}{_WH}{'  Subset Selection'.center(mw)}{_R}{_YL}║{_R}")
    print(f"  {_YL}╠{'═' * mw}╣{_R}")
    info = f"  Dataset contains {total} prompts.  "
    print(f"  {_YL}║{_R}{_WH}{info.ljust(mw)}{_R}{_YL}║{_R}")
    print(f"  {_YL}╚{'═' * mw}╝{_R}")
    print()

    while True:
        raw = input(f"  {_CY}> {_R}Subset size (1-{total}), or Enter for all: ").strip()
        if raw == "" or raw == "0":
            print(f"  {_GR}> Running all {_B}{total}{_R} prompts.")
            print()
            return total
        if raw.isdigit() and 1 <= int(raw) <= total:
            n = int(raw)
            print(f"  {_GR}> Running first {_B}{n}{_R} of {total} prompts.")
            print()
            return n
        print(f"  {_YL}! {_R}Invalid — enter 1-{total} or press Enter for all.")


def select_repeats() -> int:
    """Ask how many times each prompt should be repeated; Enter or 1 means once."""
    mw = 46
    print(f"  {_YL}╔{'═' * mw}╗{_R}")
    print(f"  {_YL}║{_R}{_B}{_WH}{'  Repeat Selection'.center(mw)}{_R}{_YL}║{_R}")
    print(f"  {_YL}╠{'═' * mw}╣{_R}")
    note = "  Results saved as  1-1  1-2  2-1  etc.  "
    print(f"  {_YL}║{_R}{_DIM}{_WH}{note.ljust(mw)}{_R}{_YL}║{_R}")
    print(f"  {_YL}╚{'═' * mw}╝{_R}")
    print()

    while True:
        raw = input(f"  {_CY}> {_R}Repeats per prompt (N), or Enter for 1: ").strip()
        if raw == "" or raw == "1":
            print(f"  {_GR}> Each prompt will run {_B}1{_R} time.")
            print()
            return 1
        if raw.isdigit() and int(raw) >= 1:
            n = int(raw)
            print(f"  {_GR}> Each prompt will repeat {_B}{n}{_R} times.")
            print()
            return n
        print(f"  {_YL}! {_R}Invalid — enter a positive number or press Enter for 1.")


def select_base_prompt() -> bool:
    """Ask whether to constrain model output to only YTA or NTA. Default is off."""
    mw = 46
    print(f"  {_YL}+{'=' * mw}+{_R}")
    print(f"  {_YL}|{_R}{_B}{_WH}{'  Base Prompt'.center(mw)}{_R}{_YL}|{_R}")
    print(f"  {_YL}+{'=' * mw}+{_R}")
    note = "  Enter keeps dataset prompts unchanged.  "
    print(f"  {_YL}|{_R}{_DIM}{_WH}{note.ljust(mw)}{_R}{_YL}|{_R}")
    print(f"  {_YL}+{'=' * mw}+{_R}")
    print()

    while True:
        raw = input(f"  {_CY}> {_R}Force answers to only YTA or NTA? [y/N]: ").strip().lower()
        if raw in ("", "n", "no"):
            print(f"  {_GR}> Base prompt:{_R} {_B}disabled{_R}")
            print()
            return False
        if raw in ("y", "yes"):
            print(f"  {_GR}> Base prompt:{_R} {_B}enabled{_R}")
            print()
            return True
        print(f"  {_YL}! {_R}Invalid - enter y or n, or press Enter for no.")


def select_api_temperature() -> Optional[float]:
    """Ask for an optional API temperature; Enter means provider/model default."""
    mw = 46
    print(f"  {_YL}+{'=' * mw}+{_R}")
    print(f"  {_YL}|{_R}{_B}{_WH}{'  API Temperature'.center(mw)}{_R}{_YL}|{_R}")
    print(f"  {_YL}+{'=' * mw}+{_R}")
    note = "  Enter keeps the model/provider default.  "
    print(f"  {_YL}|{_R}{_DIM}{_WH}{note.ljust(mw)}{_R}{_YL}|{_R}")
    print(f"  {_YL}+{'=' * mw}+{_R}")
    print()

    while True:
        raw = input(f"  {_CY}> {_R}Temperature (0-1), or Enter for default: ").strip()
        if raw == "":
            print(f"  {_GR}> API temperature:{_R} {_B}model default{_R}")
            print()
            return None
        try:
            temperature = float(raw)
        except ValueError:
            print(f"  {_YL}! {_R}Invalid — enter a number from 0 to 1, or press Enter.")
            continue
        if 0 <= temperature <= 1:
            print(f"  {_GR}> API temperature:{_R} {_B}{temperature:g}{_R}")
            print()
            return temperature
        print(f"  {_YL}! {_R}Invalid — enter a number from 0 to 1, or press Enter.")


# ── Runtime prompts ───────────────────────────────────────────────────────────

def wait_for_user_login(model: str) -> None:
    mw = 46
    print()
    print(f"  {_YL}╔{'═' * mw}╗{_R}")
    print(f"  {_YL}║{_R}{_B}{_YL}{'  Action Required'.center(mw)}{_R}{_YL}║{_R}")
    print(f"  {_YL}╠{'═' * mw}╣{_R}")
    line1 = f"  Log in to {model} in the browser window."
    line2 = f"  Then return here and press Enter."
    print(f"  {_YL}║{_R}  {_WH}Log in to {_B}{model}{_R}{_WH} in the browser window.{_R}{' ' * (mw - len(line1))}{_YL}║{_R}")
    print(f"  {_YL}║{_R}  {_WH}Then return here and press Enter.{_R}{' ' * (mw - len(line2))}{_YL}║{_R}")
    print(f"  {_YL}╚{'═' * mw}╝{_R}")
    input(f"\n  {_CY}> {_R}Press Enter once logged in and {_B}{model}{_R} is ready... ")


def print_run_complete(save_path: str) -> None:
    print()
    print(f"  {_GR}{'─' * 50}{_R}")
    print(f"  {_B}{_GR}  Run complete.{_R}")
    print(f"  {_GR}  Results saved to:{_R}")
    print(f"  {_WH}  {save_path}{_R}")
    print(f"  {_GR}{'─' * 50}{_R}")
    input(f"\n  {_CY}> {_R}Press Enter to close the browser and exit. ")


# ── Progress bar ──────────────────────────────────────────────────────────────

class ProgressBar:
    """
    Colorful progress bar reprinted after every completed prompt.

    Tracks two counters separately so resumed runs don't skew the ETA:
      completed  — total done (processed + skipped), drives the visual bar.
      _processed — only entries actually sent to the backend, drives timing.

    Usage:
        bar = ProgressBar(total=300)
        bar.skip()      # already-done entry on resume — advances bar, no redraw
        bar.update()    # freshly processed entry — advances bar and redraws
    """

    _FULL  = "█"
    _EMPTY = "░"

    def __init__(self, total: int) -> None:
        self.total      = max(total, 1)
        self.completed  = 0
        self.failures   = 0
        self._processed = 0          # entries actually sent to the backend
        self._start     = time.monotonic()

    # ── public ────────────────────────────────────────────────────────────

    def skip(self) -> None:
        """Advance the display counter for an already-done (resumed) entry."""
        self.completed += 1

    def update(self) -> None:
        """Advance both counters for a freshly processed entry and redraw."""
        self.completed  += 1
        self._processed += 1
        self._render()

    def fail(self) -> None:
        """Mark a prompt as failed — advances counters, increments failure count, redraws."""
        self.completed  += 1
        self._processed += 1
        self.failures   += 1
        self._render()

    # ── internals ─────────────────────────────────────────────────────────

    @staticmethod
    def _fmt(secs: float) -> str:
        s = int(secs)
        if s < 60:
            return f"{s}s"
        m, s = divmod(s, 60)
        if m < 60:
            return f"{m}m {s:02d}s"
        h, m = divmod(m, 60)
        return f"{h}h {m:02d}m"

    def _render(self) -> None:
        elapsed   = time.monotonic() - self._start
        completed = self.completed
        total     = self.total
        pct       = completed / total

        # ETA uses only actually-processed entries to avoid skew from fast skips
        if self._processed > 0:
            avg = elapsed / self._processed
            eta = avg * (total - completed)
        else:
            avg = eta = 0.0

        # ── dimensions ────────────────────────────────────────────────────
        term_w = shutil.get_terminal_size((80, 24)).columns
        box_w  = min(term_w - 6, 72)   # visible chars inside ║ … ║

        # ── bar line ──────────────────────────────────────────────────────
        id_w      = len(str(total))
        count_vis = f" {completed:{id_w}d} / {total}  {pct * 100:5.1f}% "
        bar_w     = max(box_w - len(count_vis) - 2, 10)   # 2 for [ ]
        filled    = round(bar_w * pct)
        empty     = bar_w - filled

        bar_col  = f"{_GR}{self._FULL * filled}{_R}{_DIM}{self._EMPTY * empty}{_R}"
        cnt_col  = f"{_B}{_WH}{count_vis}{_R}"
        bar_line = f"[{bar_col}]{cnt_col}"
        bar_pad  = max(0, box_w - (2 + bar_w + len(count_vis)))

        # ── time line ─────────────────────────────────────────────────────
        sep_vis = "   │   "
        sep_col = f"   {_DIM}│{_R}   "

        pv, pc = [], []   # parallel plain / coloured part lists

        pv.append(f"elapsed: {self._fmt(elapsed)}")
        pc.append(f"{_DIM}elapsed:{_R} {_B}{_WH}{self._fmt(elapsed)}{_R}")

        if self._processed > 0:
            pv.append(f"avg: {avg:.1f}s/prompt")
            pc.append(f"{_DIM}avg:{_R} {_B}{_WH}{avg:.1f}s{_R}{_DIM}/prompt{_R}")

            if completed < total:
                pv.append(f"ETA: {self._fmt(eta)}")
                pc.append(f"{_DIM}ETA:{_R} {_B}{_YL}{self._fmt(eta)}{_R}")
            else:
                pv.append("Done!")
                pc.append(f"{_B}{_GR}Done!{_R}")

        if self.failures > 0:
            pv.append(f"failed: {self.failures}")
            pc.append(f"{_DIM}failed:{_R} {_B}\033[91m{self.failures}{_R}")

        time_vis = sep_vis.join(pv)
        time_col = sep_col.join(pc)
        time_pad = max(0, box_w - len(time_vis))

        # ── draw ──────────────────────────────────────────────────────────
        full_w   = box_w + 2   # +2 for the single space padding each side
        top      = f"  {_CY}╔{'═' * full_w}╗{_R}"
        mid      = f"  {_CY}╠{'═' * full_w}╣{_R}"
        bot      = f"  {_CY}╚{'═' * full_w}╝{_R}"
        bar_row  = f"  {_CY}║{_R} {bar_line}{' ' * bar_pad} {_CY}║{_R}"
        time_row = f"  {_CY}║{_R} {time_col}{' ' * time_pad} {_CY}║{_R}"

        print()
        print(top)
        print(bar_row)
        print(mid)
        print(time_row)
        print(bot)
        print()
