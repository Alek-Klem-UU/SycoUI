import csv
from itertools import islice
import json
import os
import logging
import tiktoken

logger = logging.getLogger(__name__)

DATASET_PATH = os.path.join(
    os.path.dirname(__file__), "RawData", "DataSets", "AITA-YTA-1000.csv"
)


def load_prompts(max_rows: int | None = None) -> list:
    """
    Load AITA-YTA-1000.csv and return a list of (prompt_text, prompt_id) tuples.
    prompt_id is taken from the unnamed pandas index column.
    """
    with open(DATASET_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = islice(reader, max_rows) if max_rows is not None else reader
        return [
            (row["prompt"], row.get("", str(i)))
            for i, row in enumerate(rows)
        ]


def count_csv_rows() -> int:
    """Return the number of data rows in the dataset (header excluded)."""
    with open(DATASET_PATH, newline="", encoding="utf-8") as f:
        return max(0, sum(1 for _ in csv.reader(f)) - 1)


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


def count_total_tokens(prompts: list) -> dict:
    """
    Count input tokens for every prompt.

    Uses the cl100k_base encoding as a model-agnostic approximation.

    Returns a dict with:
        total  — sum of tokens across all prompts
        count  — number of prompts
        min    — smallest single prompt (tokens)
        max    — largest single prompt (tokens)
        avg    — mean tokens per prompt
    """
    enc = tiktoken.get_encoding("cl100k_base")

    counts = [
        len(enc.encode(prompt_text))
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
    ensure_ascii=False preserves non-ASCII characters.
    """
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(history_data, f, indent=4, ensure_ascii=False)
        logger.info("Saved %d entries to %s", len(history_data), file_path)
    except OSError as e:
        logger.error("Failed to save history to %s: %s", file_path, e)
