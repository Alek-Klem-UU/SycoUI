# ThesisScraper

A browser-automation tool that sends adversarial mathematical problems to four AI chatbots and records their full responses for comparative analysis. Built for thesis research at Utrecht University.

---

## What it does

For each problem in the **BrokenMath** dataset, the scraper:

1. Opens a persistent browser session for the selected AI platform
2. Waits for the user to log in manually (sessions are saved, so this is only needed once)
3. Sends the base prompt followed by each problem
4. Waits for the model to finish responding
5. Scrapes the full conversation and saves it to JSON

Results are saved incrementally, so the run can be interrupted and resumed at any time.

---

## Supported platforms

| Key | Platform | Default mode |
|-----|----------|-------------|
| `ChatGPT` | chatgpt.com | ChatGPT |
| `Claude` | claude.ai | Sonnet 4.6 |
| `Gemini` | gemini.google.com | Fast |
| `DeepSeek` | chat.deepseek.com | Default |

---

## Setup

**Requirements:** Python 3.12+

```bash
cd ThesisScraper
pip install -r requirements.txt
```

Install the Chromium browser used by Playwright/Patchright:

```bash
patchright install chromium
```

---

## Configuration

Open `ThesisScraper/main.py` and set the `MODEL` variable at the top:

```python
MODEL = "ChatGPT"   # "Claude" | "Gemini" | "DeepSeek" | "ChatGPT"
```

---

## Usage

```bash
cd ThesisScraper
python main.py
```

The browser window will open and pause for login. Once you are logged in and the chat interface is ready, press **Enter** in the terminal. The scraper will then run through the full dataset automatically.

Progress is saved after every problem. To resume an interrupted run, just run `main.py` again with the same `MODEL` — already-completed entries are skipped.

---

## Project structure

```
ThesisScraper/
├── main.py                  # Entry point — configuration, orchestration
├── browser_base.py          # Shared retry logic and error types
├── claude_browser.py        # Automation for claude.ai
├── ChatGPT_browser.py       # Automation for chatgpt.com
├── gemini_browser.py        # Automation for gemini.google.com
├── deepseek_browser.py      # Automation for chat.deepseek.com
├── data_processing.py       # Load prompts, save/load results
├── utils.py                 # HumanTypist — realistic keystroke simulation
├── requirements.txt
└── RawData/
    ├── DataSets/
    │   └── BrokenMath.json  # Input: adversarial math problems
    ├── Prompts/
    │   └── BrokenMath.txt   # Base system prompt prepended to each problem
    └── SavedData/
        ├── ChatGPT/
        ├── Claude/
        ├── Gemini/
        └── DeepSeek/        # Output: one JSON file per model
```

---

## Output format

Each model's results are saved to `RawData/SavedData/<MODEL>/BrokenMath.json` as a JSON object keyed by `problem_id`:

```json
{
  "42": [
    {
      "turn": 1,
      "user": "<the problem text>",
      "model_output": "<the model's response>"
    }
  ]
}
```

---

## Notes

- Browser sessions (login cookies) are stored in `*_ui_session/` folders and are excluded from version control. Each platform only requires one manual login per machine.
- The scraper simulates human typing speed and adds randomised delays between requests to reduce bot-detection risk.
- If the active model does not match the expected mode in `_MODE_MAP`, the run aborts early rather than silently collecting data under the wrong configuration.
