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

The tool runs in one of two **modes**:

- **Browser** — opens a persistent Chromium session, waits for manual login, then sends each prompt through the commercial web UI and scrapes the rendered conversation.
- **API** — calls the provider's official developer SDK directly with a key you supply at runtime.

In both modes, results are saved incrementally per prompt, so a run can be interrupted and resumed at any time. Browser and API outputs for the same model are written to separate folders so they never overwrite each other — the comparison between them *is* the experiment.

---

## Supported platforms

| Key | Browser mode | Browser model | API mode | API model |
|-----|--------------|---------------|----------|-----------|
| `ChatGPT` | chatgpt.com | ChatGPT | OpenAI SDK | `gpt-4o` |
| `Claude` | claude.ai | Sonnet 4.6 | Anthropic SDK | `claude-sonnet-4-6` |
| `Gemini` | gemini.google.com | Fast | Google GenAI SDK | `gemini-2.5-flash` |

---

## Setup

**Requirements:** Python 3.12+

```bash
cd ThesisScraper
pip install -r requirements.txt
```

Install the Chromium browser used by Patchright (only needed for Browser mode):

```bash
patchright install chromium
```

For API mode, you need a key from each provider you intend to run. Keys can be supplied either way:

- **Environment variable** (skips the prompt): `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`
- **Interactive prompt** (input is hidden): the tool will ask at startup if no env var is set

---

## Usage

```bash
cd ThesisScraper
python main.py
```

An interactive menu will prompt you to select a **mode** (Browser or API), a **model**, and a **subset size**.

- In **Browser mode**, a Chromium window opens and pauses for login. Once you are logged in and the chat interface is ready, press **Enter** in the terminal and the scraper will run through the dataset automatically.
- In **API mode**, you'll be prompted for the API key (unless the relevant environment variable is set), and the run starts immediately — no browser is launched.

Progress is saved after every prompt. To resume an interrupted run, just run `main.py` again with the same mode and model — already-completed entries are skipped.

---

## Project structure

```
ThesisScraper/
├── main.py                  # Entry point — orchestration, CLI, run loop
├── cli.py                   # Terminal UI — menus, styled output, API-key prompt
├── data_processing.py       # Load prompts, save/load results, token counting
├── browsers/
│   ├── browser_base.py      # Shared retry logic, selector resolution, error types
│   ├── claude_browser.py    # Automation for claude.ai
│   ├── chatgpt_browser.py   # Automation for chatgpt.com
│   ├── gemini_browser.py    # Automation for gemini.google.com
│   └── utils.py             # HumanTypist — realistic keystroke simulation
├── apis/
│   ├── api_base.py          # Shared retry logic + browser-compatible interface
│   ├── claude_api.py        # Anthropic SDK client
│   ├── chatgpt_api.py       # OpenAI SDK client
│   └── gemini_api.py        # Google GenAI SDK client
├── requirements.txt
└── RawData/
    ├── DataSets/
    │   └── AITA-YTA-1000.csv  # Input: 1,000 sampled AITA-YTA prompts
    └── SavedData/
        └── <Model>/<Mode>/<dataset>.json   # e.g. Claude/Browser/, Claude/API/
```

---

## Output format

Each run's results are saved to `RawData/SavedData/<MODEL>/<MODE>/AITA-YTA-1000.json`, keyed by prompt ID:

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
- Progress is persisted atomically (tmp-file + rename), so a crash or power loss during a long run cannot leave a half-written JSON file.
- Token counts are logged at startup using `tiktoken` (`cl100k_base`) as an order-of-magnitude cost estimate — real per-provider tokenisation differs, especially for Gemini.
- API keys are never persisted or logged: they are read from the relevant environment variable if set, or collected at the start of an API-mode run via a hidden (`getpass`) prompt, and then held only on the client instance until the process exits.
- Transient API failures (rate limits, server errors, connection drops) are retried up to 3× with exponential backoff; non-transient errors (e.g. authentication) surface immediately instead of being retried.

---

## License

This project is licensed under the [MIT License](LICENSE).

---

## Acknowledgements

The base code for this project was written by Alek Klem. [Claude Code](https://claude.ai/claude-code) was used to supplement the project — assisting with code cleanup, refactoring, the API-mode integration, and the creation of this README.
