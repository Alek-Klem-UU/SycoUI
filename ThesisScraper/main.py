import os
import datetime
import logging
from gemini_browser import GeminiBrowser
from claude_browser import ClaudeBrowser
from deepseek_browser import DeepSeekBrowser
from ChatGPT_browser import ChatGPTBrowser
from browser_base import BaseBrowser
from data_processing import load_prompts, load_base_prompt, load_history, save_history, count_total_tokens

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

# MODEL and SAVE_DATA_PATH are set at runtime by select_model() in main().
MODEL          = ""
SAVE_DATA_PATH = ""

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
RAW_DATA_DIR = os.path.join(SCRIPT_DIR, "RawData")

DATA_SET_PATH    = os.path.join(RAW_DATA_DIR, "DataSets", "Elephant.json")
BASE_PROMPT_PATH = os.path.join(RAW_DATA_DIR, "Prompts",  "Elephant.txt")

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Browser Factory
# -----------------------------------------------------------------------------

_BROWSER_MAP = {
    "Gemini":   GeminiBrowser,
    "Claude":   ClaudeBrowser,
    "DeepSeek": DeepSeekBrowser,
    "ChatGPT":  ChatGPTBrowser,
}

_MODE_MAP = {
    "Gemini":   "Fast",
    "Claude":   "Sonnet 4.6",
    "DeepSeek": "Default",
    "ChatGPT":  "ChatGPT",
}

# -----------------------------------------------------------------------------
# Startup selection
# -----------------------------------------------------------------------------

def select_model() -> str:
    """
    Show a numbered menu and return the model name the user picks.

    Keeps looping until a valid number is entered, so a mis-press
    doesn't crash the script.
    """
    options = list(_BROWSER_MAP.keys())
    print()
    print("=" * 50)
    print("  SycoUI — Select a model")
    print("=" * 50)
    for i, name in enumerate(options, 1):
        print(f"  {i}. {name}  (mode: {_MODE_MAP[name]})")
    print()

    while True:
        choice = input(f"Enter number (1-{len(options)}): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            selected = options[int(choice) - 1]
            print(f"\nSelected: {selected}")
            return selected
        print(f"  Invalid — please enter a number between 1 and {len(options)}.")


def _setup_file_logging():
    """
    Add a timestamped file handler to the root logger.

    A separate log file is created for each run so that long overnight
    scrapes have a persistent record for debugging after the fact.
    The filename includes the model name so runs are easy to tell apart.
    """
    log_dir = os.path.join(SCRIPT_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    log_path = os.path.join(log_dir, f"{MODEL}_{timestamp}.log")
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logging.getLogger().addHandler(handler)
    logger.info("Logging to %s", log_path)

# -----------------------------------------------------------------------------
# Browser Factory
# -----------------------------------------------------------------------------

def create_browser(headless: bool = False) -> BaseBrowser:
    browser_cls = _BROWSER_MAP.get(MODEL)
    if browser_cls is None:
        raise ValueError(
            f"Unknown MODEL '{MODEL}'. Valid options: {list(_BROWSER_MAP.keys())}"
        )
    logger.info("Using browser: %s (mode: %s)", MODEL, _MODE_MAP[MODEL])
    return browser_cls(headless=headless)

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def validate_resources():
    for path in (DATA_SET_PATH, BASE_PROMPT_PATH):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Critical resource missing: {path}")
    os.makedirs(os.path.dirname(SAVE_DATA_PATH), exist_ok=True)


def wait_for_user_login():
    print()
    print("=" * 50)
    print(f"ACTION REQUIRED: Log in to {MODEL}, then press ENTER.")
    print("=" * 50)
    input(f"\nPress Enter once logged in and {MODEL} is ready...")


def _resolve_turns(base_text: str, prompt_text: str | list[str]) -> list[str]:
    """
    Build the ordered list of messages to send for one prompt entry.

    - Single-turn: prepend the base prompt to the first (only) message.
    - Multi-turn:  prepend the base prompt to the first message; subsequent
                   turns are sent as-is, as natural follow-ups.
    """
    turns = [prompt_text] if isinstance(prompt_text, str) else list(prompt_text)
    if not turns:
        raise ValueError("prompt_text must be a non-empty string or list of strings.")
    # Base prompt is always attached to the opening message only.
    turns[0] = f"{base_text}\n\n{turns[0]}" if base_text else turns[0]
    return turns


def process_prompt(
    browser: BaseBrowser,
    base_text: str,
    prompt_text: str | list[str],
) -> list | None:
    """
    Run one prompt (single- or multi-turn) and return the full conversation history.

    In multi-turn mode every message in prompt_text is sent sequentially inside
    the same chat window, with a rate-limit pause between turns.
    """
    browser.navigate_home()
    browser.rate_limit()

    current_mode = browser.get_active_model()
    if current_mode != _MODE_MAP[MODEL]:
        logger.error("Mode mismatch: expected '%s', got '%s'.", _MODE_MAP[MODEL], current_mode)
        return None

    turns = _resolve_turns(base_text, prompt_text)

    for i, message in enumerate(turns):
        if i > 0:
            # Inter-turn pause — only after the first message has been sent.
            browser.rate_limit()
        logger.info("Sending turn %d/%d.", i + 1, len(turns))
        browser.send_message(message)
        browser.wait_for_response()

    return browser.get_history()


def run(
    browser: BaseBrowser,
    prompts: list,
    base_prompt: str,
    history: dict,
):
    for prompt_text, prompt_id in prompts:
        logger.info("\n\n")
        str_id = str(prompt_id)

        if str_id in history and history[str_id] != "IN PROGRESS":
            logger.info("Skipping ID %s: already processed.", str_id)
            continue

        logger.info("Processing ID %s…", str_id)

        history[str_id] = "IN PROGRESS"
        save_history(history, SAVE_DATA_PATH)

        result = process_prompt(browser, base_prompt, prompt_text)

        if result is None:
            logger.warning("Aborting run due to mode mismatch.")
            return

        history[str_id] = result
        save_history(history, SAVE_DATA_PATH)
        logger.info("Saved ID %s.", str_id)

# -----------------------------------------------------------------------------
# Entry Point
# -----------------------------------------------------------------------------

def main():
    global MODEL, SAVE_DATA_PATH
    MODEL = select_model()
    SAVE_DATA_PATH = os.path.join(RAW_DATA_DIR, "SavedData", MODEL, "BrokenMath.json")

    _setup_file_logging()
    try:
        validate_resources()
        base_prompt = load_base_prompt(BASE_PROMPT_PATH)
        prompts     = load_prompts(DATA_SET_PATH)
        history     = load_history(SAVE_DATA_PATH)
    except Exception as e:
        logger.error("Initialization failed: %s", e)
        return

    tok = count_total_tokens(prompts, base_prompt)
    logger.info(
        "Dataset: %d prompts | tokens — total: %s  avg: %s  min: %s  max: %s",
        tok["count"],
        f"{tok['total']:,}",
        f"{tok['avg']:,}",
        f"{tok['min']:,}",
        f"{tok['max']:,}",
    )

    with create_browser(headless=False) as browser:
        wait_for_user_login()
        try:
            run(browser, prompts, base_prompt, history)
        except KeyboardInterrupt:
            logger.info("Interrupted by user — progress saved.")
        except Exception:
            logger.exception("Unexpected error during run.")
        finally:
            print()
            print("-" * 30)
            print(f"Run complete. Results saved to: {SAVE_DATA_PATH}")
            input("Press Enter to close the browser and exit.")


if __name__ == "__main__":
    main()
