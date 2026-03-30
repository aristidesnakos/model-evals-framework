# Evaluation Report: swms_safety_generator

**Run ID:** 20260330_183136
**Date:** 2026-03-30 20:34 UTC
**Runs per test:** 3
**Judges:** anthropic/claude-sonnet-4.6, openai/gpt-5.4

## Summary

| Model | Avg Score | Min | Max | Std Dev | Avg Latency | Total Tokens | Errors |
|-------|-----------|-----|-----|---------|-------------|-------------|--------|
| GPT-5.4 Mini | 8.1/10 | 7.33 | 8.93 | 0.2 | 12.3s | 41,543 | 0 |
| GPT-5.4 Nano | 7.9/10 | 7.24 | 8.5 | 0.28 | 12.7s | 47,034 | 0 |
| Mistral Small 4 | 7.6/10 | 7.11 | 8.16 | 0.16 | 11.5s | 43,658 | 0 |
| Gemini 3.1 Flash Lite | 7.4/10 | 6.67 | 8.29 | 0.22 | 6.8s | 31,940 | 0 |
| Qwen 3.5 Plus | 7.4/10 | 6.8 | 8.27 | 0.23 | 84.5s | 100,463 | 0 |
| Qwen 3.5 Flash | 7.0/10 | 5.93 | 8.16 | 0.3 | 120.6s | 196,002 | 0 |

## Per-Test-Case Results

### Demolition — load-bearing structural element
*Category: structured_generation | ID: swms_001*

| Model | Avg | Std Dev | Completeness | Accuracy | Format | Domain | Clarity |
|-------|-----|---------|-------------|----------|--------|--------|---------|
| GPT-5.4 Mini | 8.93 | 0.15 | 9.7 | 8.8 | 9.5 | 7.0 | 9.0 |
| GPT-5.4 Nano | 8.5 | 0.5 | 9.2 | 8.2 | 9.0 | 7.0 | 9.0 |
| Gemini 3.1 Flash Lite | 8.29 | 0.28 | 8.3 | 8.3 | 9.5 | 6.7 | 8.7 |
| Qwen 3.5 Plus | 8.27 | 0.27 | 9.3 | 7.5 | 9.5 | 6.5 | 8.2 |
| Mistral Small 4 | 8.16 | 0.3 | 8.8 | 8.0 | 8.0 | 6.8 | 8.8 |
| Qwen 3.5 Flash | 8.16 | 0.21 | 9.0 | 7.7 | 9.5 | 6.2 | 8.2 |

### Asbestos disturbance during renovation
*Category: structured_generation | ID: swms_002*

| Model | Avg | Std Dev | Completeness | Accuracy | Format | Domain | Clarity |
|-------|-----|---------|-------------|----------|--------|--------|---------|
| Mistral Small 4 | 7.43 | 0.23 | 8.5 | 6.2 | 9.3 | 5.3 | 8.3 |
| GPT-5.4 Nano | 7.38 | 0.07 | 8.2 | 6.5 | 9.0 | 5.3 | 8.3 |
| GPT-5.4 Mini | 7.33 | 0.16 | 7.8 | 6.5 | 9.2 | 5.3 | 8.5 |
| Qwen 3.5 Plus | 7.27 | 0.24 | 7.8 | 6.5 | 9.5 | 5.0 | 8.0 |
| Gemini 3.1 Flash Lite | 7.2 | 0.05 | 7.5 | 6.5 | 9.3 | 5.3 | 8.0 |
| Qwen 3.5 Flash | 6.96 | 0.44 | 7.8 | 5.8 | 9.3 | 4.7 | 7.7 |

### Electrical work near energised services
*Category: structured_generation | ID: swms_003*

| Model | Avg | Std Dev | Completeness | Accuracy | Format | Domain | Clarity |
|-------|-----|---------|-------------|----------|--------|--------|---------|
| GPT-5.4 Mini | 8.5 | 0.22 | 8.8 | 8.2 | 10.0 | 6.7 | 9.0 |
| GPT-5.4 Nano | 8.22 | 0.29 | 8.8 | 7.8 | 8.7 | 7.0 | 8.7 |
| Gemini 3.1 Flash Lite | 8.14 | 0.16 | 7.7 | 8.5 | 10.0 | 6.2 | 8.7 |
| Mistral Small 4 | 7.66 | 0.14 | 8.3 | 6.8 | 9.0 | 6.2 | 8.3 |
| Qwen 3.5 Flash | 7.57 | 0.31 | 8.2 | 7.0 | 9.7 | 5.2 | 8.0 |
| Qwen 3.5 Plus | 6.8 | 0.54 | 7.3 | 6.0 | 9.2 | 4.5 | 7.5 |

### Confined space entry — multi-risk scenario
*Category: structured_generation | ID: swms_004*

| Model | Avg | Std Dev | Completeness | Accuracy | Format | Domain | Clarity |
|-------|-----|---------|-------------|----------|--------|--------|---------|
| Mistral Small 4 | 7.91 | 0.06 | 8.5 | 7.5 | 9.5 | 5.8 | 8.2 |
| Qwen 3.5 Plus | 7.9 | 0.04 | 8.5 | 7.5 | 10.0 | 5.3 | 8.0 |
| GPT-5.4 Mini | 7.71 | 0.34 | 8.2 | 7.2 | 10.0 | 5.2 | 8.3 |
| Gemini 3.1 Flash Lite | 7.28 | 0.17 | 7.3 | 7.2 | 9.3 | 5.0 | 7.8 |
| GPT-5.4 Nano | 7.24 | 0.38 | 7.5 | 7.0 | 8.7 | 5.2 | 8.2 |
| Qwen 3.5 Flash | 7.16 | 0.11 | 7.8 | 6.5 | 9.5 | 4.7 | 7.3 |

### Working at heights — falls >2m on scaffold
*Category: structured_generation | ID: swms_005*

| Model | Avg | Std Dev | Completeness | Accuracy | Format | Domain | Clarity |
|-------|-----|---------|-------------|----------|--------|--------|---------|
| GPT-5.4 Mini | 8.2 | 0.09 | 8.8 | 8.0 | 9.5 | 5.5 | 9.0 |
| GPT-5.4 Nano | 7.98 | 0.33 | 8.7 | 7.8 | 9.0 | 5.3 | 8.8 |
| Mistral Small 4 | 7.29 | 0.1 | 7.5 | 7.2 | 9.2 | 4.7 | 8.2 |
| Qwen 3.5 Plus | 7.02 | 0.15 | 7.2 | 6.8 | 9.5 | 4.0 | 8.0 |
| Gemini 3.1 Flash Lite | 6.67 | 0.53 | 6.5 | 6.5 | 9.5 | 3.7 | 8.0 |
| Qwen 3.5 Flash | 6.23 | 0.52 | 6.8 | 5.8 | 8.0 | 3.2 | 7.5 |

### Excavation near pressurised gas mains
*Category: structured_generation | ID: swms_006*

| Model | Avg | Std Dev | Completeness | Accuracy | Format | Domain | Clarity |
|-------|-----|---------|-------------|----------|--------|--------|---------|
| GPT-5.4 Nano | 8.05 | 0.13 | 8.5 | 7.7 | 8.7 | 7.0 | 8.5 |
| GPT-5.4 Mini | 7.87 | 0.25 | 8.0 | 7.0 | 9.7 | 7.0 | 8.7 |
| Qwen 3.5 Plus | 7.32 | 0.13 | 7.7 | 6.5 | 9.5 | 5.7 | 8.0 |
| Mistral Small 4 | 7.11 | 0.14 | 7.5 | 6.2 | 8.8 | 6.0 | 7.8 |
| Gemini 3.1 Flash Lite | 7.05 | 0.11 | 7.2 | 6.2 | 9.3 | 5.7 | 8.0 |
| Qwen 3.5 Flash | 5.93 | 0.23 | 6.2 | 5.0 | 8.2 | 4.5 | 6.8 |

## Reliability Analysis

Models with high standard deviation across runs may produce inconsistent results.

| Model | Avg Std Dev | Reliability |
|-------|-----------|-------------|
| GPT-5.4 Mini | 0.2 | High |
| GPT-5.4 Nano | 0.28 | High |
| Mistral Small 4 | 0.16 | High |
| Gemini 3.1 Flash Lite | 0.22 | High |
| Qwen 3.5 Plus | 0.23 | High |
| Qwen 3.5 Flash | 0.3 | High |

---
*Generated by EvalPulse on 2026-03-30 20:34 UTC*