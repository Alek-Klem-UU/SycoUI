import os
import time
import random
from patchright.sync_api import sync_playwright
from utils import HumanTypist
import re 

class GeminiBrowser:
    def __init__(self):
        self.playwright = None
        self.context = None
        self.page = None
        self._setup()

    def _setup(self):
        USER_DATA_DIR = os.path.join(os.getcwd(), "gemini_ui_session")
        
        # Start Patchright synchronously
        self.playwright = sync_playwright().start()
        
        width = 400
        height = 600
        
       
        screen_x = 0
        screen_y = 0

        self.context = self.playwright.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=False,
            # This sets the internal page size
            viewport={'width': width, 'height': height}, 
            args=[
                f"--window-size={width},{height}",
                f"--window-position={screen_x},{screen_y}",
                "--disable-blink-features=AutomationControlled"
            ]
        )

        self.page = self.context.pages[0]
       
    
    def new_chat(self):
       
        self.page.goto("https://gemini.google.com/app")
        self.page.wait_for_selector("div[contenteditable='true']", timeout=30000)
        time.sleep(1)

    def wait_for_login(self):
        print("\n" + "="*50)
        print("ACTION REQUIRED: Log in, then press ENTER in this terminal.")
        print("="*50 + "\n")
        input("Press Enter once logged in...")

    def get_current_mode(self):
        """
        Robustly finds the active mode (Snel, Pro, Thinking) by targeting 
        the data-test-id and filtering for visibility.
        """
        try:
            # 1. Wait for the specific container you provided to exist
            selector = "[data-test-id='logo-pill-label-container']"
            self.page.wait_for_selector(selector, timeout=5000, state="attached")
        
            # 2. Get all instances (Gemini often keeps a hidden one in the DOM)
            pills = self.page.locator(selector).all()
        
            for pill in pills:
                if pill.is_visible():
                    # Extract text and clean it (removes the 'keyboard_arrow_down' icon text)
                    text = pill.inner_text().strip()
                    # If the text contains the icon name 'keyboard_arrow_down', split it
                    clean_text = text.split('\n')[0].replace('keyboard_arrow_down', '').strip()
                    if clean_text:
                        return clean_text
        
            # Fallback: if visible check fails, try the first one that has text
            return pills[0].inner_text().strip().split('\n')[0]
        except Exception as e:
            print(f"Mode detection failed: {e}")
            return "ERROR"

    def send_message(self, text):
        """Finds the input, types humanly, and sends it."""
        chat_input = self.page.get_by_role("textbox", name="Prompt")
        chat_input.click()
        
        if not chat_input.is_visible():
            chat_input = self.page.locator("div[contenteditable='true']").first
        
        # Human_typer integration
        HumanTypist.type_text(chat_input, text)
       
        time.sleep(random.uniform(0.6, 1.5))

        if random.random() > 1:
            chat_input.press("Enter")
        else:
            # Finding the 'Send' button by its aria-label
            self.page.locator("button[aria-label*='Send']").click()


    def wait_for_response(self):
       
        stop_button_selector = "button[aria-label*='Stop']"
    
        started = False
        for _ in range(50): 
            if self.page.locator(stop_button_selector).is_visible():
                started = True
                break
            time.sleep(0.5)

        if started:
            self.page.locator(stop_button_selector).wait_for(state="hidden", timeout=90000000)
            print("\n[✔] Response complete (Stop button vanished).")
        else:
            self.page.get_by_role("button", name="Use microphone").wait_for(state="visible", timeout=1000000)
            print("\n[✔] Response complete (Microphone returned).")

    def get_detailed_conversation(self):
        """
        Iterates through the entire chat, expands every 'Thinking' block, 
        and extracts the CoT text alongside the final response.
        """
        history = []
        
        # Wait for responses to be ready
        self.page.wait_for_selector("model-response", state="visible", timeout=15000)
        
        turns = self.page.locator("model-response").all()
        queries = self.page.locator("user-query").all()

        for i, resp_node in enumerate(turns):
            turn_data = {
                "turn": i + 1,
                "user": queries[i].inner_text().strip() if i < len(queries) else "N/A",
                "thought": None,
                "model_output": ""
            }

            # --- 1. HANDLE EXPANDING ---
            expander = resp_node.locator("div.thoughts-header-button-content:has-text('Show thinking')").first
            if expander.count() > 0:
                try:
                    expander.click(force=True)
                    # Instead of waiting for it to hide, just give the DOM 1 second to render the expanded text
                    self.page.wait_for_timeout(1000) 
                except Exception as e:
                    print(f"Turn {i+1}: Could not click the 'Show thinking' div. Error: {e}")

            # --- 2. EXTRACT THOUGHT TEXT ---
            # We look specifically for the expanded content container
            thought_container = resp_node.locator("[class*='thoughts-content'], .actual-expanded-thought-class").first
            
            if thought_container.count() > 0:
                raw_thought = thought_container.inner_text().strip()
                
                # Sometimes the button text itself ("Show thinking" or "Hide thinking") 
                # gets caught in the extraction. Let's clean it up.
                if raw_thought.startswith("Show thinking"):
                    raw_thought = raw_thought.replace("Show thinking", "", 1).strip()
                elif raw_thought.startswith("Hide thinking"):
                    raw_thought = raw_thought.replace("Hide thinking", "", 1).strip()
                    
                turn_data["thought"] = raw_thought

            # --- 3. EXTRACT FINAL RESPONSE ---
            # Use .last here. Often, the thought block is the first element, and the actual response is the last.
            content_area = resp_node.locator(".message-content, .markdown, response-body").last
            
            if content_area.count() > 0:
                raw_text = content_area.inner_text().strip()
                
                # ROBUST SEPARATION: If the inner_text grabbed EVERYTHING (thought + answer),
                # we do a direct string replace to remove the thought part, leaving only the answer.
                if turn_data["thought"] and turn_data["thought"] in raw_text:
                    raw_text = raw_text.replace(turn_data["thought"], "").strip()
                
                # Final cleanup of any stray button text that bled into the main response
                raw_text = raw_text.replace("Show thinking", "").replace("Hide thinking", "").strip()
                
                turn_data["model_output"] = raw_text

            history.append(turn_data)

        return history


    def rate_limit(self):
        sleep_time = random.randint(2, 7)
        print(f"Rate limit for {sleep_time} seconds")
        time.sleep(sleep_time + random.random())

    def close(self):
        if self.context:
            self.context.close()
        if self.playwright:
            self.playwright.stop()

