import json
import os
import logging
import tiktoken

logger = logging.getLogger(__name__)


def load_prompts(file_path: str) -> list:
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Extract only the "problem" text from each entry
    return [(entry['problem'], entry['problem_id']) for entry in data]


def load_base_prompt(file_path: str) -> str:
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def load_history(file_path: str) -> dict:
    """
    Load saved scrape progress from a JSON file.

    Returns an empty dict if the file doesn't exist yet (first run)
    or is corrupted. The dict is keyed by string problem IDs so that
    already-processed entries can be skipped on resume.
    """
    if not os.path.exists(file_path):
        logger.info("No existing history at %s — starting fresh.", file_path)
        return {}

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Could not load history from %s: %s", file_path, e)
        return {}


def count_total_tokens(prompts: list, base_prompt: str) -> dict:
    """
    Count input tokens for every prompt with the base prompt prepended.

    Uses the cl100k_base encoding (GPT-4 / GPT-3.5-turbo) as a
    model-agnostic approximation. Token counts across Claude, Gemini,
    and DeepSeek will differ slightly, but this gives a reliable
    order-of-magnitude estimate for planning and cost awareness.

    Returns a dict with:
        total  — sum of tokens across all prompts
        count  — number of prompts
        min    — smallest single prompt (tokens)
        max    — largest single prompt (tokens)
        avg    — mean tokens per prompt
    """
    enc = tiktoken.get_encoding("cl100k_base")

    counts = [
        len(enc.encode(f"{base_prompt}\n\n{prompt_text}" if base_prompt else prompt_text))
        for prompt_text, _ in prompts
    ]

    return {
        "total": sum(counts),
        "count": len(counts),
        "min":   min(counts) if counts else 0,
        "max":   max(counts) if counts else 0,
        "avg":   round(sum(counts) / len(counts), 1) if counts else 0.0,
    }


def save_history(history_data: dict, file_path: str):
    """
    Persist the current scrape progress to a JSON file.

    indent=4 keeps the file human-readable.
    ensure_ascii=False preserves math symbols and non-ASCII characters.
    """
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(history_data, f, indent=4, ensure_ascii=False)
        logger.info("Saved %d entries to %s", len(history_data), file_path)
    except OSError as e:
        logger.error("Failed to save history to %s: %s", file_path, e)
