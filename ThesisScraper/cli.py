"""
cli.py — Terminal UI for SycoUI.

All interactive prompts and visual rendering live here so that
main.py stays focused on orchestration logic.
"""

import getpass
import os
import sys

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
