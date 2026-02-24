import json
import os
from operator import concat

def load_prompts(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Extract only the "problem" text from each entry
    prompts = [(entry['problem'], entry['problem_id']) for entry in data]
    return prompts


def load_base_prompt(file_path):
    file = open(file_path, 'r')
    lines = file.readlines()

    text = ""

    for line in lines:
        text += line

    text += "\n"


    return text

def load_history(file_path):
    """
    Loads conversation history from a JSON file. 
    Returns an empty list if the file doesn't exist or is corrupted.
    """
    if not os.path.exists(file_path):
        print(f"File {file_path} not found. Starting with empty history.")
        return []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, Exception) as e:
        print(f"Error loading {file_path}: {e}")
        return []

def save_history(history_data, file_path):
    """
    Saves the list of conversation turns to a JSON file with clean formatting.
    """
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            # indent=4 makes the file human-readable
            # ensure_ascii=False preserves math symbols and non-English characters
            json.dump(history_data, f, indent=4, ensure_ascii=False)
        print(f"Successfully saved {len(history_data)} turns to {file_path}")
    except Exception as e:
        print(f"Error saving to {file_path}: {e}")