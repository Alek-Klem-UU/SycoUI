<img src="https://github.com/UtrechtUniversity.png" alt="Utrecht University" width="80" align="right"/>

# SycoUI

SycoUI is the data-collection tool used for the bachelor thesis *Comparing Sycophantic Tendencies in Proprietary Interfaces versus Developer APIs* by Alek Klem at Utrecht University.

The project compares whether consumer web interfaces make large language models more socially sycophantic than the same providers' developer APIs. The study calls this behavioral difference the **Interface Effect**.

## Research Context

Most sycophancy research evaluates models through developer APIs, but most users interact with AI systems through commercial web products. These interfaces can add hidden system prompts, persona layers, memory/context features, tool-routing logic, and product-level safety filters on top of the underlying model.

SycoUI was built to test whether those interface layers change model behavior. It collects matched responses from browser interfaces and APIs, then stores them for later scoring on the ELEPHANT social-sycophancy benchmark.

The thesis evaluates four consumer-facing systems:

| Provider | Browser model | API model identifier | API default | API T = 0 | Browser runs |
|---|---|---|---:|---:|---:|
| OpenAI | ChatGPT-5.3 | `gpt-5.3-chat-latest` | yes | no | 3 per prompt |
| Anthropic | Claude Sonnet 4.6 | `claude-sonnet-4-6` | yes | yes | 3 per prompt |
| Google | Gemini 3 Flash | `gemini-3-flash-preview` | yes | yes | 3 per prompt |
| DeepSeek | DeepSeek-V4-Flash | `deepseek-v4-flash` | yes | yes | 3 per prompt |

Browser data for AITA-YTA was collected from April 30 to May 4, 2026. Browser data for AITA-NTA and AITA-NTA-FLIPPED was collected from May 7 to May 16, 2026, with ChatGPT finishing on May 18, 2026 after OpenAI changed the browser default model and the automation had to reselect ChatGPT-5.3 manually.

## What It Does

SycoUI supports two collection modes:

- **Browser mode** opens a persistent Chromium session, waits for manual login, sends prompts through the commercial web UI, and scrapes the rendered response.
- **API mode** calls the provider's developer API with the same prompt set and saves responses in the same result format.

Runs are saved incrementally after every prompt. If a run is interrupted, restarting the same model/mode skips completed prompts and retries incomplete ones.

The browser pipeline uses Patchright, a stealth-patched Playwright fork, plus human-like typing delays and rate-limit backoff. Each provider has a dedicated browser class with multiple selector candidates because commercial UIs change frequently.

## Benchmark and Datasets

The study uses ELEPHANT, a benchmark for social sycophancy: cases where a model preserves the user's self-image instead of giving an honest assessment.

SycoUI collects responses for two ELEPHANT subsets:

| Subset | Use | Sample |
|---|---|---:|
| `AITA-YTA` | Validation, indirectness, and framing | 1,000 prompts |
| `AITA-NTA` + `AITA-NTA-FLIPPED` | Moral endorsement | 1,000 matched prompt pairs |

The AITA-YTA subset contains posts where Reddit's r/AmITheAsshole community judged the poster to be at fault. If a model validates the poster anyway, that response can be scored as socially sycophantic.

The moral-endorsement subset presents the same conflict from both sides. A sycophantic model may endorse whoever is asking, even when the two perspectives are mutually inconsistent.

Responses are scored across four dimensions:

| Dimension | What it measures |
|---|---|
| Validation | Whether the model affirms the user's feelings or position when that affirmation is unwarranted |
| Indirectness | Whether the model hedges or softens criticism instead of giving clear advice |
| Framing | Whether the model accepts a flawed premise instead of challenging the user's framing |
| Moral endorsement | Whether the model sides with both parties when the same conflict is shown from opposite perspectives |

## Thesis Findings

The thesis finds evidence for an Interface Effect across all four evaluated models on at least one sycophancy dimension.

- Claude shows significant browser increases across validation, indirectness, and framing.
- Gemini shows significant browser gaps on validation, indirectness, and framing, although framing reverses direction: the browser is less sycophantic than API default on that dimension.
- ChatGPT shows significant browser increases on indirectness and framing. Validation is near ceiling in both conditions.
- DeepSeek shows no significant browser gap on validation or framing, a small significant browser increase on indirectness, and a strong reversal on moral endorsement.

The largest AITA-YTA effect is ChatGPT-5.3 on framing: browser responses are estimated to be almost 49 times more likely to be sycophantic than API-default responses.

These results suggest that API-only alignment evaluations can miss behavior introduced or amplified by consumer product interfaces.

## Setup

Requirements: Python 3.12+

```bash
cd ThesisScraper
pip install -r requirements.txt
```

Install the Chromium browser used by Patchright for browser mode:

```bash
patchright install chromium
```

For API mode, provide the relevant provider key either through an environment variable or the hidden interactive prompt at startup.

Supported environment variables:

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GEMINI_API_KEY`
- `DEEPSEEK_API_KEY`

## Usage

```bash
cd ThesisScraper
python main.py
```

The interactive menu asks for:

- collection mode: browser or API
- provider/model
- dataset/subset size

In browser mode, a Chromium window opens and pauses for login. After the chat interface is ready, press Enter in the terminal and the scraper proceeds automatically.

In API mode, the run starts immediately once the API key is available.

## Project Structure

```text
ThesisScraper/
|-- main.py                  # Entry point and run orchestration
|-- cli.py                   # Terminal menus and API-key prompt
|-- data_processing.py       # Prompt loading, result persistence, token estimates
|-- browsers/
|   |-- browser_base.py      # Shared browser automation and retry behavior
|   |-- chatgpt_browser.py   # chatgpt.com automation
|   |-- claude_browser.py    # claude.ai automation
|   |-- gemini_browser.py    # gemini.google.com automation
|   |-- deepseek_browser.py  # chat.deepseek.com automation
|   `-- utils.py             # HumanTypist and browser helpers
|-- apis/
|   |-- api_base.py          # Shared API client interface and retries
|   |-- chatgpt_api.py       # OpenAI API client
|   |-- claude_api.py        # Anthropic API client
|   |-- gemini_api.py        # Google GenAI API client
|   `-- deepseek_api.py      # DeepSeek API client
|-- requirements.txt
`-- RawData/
    |-- DataSets/            # ELEPHANT prompt subsets
    `-- SavedData/           # Collected model outputs by provider and mode
```

## Output Format

Results are saved under:

```text
RawData/SavedData/<MODEL>/<MODE>/<dataset>.json
```

Each file is keyed by prompt ID:

```json
{
  "42": [
    {
      "turn": 1,
      "user": "<prompt text>",
      "model_output": "<model response>"
    }
  ],
  "43": "IN PROGRESS"
}
```

An `"IN PROGRESS"` entry means the run stopped before that prompt completed. It will be retried on the next run.

## Notes

- Browser sessions are stored in `*_ui_session/` folders and should not be committed.
- Browser responses are collected three times per prompt because commercial web interfaces do not expose sampling parameters.
- API default runs approximate each provider's normal API behavior; API T = 0 runs expose the model's greedy response where the provider supports it.
- Thinking effort is matched where possible: Gemini uses low API thinking effort to match browser Fast mode, DeepSeek has thinking disabled, Claude does not use extended thinking by default, and ChatGPT thinking effort is not directly controllable.
- Progress is persisted atomically with a temporary file and rename.
- API keys are read from environment variables or hidden prompts and are never logged or persisted.

## License

This project is licensed under the [MIT License](LICENSE).

## Acknowledgements

The base code for this project was written by Alek Klem. Claude Code was used to supplement the project by assisting with code cleanup, refactoring, API-mode integration, and README drafting.
