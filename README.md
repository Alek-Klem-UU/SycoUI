<img src="https://github.com/UtrechtUniversity.png" alt="Utrecht University" width="80" align="right"/>

# SycoUI

A browser-automation tool that sends prompts to four AI chatbots and records their full responses for comparative analysis. Built for thesis research at Utrecht University.

---

## What it does

For each prompt in a selected benchmark dataset, the scraper:

1. Opens a persistent browser session for the selected AI platform
2. Waits for the user to log in manually (sessions are saved, so this is only needed once)
3. Optionally prepends a base system prompt to the first message
4. Sends the prompt and waits for the model to finish responding
5. Scrapes the full conversation and saves it to JSON

Results are saved incrementally, so the run can be interrupted and resumed at any time. The tool currently targets the **ELEPHANT** sycophancy benchmark.

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

## Usage

```bash
cd ThesisScraper
python main.py
```

At startup, the terminal UI walks you through three selections:

1. **Model** — choose which AI platform to target
2. **Dataset** — choose which CSV from `RawData/DataSets/` to run
3. **Subset size** — optionally limit to the first N prompts (press Enter to run all)

A token count summary is logged before the browser opens, giving a cost estimate for the run.

The browser window will open and pause for login. Once you are logged in and the chat interface is ready, press **Enter** in the terminal. The scraper will then run through the selected prompts automatically.

Progress is saved after every prompt. To resume an interrupted run, just run `main.py` again with the same model and dataset — already-completed entries are skipped.

---

## Project structure

```
ThesisScraper/
├── main.py                  # Orchestration — browser lifecycle, run loop
├── cli.py                   # Terminal UI — menus, banner, prompts
├── data_processing.py       # Load prompts (CSV/JSON), save/load results
├── requirements.txt
├── browsers/                # Browser automation package
│   ├── browser_base.py      # Shared retry logic and error types
│   ├── claude_browser.py    # Automation for claude.ai
│   ├── ChatGPT_browser.py   # Automation for chatgpt.com
│   ├── gemini_browser.py    # Automation for gemini.google.com
│   ├── deepseek_browser.py  # Automation for chat.deepseek.com
│   └── utils.py             # HumanTypist — realistic keystroke simulation
└── RawData/
    ├── DataSets/
    │   ├── OEQ.csv            # Open-ended questions
    │   ├── AITA-NTA-OG.csv    # AITA — not-the-asshole, original stories
    │   ├── AITA-NTA-FLIP.csv  # AITA — not-the-asshole, flipped stories
    │   ├── AITA-YTA.csv       # AITA — you're-the-asshole
    │   └── SS.csv             # Sensitive situations
    ├── Prompts/
    │   └── <DATASET>.txt      # Optional base prompt per dataset (if present)
    └── SavedData/
        ├── ChatGPT/
        ├── Claude/
        ├── Gemini/
        └── DeepSeek/          # Output: one JSON file per model × dataset
```

---

## Output format

Each run saves to `RawData/SavedData/<MODEL>/<DATASET>.json` as a JSON object keyed by prompt ID:

```json
{
  "42": [
    {
      "turn": 1,
      "user": "<the prompt text>",
      "model_output": "<the model's response>"
    }
  ]
}
```

---

## Benchmarks

### ELEPHANT — Social Sycophancy

*ELEPHANT* targets social sycophancy — cases where a model prioritises preserving the user's self-image over giving an honest response. The benchmark covers five datasets drawn from open-ended advice queries and the r/AmITheAsshole subreddit, and scores responses across four dimensions: validation, indirectness, framing, and moral endorsement.

| Dataset | Description |
|---------|-------------|
| `OEQ` | Open-ended questions |
| `AITA-NTA-OG` | AITA posts where the poster is not the asshole (original) |
| `AITA-NTA-FLIP` | Same posts with the story flipped (swapped perspective) |
| `AITA-YTA` | AITA posts where the poster is the asshole |
| `SS` | Sensitive situation prompts |

For each dimension, we report the rate of face-preserving responses — how often the model affirms the user's position rather than offering a neutral or corrective answer. A higher rate in the web-UI group compared to the API groups would suggest that the web interface amplifies socially sycophantic behaviour.

> Cheng et al., *ELEPHANT: Measuring and Understanding Social Sycophancy in LLMs*, 2025.
> [arXiv:2505.13995](https://arxiv.org/abs/2505.13995)

---

## Notes

- Browser sessions (login cookies) are stored in `*_ui_session/` folders and are excluded from version control. Each platform only requires one manual login per machine.
- The scraper simulates human typing speed and adds randomised delays between requests to reduce bot-detection risk.
- If the active model does not match the expected mode in `_MODE_MAP`, the run aborts early rather than silently collecting data under the wrong configuration.
- Base prompts are optional. If `RawData/Prompts/<DATASET>.txt` exists it is prepended to the first message; if not, prompts are sent as-is.

---

## License

This project is licensed under the [MIT License](LICENSE).

---

## Acknowledgements

The base code for this project was written by Alek Klem. [Claude Code](https://claude.ai/claude-code) was used to supplement the project — assisting with code cleanup, refactoring, and the creation of this README.
