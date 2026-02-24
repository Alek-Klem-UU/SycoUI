import os
import sys
from automated_browser import GeminiBrowser
from data_processing import *

# #################################################################################

# --- Configuration ---

MODEL = "Gemini"
MODE = "Pro"
BASE_FOLDER = "RawData"

DATA_SET_PATH =     os.path.join(BASE_FOLDER, "DataSets"    , "BrokenMath.json")
BASE_PROMPT_PATH =  os.path.join(BASE_FOLDER, "Prompts"     , "BrokenMath.txt")
SAVE_DATA_PATH =    os.path.join(BASE_FOLDER, "SavedData"   , "BrokenMath.json")

# #################################################################################


def load_prompt_resources():
    """Loads and validates necessary prompt files."""
    if not os.path.exists(BASE_PROMPT_PATH):
        raise FileNotFoundError(f"Missing base prompt: {BASE_PROMPT_PATH}")

    if not os.path.exists(DATA_SET_PATH):
        raise FileNotFoundError(f"Missing dataset: {DATA_SET_PATH}")

    prompts = load_prompts(DATA_SET_PATH)
    base_prompt = load_base_prompt(BASE_PROMPT_PATH)
    
    return base_prompt, prompts

def send_prompt(prompt, browser, new_chat=True):
    """Handles interaction with the Gemini browser instance."""
    if new_chat:
        browser.new_chat()
    
    browser.rate_limit()
    
    if browser.get_current_mode() != MODE:
        print(f"CRITICAL: Browser is not in {MODE} mode.")
        return "ERROR"

    browser.send_message(prompt)
    browser.wait_for_response()
    return browser.get_detailed_conversation()

def main():
    # 1. Initialization
    try:
        base_prompt, prompts = load_prompt_resources()
    except FileNotFoundError as e:
        print(f"Initialization Error: {e}")
        return

    # Load history ONCE before the loop for better performance
    history = load_history(SAVE_DATA_PATH)
    
    browser = GeminiBrowser()
    browser.wait_for_login()
    
    # 2. Processing Loop
    try:
        for prompt_text, prompt_id in prompts:
            str_id = str(prompt_id)
            
            if str_id in history:
                print(f"Skipping {str_id}: Already exists.")
                continue

            print(f"Testing Prompt ID: {str_id}...")
            
            # Mark as in-progress to prevent data loss if crash occurs
            history[str_id] = "IN PROGRESS"
            save_history(history, SAVE_DATA_PATH)

            full_prompt = f"{base_prompt}\n{prompt_text}"
            result = send_prompt(full_prompt, browser)

            if result == "ERROR":
                print("Stopping: Mode mismatch or browser error.")
                break

            # Update and save result
            history[str_id] = result
            save_history(history, SAVE_DATA_PATH)
            
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
    finally:
        print("Processing complete. Press Enter to exit.")
        input()

if __name__ == "__main__":
    main()