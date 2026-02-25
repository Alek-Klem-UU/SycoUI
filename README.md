<img src="https://github.com/UtrechtUniversity.png" alt="Utrecht University" width="80" align="right"/>

# SycoUI

A browser-automation tool that sends adversarial mathematical problems to four AI chatbots and records their full responses for comparative analysis. Built for thesis research at Utrecht University.

---

## What it does

For each problem in a configured benchmark dataset, the scraper:

1. Opens a persistent browser session for the selected AI platform
2. Waits for the user to log in manually (sessions are saved, so this is only needed once)
3. Sends the base prompt followed by each problem
4. Waits for the model to finish responding
5. Scrapes the full conversation and saves it to JSON

Results are saved incrementally, so the run can be interrupted and resumed at any time. The tool currently supports two sycophancy benchmarks: **BrokenMath** and **ELEPHANT**.

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

## Benchmarks

### BrokenMath — Single-Turn Accuracy

*BrokenMath* prompts are single-turn: the model receives a flawed mathematical theorem and gives one response. We record whether that response agrees with the flawed premise or correctly rejects it. The primary metric is the **Sycophancy Rate (SR)** — the share of prompts where the model accepts the incorrect theorem:

$$SR = \frac{\text{Number of sycophantic responses}}{\text{Total prompts}}$$

> Petrov et al., *BrokenMath: A Benchmark for Sycophancy in Theorem Proving with LLMs*, NeurIPS 2025.
> [arXiv:2510.04721](https://arxiv.org/abs/2510.04721) · [HuggingFace](https://huggingface.co/datasets/INSAIT-Institute/BrokenMath)

---

### ELEPHANT — Social Sycophancy

*ELEPHANT* targets social sycophancy — cases where a model prioritises preserving the user's self-image over giving an honest response. Prompts are single-turn, drawn from open-ended advice queries and the r/AmITheAsshole subreddit. The benchmark scores responses across four dimensions: validation, indirectness, framing, and moral endorsement.

For each dimension, we report the rate of face-preserving responses — how often the model affirms the user's position rather than offering a neutral or corrective answer. A higher rate in the web-UI group compared to the API groups would suggest that the web interface amplifies socially sycophantic behaviour.

> Cheng et al., *ELEPHANT: Measuring and Understanding Social Sycophancy in LLMs*, 2025.
> [arXiv:2505.13995](https://arxiv.org/abs/2505.13995)

---

## Notes

- Browser sessions (login cookies) are stored in `*_ui_session/` folders and are excluded from version control. Each platform only requires one manual login per machine.
- The scraper simulates human typing speed and adds randomised delays between requests to reduce bot-detection risk.
- If the active model does not match the expected mode in `_MODE_MAP`, the run aborts early rather than silently collecting data under the wrong configuration.

---

## License

This project is licensed under the [MIT License](LICENSE).

---

## Acknowledgements

The base code for this project was written by Alek Klem. [Claude Code](https://claude.ai/claude-code) was used to supplement the project — assisting with code cleanup, refactoring, and the creation of this README.
