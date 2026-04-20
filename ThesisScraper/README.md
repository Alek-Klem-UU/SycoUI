<img src="https://github.com/UtrechtUniversity.png" alt="Utrecht University" width="80" align="right"/>

# SycoUI

A browser-automation tool for measuring social sycophancy in AI web interfaces. Built for thesis research at Utrecht University comparing sycophantic behaviour between raw developer APIs and commercial web interfaces across three major LLM providers.

---

## Research context

Almost all sycophancy research is conducted through developer APIs, yet most users interact with AI through commercial web interfaces — which layer hidden system prompts, persona instructions, and content filters on top of the raw model. Whether these layers change how sycophantically a model behaves has not been systematically studied.

This tool operationalises that comparison. It automates the web interface condition (Group B) of a controlled study evaluating 1,000 prompts from the **ELEPHANT** benchmark across three providers. Responses are later scored across four dimensions: validation, indirectness, framing, and moral endorsement.

> Full proposal: *Comparing Sycophantic Tendencies in Proprietary Interfaces versus Developer APIs*, Alek Klem, Utrecht University (2026). Supervisor: Dr. Uwe Peters.

---

## What it does

For each prompt in the dataset, the scraper:

1. Opens a persistent browser session for the selected AI platform
2. Waits for the user to log in manually (sessions are saved, so this is only needed once)
3. Sends the prompt to the model
4. Waits for the model to finish responding
5. Scrapes the full conversation and saves it to JSON

Results are saved incrementally, so the run can be interrupted and resumed at any time.

---

## Supported platforms

| Key | Platform | Mode |
|-----|----------|------|
| `ChatGPT` | chatgpt.com | ChatGPT |
| `Claude` | claude.ai | Sonnet 4.6 |
| `Gemini` | gemini.google.com | Fast |

---

## Setup

**Requirements:** Python 3.12+

```bash
cd ThesisScraper
pip install -r requirements.txt
```

Install the Chromium browser used by Patchright:

```bash
patchright install chromium
```

---

## Usage

```bash
cd ThesisScraper
python main.py
```

An interactive menu will prompt you to select a model and subset size. The browser window will then open and pause for login. Once you are logged in and the chat interface is ready, press **Enter** in the terminal. The scraper will run through the dataset automatically.

Progress is saved after every prompt. To resume an interrupted run, just run `main.py` again with the same model — already-completed entries are skipped.

---

## Project structure

```
ThesisScraper/
├── main.py                  # Entry point — orchestration, CLI, run loop
├── cli.py                   # Terminal UI — menus, styled output
├── data_processing.py       # Load prompts, save/load results, token counting
├── browsers/
│   ├── browser_base.py      # Shared retry logic, selector resolution, error types
│   ├── claude_browser.py    # Automation for claude.ai
│   ├── chatgpt_browser.py   # Automation for chatgpt.com
│   ├── gemini_browser.py    # Automation for gemini.google.com
│   └── utils.py             # HumanTypist — realistic keystroke simulation
├── requirements.txt
└── RawData/
    ├── DataSets/
    │   └── AITA-YTA-1000.csv  # Input: 1,000 sampled AITA-YTA prompts
    └── SavedData/
        ├── ChatGPT/
        ├── Claude/
        └── Gemini/            # Output: one JSON file per model
```

---

## Output format

Each model's results are saved to `RawData/SavedData/<MODEL>/AITA-YTA-1000.json`, keyed by prompt ID:

```json
{
  "42": [
    {
      "turn": 1,
      "user": "<the prompt text>",
      "model_output": "<the model's response>"
    }
  ],
  "43": "IN PROGRESS"
}
```

An `"IN PROGRESS"` entry indicates the run was interrupted before that prompt completed — it will be retried on the next run.

---

## Benchmark

### ELEPHANT — Social Sycophancy

*ELEPHANT* targets social sycophancy: cases where a model prioritises preserving the user's self-image over giving an honest response. This study uses the **AITA-YTA** subset, where community consensus has already established that the poster is in the wrong in each scenario — making any face-preserving model response unambiguously sycophantic.

Responses are scored across four dimensions:

| Dimension | What it measures |
|-----------|-----------------|
| Validation | Whether the model affirms the user's position |
| Indirectness | Whether criticism is softened or avoided |
| Framing | Whether the situation is framed to favour the user |
| Moral endorsement | Whether the model endorses questionable behaviour |

A higher face-preserving rate in the web interface condition relative to the API condition would support the hypothesis that commercial deployments amplify sycophantic behaviour beyond what the underlying model exhibits.

> Cheng et al., *ELEPHANT: Measuring and Understanding Social Sycophancy in LLMs*, 2025.
> [arXiv:2505.13995](https://arxiv.org/abs/2505.13995)

---

## Notes

- Browser sessions (login cookies) are stored in `*_ui_session/` folders and are excluded from version control. Each platform only requires one manual login per machine.
- The scraper simulates human typing speed and adds randomised delays between requests to reduce bot-detection risk.
- If the active model does not match the expected mode, the run aborts early rather than silently collecting data under the wrong configuration.
- Token counts are logged at startup using `tiktoken` (cl100k_base) as an order-of-magnitude cost estimate.

---

## License

This project is licensed under the [MIT License](LICENSE).

---

## Acknowledgements

The base code for this project was written by Alek Klem. [Claude Code](https://claude.ai/claude-code) was used to supplement the project — assisting with code cleanup, refactoring, and the creation of this README.
