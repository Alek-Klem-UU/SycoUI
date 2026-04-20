import os
import datetime
import logging
from dataclasses import dataclass
from browsers import (
    BaseBrowser,
    ChatGPTBrowser,
    ClaudeBrowser,
    GeminiBrowser,
)
from data_processing import DATASET_PATH, load_prompts, load_history, save_history, count_total_tokens, count_csv_rows
from cli import print_banner, select_model, select_dataset, select_subset, wait_for_user_login, print_run_complete

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
RAW_DATA_DIR = os.path.join(SCRIPT_DIR, "RawData")

@dataclass
class RunConfig:
    model: str
    dataset_name: str
    save_data_path: str

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Browser Factory
# -----------------------------------------------------------------------------

_BROWSER_MAP = {
    "Gemini":  GeminiBrowser,
    "Claude":  ClaudeBrowser,
    "ChatGPT": ChatGPTBrowser,
}

_MODE_MAP = {
    "Gemini":  "Fast",
    "Claude":  "Sonnet 4.6",
    "ChatGPT": "ChatGPT",
}

def _setup_file_logging(config: RunConfig):
    """
    Add a timestamped file handler to the root logger.

    A separate log file is created for each run so that long overnight
    scrapes have a persistent record for debugging after the fact.
    The filename includes the model name so runs are easy to tell apart.
    """
    log_dir = os.path.join(SCRIPT_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    log_path = os.path.join(log_dir, f"{config.model}_{config.dataset_name}_{timestamp}.log")
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logging.getLogger().addHandler(handler)
    logger.info("Logging to %s", log_path)


def create_browser(config: RunConfig, headless: bool = False) -> BaseBrowser:
    browser_cls = _BROWSER_MAP.get(config.model)
    if browser_cls is None:
        raise ValueError(
            f"Unknown model '{config.model}'. Valid options: {list(_BROWSER_MAP.keys())}"
        )
    logger.info("Using browser: %s (mode: %s)", config.model, _MODE_MAP[config.model])
    return browser_cls(headless=headless)

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def validate_resources(config: RunConfig):
    if not os.path.exists(DATASET_PATH):
        raise FileNotFoundError(f"Critical resource missing: {DATASET_PATH}")
    os.makedirs(os.path.dirname(config.save_data_path), exist_ok=True)


def process_prompt(
    browser: BaseBrowser,
    prompt_text: str,
    config: RunConfig,
) -> list | None:
    """Send a single prompt and return the full conversation history."""
    browser.navigate_home()
    browser.rate_limit()

    current_mode = browser.get_active_model()
    if current_mode != _MODE_MAP[config.model]:
        logger.error("Mode mismatch: expected '%s', got '%s'.", _MODE_MAP[config.model], current_mode)
        return None

    browser.send_message(prompt_text)
    browser.wait_for_response()

    return browser.get_history()


def run(
    browser: BaseBrowser,
    prompts: list,
    history: dict,
    config: RunConfig,
):
    for prompt_text, prompt_id in prompts:
        logger.info("\n\n")
        str_id = str(prompt_id)

        if str_id in history and history[str_id] != "IN PROGRESS":
            logger.info("Skipping ID %s: already processed.", str_id)
            continue

        logger.info("Processing ID %s…", str_id)

        history[str_id] = "IN PROGRESS"
        save_history(history, config.save_data_path)

        result = process_prompt(browser, prompt_text, config)

        if result is None:
            logger.warning("Aborting run due to mode mismatch.")
            return

        history[str_id] = result
        save_history(history, config.save_data_path)
        logger.info("Saved ID %s.", str_id)

# -----------------------------------------------------------------------------
# Entry Point
# -----------------------------------------------------------------------------

def main():
    print_banner()
    model = select_model(_BROWSER_MAP, _MODE_MAP)
    _, dataset_name = select_dataset(os.path.join(RAW_DATA_DIR, "DataSets"))
    save_data_path = os.path.join(RAW_DATA_DIR, "SavedData", model, f"{dataset_name}.json")

    config = RunConfig(
        model=model,
        dataset_name=dataset_name,
        save_data_path=save_data_path,
    )

    _setup_file_logging(config)
    try:
        validate_resources(config)
        history = load_history(config.save_data_path)

        # For CSVs, count rows cheaply first so the subset prompt can show the
        # total before any parsing happens, then load only the requested rows.
        total   = count_csv_rows()
        n       = select_subset(total)
        prompts = load_prompts(max_rows=n)
    except Exception as e:
        logger.error("Initialization failed: %s", e)
        return

    tok = count_total_tokens(prompts)
    logger.info(
        "Dataset: %d prompts | tokens — total: %s  avg: %s  min: %s  max: %s",
        tok["count"],
        f"{tok['total']:,}",
        f"{tok['avg']:,}",
        f"{tok['min']:,}",
        f"{tok['max']:,}",
    )

    with create_browser(config, headless=False) as browser:
        wait_for_user_login(config.model)
        try:
            run(browser, prompts, history, config)
        except KeyboardInterrupt:
            logger.info("Interrupted by user — progress saved.")
        except Exception:
            logger.exception("Unexpected error during run.")
        finally:
            print_run_complete(config.save_data_path)


if __name__ == "__main__":
    main()
