<img src="https://github.com/UtrechtUniversity.png" alt="Utrecht University" width="80" align="right"/>

# SycoUI

**SycoUI** is a Python-based data-collection pipeline for comparing the behavior of large language models (LLMs) across consumer-facing user interfaces (UIs) and developer APIs.

It was developed at Utrecht University as part of a research project examining whether access mode affects **social sycophancy** in LLMs. The project evaluates ChatGPT, Claude, Gemini, and DeepSeek using matched prompts from the ELEPHANT benchmark.

SycoUI supports standardized collection from both provider APIs and their consumer web interfaces, with incremental saving and resumable runs designed for long-running UI evaluations.

## Research Context

Most behavioral evaluations of LLMs are conducted through developer APIs, even though many users interact with these systems through consumer-facing interfaces.

API and UI access are not necessarily behaviorally equivalent. Consumer interfaces may introduce additional system instructions, safety mechanisms, routing decisions, memory features, reasoning configurations, or other product-level interventions. As a result, evaluations conducted through APIs may not fully characterize the systems encountered by users.

The associated study compares social sycophancy under API and consumer-UI access across four major LLMs.

## Supported Models

| Provider | Consumer UI model | API model identifier | API default | API T = 0 | UI repetitions |
|---|---|---|---:|---:|---:|
| OpenAI | ChatGPT-5.3 | `gpt-5.3-chat-latest` | yes | no | 3 |
| Anthropic | Claude Sonnet 4.6 | `claude-sonnet-4-6` | yes | yes | 3 |
| Google | Gemini 3 Flash | `gemini-3-flash-preview` | yes | yes | 3 |
| DeepSeek | DeepSeek-V4-Flash | `deepseek-v4-flash` | yes | yes | 3 |

Reasoning configurations were matched across access conditions where provider controls allowed this:

- Gemini used low reasoning effort through the API to correspond to Fast mode in the consumer UI.
- DeepSeek reasoning was disabled.
- Claude extended reasoning was not enabled.
- ChatGPT reasoning effort could not be directly controlled.

## What SycoUI Does

SycoUI supports two data-collection modes.

### Consumer UI mode

The pipeline opens a persistent Chromium browser session and submits prompts directly through the provider's consumer interface.

Provider-specific adapters handle:

- interface navigation;
- prompt submission;
- response extraction;
- response-completion detection;
- model selection or verification where possible;
- retries for incomplete or failed collection attempts.

Each provider has its own browser adapter because commercial interfaces differ substantially and may change over time.

### API mode

The same prompt sets can be submitted directly to provider APIs.

Each API prompt is sent as an independent one-turn request so that conversational history does not carry over between observations. API responses are stored in the same general result format as consumer-UI responses.

Temporary API failures, such as rate limits or server errors, are retried automatically.

## Resumable Data Collection

SycoUI saves progress continuously during collection.

Before a prompt is processed, it is marked as:

```json
"IN PROGRESS"
