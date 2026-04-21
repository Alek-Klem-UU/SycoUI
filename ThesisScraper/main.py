import os
import datetime
import logging
from dataclasses import dataclass
from typing import Union

from apis import BaseAPI, ChatGPTAPI, ClaudeAPI, GeminiAPI
from browsers import (
    BaseBrowser,
    ChatGPTBrowser,
    ClaudeBrowser,
    GeminiBrowser,
)
from data_processing import load_prompts, load_history, save_history, count_total_tokens, count_csv_rows
from cli import (
    print_banner,
    select_mode,
    select_model,
    select_dataset,
    select_subset,
    wait_for_user_login,
    print_run_complete,
    prompt_api_key,
)

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
RAW_DATA_DIR = os.path.join(SCRIPT_DIR, "RawData")

Backend = Union[BaseBrowser, BaseAPI]


@dataclass
class RunConfig:
    model: str
    mode: str            # "Browser" or "API"
    dataset_name: str
    dataset_path: str
    save_data_path: str

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Backend registries
# -----------------------------------------------------------------------------

_BROWSER_MAP = {
    "Gemini":  GeminiBrowser,
    "Claude":  ClaudeBrowser,
    "ChatGPT": ChatGPTBrowser,
}

_API_MAP = {
    "Gemini":  GeminiAPI,
    "Claude":  ClaudeAPI,
    "ChatGPT": ChatGPTAPI,
}

_MODE_MAP = {
    "Gemini":  "Fast",
    "Claude":  "Sonnet 4.6",
    "ChatGPT": "ChatGPT",
}

# Provider-specific environment variables checked before prompting for a key.
# Names follow each provider's documented convention.
_API_KEY_ENV = {
    "Claude":  "ANTHROPIC_API_KEY",
    "ChatGPT": "OPENAI_API_KEY",
    "Gemini":  "GEMINI_API_KEY",
}

def _setup_file_logging(config: RunConfig):
    """
    Add a timestamped file handler to the root logger.

    A separate log file is created for each run so that long overnight
    scrapes have a persistent record for debugging after the fact.
    The filename includes the model and mode so runs are easy to tell apart.
    """
    log_dir = os.path.join(SCRIPT_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    log_path = os.path.join(
        log_dir,
        f"{config.model}_{config.mode}_{config.dataset_name}_{timestamp}.log",
    )
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
    if headless:
        # The run flow calls wait_for_user_login() which blocks on stdin until
        # the user signals login is complete. With no visible browser window
        # there is nothing to log into, so a headless run will hang forever.
        raise ValueError(
            "Headless mode is not supported: manual login is required before "
            "scraping can begin. Pass headless=False (the default)."
        )
    logger.info("Using browser: %s (mode: %s)", config.model, _MODE_MAP[config.model])
    return browser_cls(headless=headless)


def create_api_client(config: RunConfig) -> BaseAPI:
    api_cls = _API_MAP.get(config.model)
    if api_cls is None:
        raise ValueError(
            f"Unknown model '{config.model}'. Valid options: {list(_API_MAP.keys())}"
        )
    api_key = prompt_api_key(config.model, _API_KEY_ENV[config.model])
    logger.info("Using API: %s (mode: %s)", config.model, _MODE_MAP[config.model])
    return api_cls(api_key=api_key)

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def validate_resources(config: RunConfig):
    if not os.path.exists(config.dataset_path):
        raise FileNotFoundError(f"Critical resource missing: {config.dataset_path}")
    os.makedirs(os.path.dirname(config.save_data_path), exist_ok=True)


def process_prompt(
    backend: Backend,
    prompt_text: str,
    config: RunConfig,
) -> list | None:
    """Send a single prompt and return the full conversation history."""
    backend.navigate_home()
    backend.rate_limit()

    current_mode = backend.get_active_model()
    if current_mode != _MODE_MAP[config.model]:
        logger.error("Mode mismatch: expected '%s', got '%s'.", _MODE_MAP[config.model], current_mode)
        return None

    backend.send_message(prompt_text)
    backend.wait_for_response()

    return backend.get_history()


def run(
    backend: Backend,
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

        result = process_prompt(backend, prompt_text, config)

        if result is None:
            # The "IN PROGRESS" marker we just wrote stays in the JSON, but
            # the resume check above (`!= "IN PROGRESS"`) means it will be
            # retried on the next run rather than skipped. No manual cleanup
            # required.
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
    mode  = select_mode()
    backend_map = _BROWSER_MAP if mode == "Browser" else _API_MAP
    model = select_model(backend_map, _MODE_MAP)
    dataset_path, dataset_name = select_dataset(os.path.join(RAW_DATA_DIR, "DataSets"))

    # Mode is part of the save path so Browser and API runs of the same model
    # never overwrite each other — the comparison between them IS the experiment.
    save_data_path = os.path.join(
        RAW_DATA_DIR, "SavedData", model, mode, f"{dataset_name}.json"
    )

    config = RunConfig(
        model=model,
        mode=mode,
        dataset_name=dataset_name,
        dataset_path=dataset_path,
        save_data_path=save_data_path,
    )

    _setup_file_logging(config)
    try:
        validate_resources(config)
        history = load_history(config.save_data_path)

        # For CSVs, count rows cheaply first so the subset prompt can show the
        # total before any parsing happens, then load only the requested rows.
        total   = count_csv_rows(config.dataset_path)
        n       = select_subset(total)
        prompts = load_prompts(config.dataset_path, max_rows=n)

        # Construct the backend AFTER loading prompts — this way a typo in the
        # subset selection doesn't waste an API-key prompt or browser launch.
        if mode == "Browser":
            backend_ctx = create_browser(config, headless=False)
        else:
            backend_ctx = create_api_client(config)
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

    with backend_ctx as backend:
        if mode == "Browser":
            wait_for_user_login(config.model)
        try:
            run(backend, prompts, history, config)
        except KeyboardInterrupt:
            logger.info("Interrupted by user — progress saved.")
        except Exception:
            logger.exception("Unexpected error during run.")
        finally:
            print_run_complete(config.save_data_path)


if __name__ == "__main__":
    main()
