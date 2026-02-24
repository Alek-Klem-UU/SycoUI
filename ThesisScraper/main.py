import os
import logging
from gemini_browser import GeminiBrowser
from claude_browser import ClaudeBrowser
from deepseek_browser import DeepSeekBrowser
from ChatGPT_browser import ChatGPTBrowser
from data_processing import load_prompts, load_base_prompt, load_history, save_history

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

MODEL = "ChatGPT"   # "Gemini" or "Claude"


SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
RAW_DATA_DIR = os.path.join(SCRIPT_DIR, "RawData")

DATA_SET_PATH    = os.path.join(RAW_DATA_DIR, "DataSets", "BrokenMath.json")
BASE_PROMPT_PATH = os.path.join(RAW_DATA_DIR, "Prompts",  "BrokenMath.txt")
SAVE_DATA_PATH   = os.path.join(RAW_DATA_DIR, "SavedData", MODEL, "BrokenMath.json")

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Browser Factory
# -----------------------------------------------------------------------------

_BROWSER_MAP = {
    "Gemini": GeminiBrowser,
    "Claude": ClaudeBrowser,
    "DeepSeek": DeepSeekBrowser,
    "ChatGPT": ChatGPTBrowser,
}

_MODE_MAP = {
    "Gemini": "Fast",
    "Claude": "Sonnet 4.6",
    "DeepSeek": "Default",
    "ChatGPT" : "ChatGPT"
}


def create_browser(headless: bool = False) -> GeminiBrowser | ClaudeBrowser:
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
    browser: GeminiBrowser | ClaudeBrowser,
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
    browser: GeminiBrowser | ClaudeBrowser,
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
    try:
        validate_resources()
        base_prompt = load_base_prompt(BASE_PROMPT_PATH)
        prompts     = load_prompts(DATA_SET_PATH)
        history     = load_history(SAVE_DATA_PATH)
    except Exception as e:
        logger.error("Initialization failed: %s", e)
        return

    with create_browser(headless=False) as browser:
        wait_for_user_login()
        try:
            run(browser, prompts, "", history)
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