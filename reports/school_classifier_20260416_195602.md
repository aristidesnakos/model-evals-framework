# Evaluation Report: school_classifier

**Run ID:** 20260416_195602
**Date:** 2026-04-16 21:16 UTC
**Runs per test:** 3
**Judges:** anthropic/claude-sonnet-4.6, openai/gpt-5.4

## Summary

| Model | Avg Score | Min | Max | Std Dev | Avg Latency | Total Tokens | Errors |
|-------|-----------|-----|-----|---------|-------------|-------------|--------|
| GPT-5.4 Mini | 10.0/10 | 9.95 | 10.0 | 0.03 | 1.0s | 23,714 | 0 |
| Gemini 3.1 Flash Lite | 10.0/10 | 9.92 | 10.0 | 0.03 | 2.7s | 23,950 | 0 |
| GPT-5.4 Nano | 10.0/10 | 9.93 | 10.0 | 0.03 | 1.1s | 23,723 | 0 |
| Gemma 4 26B A4B IT | 10.0/10 | 9.95 | 10.0 | 0.03 | 1.8s | 25,521 | 0 |
| Gemma 4 31B IT | 10.0/10 | 9.93 | 10.0 | 0.03 | 15.5s | 20,321 | 16 |

## Per-Test-Case Results

### Maths test notice (homework, not schedule_change)
*Category: homework | ID: tc_01*

| Model | Avg | Std Dev | Completeness | Accuracy | Format | Domain | Clarity |
|-------|-----|---------|-------------|----------|--------|--------|---------|
| GPT-5.4 Mini | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| Gemma 4 26B A4B IT | 9.97 | 0.03 | 10.0 | 10.0 | 10.0 | 9.7 | 10.0 |
| GPT-5.4 Nano | 9.95 | 0.05 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |
| Gemma 4 31B IT | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |
| Gemini 3.1 Flash Lite | 9.92 | 0.03 | 10.0 | 10.0 | 10.0 | 9.2 | 10.0 |

### Swimming gala (sports, not event)
*Category: sports | ID: tc_02*

| Model | Avg | Std Dev | Completeness | Accuracy | Format | Domain | Clarity |
|-------|-----|---------|-------------|----------|--------|--------|---------|
| GPT-5.4 Nano | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| Gemma 4 26B A4B IT | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| GPT-5.4 Mini | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |
| Gemini 3.1 Flash Lite | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |
| Gemma 4 31B IT | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |

### Assembly moved — schedule change
*Category: schedule_change | ID: tc_03*

| Model | Avg | Std Dev | Completeness | Accuracy | Format | Domain | Clarity |
|-------|-----|---------|-------------|----------|--------|--------|---------|
| GPT-5.4 Mini | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| GPT-5.4 Nano | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| Gemini 3.1 Flash Lite | 9.98 | 0.03 | 10.0 | 10.0 | 10.0 | 9.8 | 10.0 |
| Gemma 4 26B A4B IT | 9.98 | 0.03 | 10.0 | 10.0 | 10.0 | 9.8 | 10.0 |
| Gemma 4 31B IT | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |

### Parent evening — event
*Category: event | ID: tc_04*

| Model | Avg | Std Dev | Completeness | Accuracy | Format | Domain | Clarity |
|-------|-----|---------|-------------|----------|--------|--------|---------|
| Gemini 3.1 Flash Lite | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| GPT-5.4 Nano | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| Gemma 4 26B A4B IT | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| Gemma 4 31B IT | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| GPT-5.4 Mini | 9.97 | 0.03 | 10.0 | 10.0 | 10.0 | 9.7 | 10.0 |

### Science fair project deadline — homework
*Category: homework | ID: tc_05*

| Model | Avg | Std Dev | Completeness | Accuracy | Format | Domain | Clarity |
|-------|-----|---------|-------------|----------|--------|--------|---------|
| GPT-5.4 Nano | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| GPT-5.4 Mini | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |
| Gemini 3.1 Flash Lite | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |
| Gemma 4 26B A4B IT | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |
| Gemma 4 31B IT | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |

### Easter holiday closure (admin, not schedule_change)
*Category: admin | ID: tc_06*

| Model | Avg | Std Dev | Completeness | Accuracy | Format | Domain | Clarity |
|-------|-----|---------|-------------|----------|--------|--------|---------|
| GPT-5.4 Mini | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |
| Gemini 3.1 Flash Lite | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |
| GPT-5.4 Nano | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |
| Gemma 4 26B A4B IT | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |
| Gemma 4 31B IT | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |

### Rugby tour — sports
*Category: sports | ID: tc_07*

| Model | Avg | Std Dev | Completeness | Accuracy | Format | Domain | Clarity |
|-------|-----|---------|-------------|----------|--------|--------|---------|
| GPT-5.4 Mini | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| Gemini 3.1 Flash Lite | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| Gemma 4 26B A4B IT | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| Gemma 4 31B IT | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| GPT-5.4 Nano | 9.97 | 0.03 | 10.0 | 10.0 | 10.0 | 9.7 | 10.0 |

### School camp — event
*Category: event | ID: tc_08*

| Model | Avg | Std Dev | Completeness | Accuracy | Format | Domain | Clarity |
|-------|-----|---------|-------------|----------|--------|--------|---------|
| GPT-5.4 Mini | 9.95 | 0.05 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |
| Gemini 3.1 Flash Lite | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |
| GPT-5.4 Nano | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |
| Gemma 4 26B A4B IT | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |
| Gemma 4 31B IT | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |

### History essay — homework
*Category: homework | ID: tc_09*

| Model | Avg | Std Dev | Completeness | Accuracy | Format | Domain | Clarity |
|-------|-----|---------|-------------|----------|--------|--------|---------|
| GPT-5.4 Mini | 9.98 | 0.03 | 10.0 | 10.0 | 10.0 | 9.8 | 10.0 |
| GPT-5.4 Nano | 9.98 | 0.03 | 10.0 | 10.0 | 10.0 | 9.8 | 10.0 |
| Gemma 4 26B A4B IT | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |
| Gemma 4 31B IT | 9.93 | 0.03 | 10.0 | 10.0 | 10.0 | 9.3 | 10.0 |
| Gemini 3.1 Flash Lite | 9.92 | 0.03 | 10.0 | 10.0 | 10.0 | 9.2 | 10.0 |

### Lunch menu update — announcement
*Category: announcement | ID: tc_10*

| Model | Avg | Std Dev | Completeness | Accuracy | Format | Domain | Clarity |
|-------|-----|---------|-------------|----------|--------|--------|---------|
| GPT-5.4 Nano | 9.98 | 0.03 | 10.0 | 10.0 | 10.0 | 9.8 | 10.0 |
| GPT-5.4 Mini | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |
| Gemini 3.1 Flash Lite | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |
| Gemma 4 26B A4B IT | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |
| Gemma 4 31B IT | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |

### Cricket match — sports
*Category: sports | ID: tc_11*

| Model | Avg | Std Dev | Completeness | Accuracy | Format | Domain | Clarity |
|-------|-----|---------|-------------|----------|--------|--------|---------|
| GPT-5.4 Mini | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| Gemma 4 31B IT | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| GPT-5.4 Nano | 9.98 | 0.03 | 10.0 | 10.0 | 10.0 | 9.8 | 10.0 |
| Gemma 4 26B A4B IT | 9.97 | 0.03 | 10.0 | 10.0 | 10.0 | 9.7 | 10.0 |
| Gemini 3.1 Flash Lite | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |

### Early dismissal — schedule_change
*Category: schedule_change | ID: tc_12*

| Model | Avg | Std Dev | Completeness | Accuracy | Format | Domain | Clarity |
|-------|-----|---------|-------------|----------|--------|--------|---------|
| Gemini 3.1 Flash Lite | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| Gemma 4 26B A4B IT | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| Gemma 4 31B IT | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| GPT-5.4 Mini | 9.97 | 0.03 | 10.0 | 10.0 | 10.0 | 9.7 | 10.0 |
| GPT-5.4 Nano | 9.97 | 0.03 | 10.0 | 10.0 | 10.0 | 9.7 | 10.0 |

### School fees — admin
*Category: admin | ID: tc_13*

| Model | Avg | Std Dev | Completeness | Accuracy | Format | Domain | Clarity |
|-------|-----|---------|-------------|----------|--------|--------|---------|
| GPT-5.4 Mini | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| Gemini 3.1 Flash Lite | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| GPT-5.4 Nano | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| Gemma 4 26B A4B IT | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| Gemma 4 31B IT | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |

### Career day — event (not schedule_change)
*Category: event | ID: tc_14*

| Model | Avg | Std Dev | Completeness | Accuracy | Format | Domain | Clarity |
|-------|-----|---------|-------------|----------|--------|--------|---------|
| Gemini 3.1 Flash Lite | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| GPT-5.4 Nano | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| GPT-5.4 Mini | 9.98 | 0.03 | 10.0 | 10.0 | 10.0 | 9.8 | 10.0 |
| Gemma 4 26B A4B IT | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |
| Gemma 4 31B IT | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |

### Exam timetable (homework, not schedule_change)
*Category: homework | ID: tc_15*

| Model | Avg | Std Dev | Completeness | Accuracy | Format | Domain | Clarity |
|-------|-----|---------|-------------|----------|--------|--------|---------|
| GPT-5.4 Mini | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| Gemini 3.1 Flash Lite | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| Gemma 4 26B A4B IT | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| Gemma 4 31B IT | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| GPT-5.4 Nano | 9.93 | 0.03 | 10.0 | 10.0 | 10.0 | 9.3 | 10.0 |

### Photo day — announcement
*Category: announcement | ID: tc_16*

| Model | Avg | Std Dev | Completeness | Accuracy | Format | Domain | Clarity |
|-------|-----|---------|-------------|----------|--------|--------|---------|
| Gemma 4 26B A4B IT | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| GPT-5.4 Mini | 9.98 | 0.03 | 10.0 | 10.0 | 10.0 | 9.8 | 10.0 |
| GPT-5.4 Nano | 9.97 | 0.03 | 10.0 | 10.0 | 10.0 | 9.7 | 10.0 |
| Gemini 3.1 Flash Lite | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |
| Gemma 4 31B IT | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |

### Netball trials — sports
*Category: sports | ID: tc_17*

| Model | Avg | Std Dev | Completeness | Accuracy | Format | Domain | Clarity |
|-------|-----|---------|-------------|----------|--------|--------|---------|
| Gemma 4 26B A4B IT | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| Gemma 4 31B IT | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| GPT-5.4 Nano | 9.97 | 0.03 | 10.0 | 10.0 | 10.0 | 9.7 | 10.0 |
| GPT-5.4 Mini | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |
| Gemini 3.1 Flash Lite | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |

### Code of conduct (admin, not announcement)
*Category: admin | ID: tc_18*

| Model | Avg | Std Dev | Completeness | Accuracy | Format | Domain | Clarity |
|-------|-----|---------|-------------|----------|--------|--------|---------|
| GPT-5.4 Mini | 9.97 | 0.03 | 10.0 | 10.0 | 10.0 | 9.7 | 10.0 |
| Gemini 3.1 Flash Lite | 9.97 | 0.03 | 10.0 | 10.0 | 10.0 | 9.7 | 10.0 |
| GPT-5.4 Nano | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |
| Gemma 4 26B A4B IT | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |
| Gemma 4 31B IT | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |

### Science project — homework
*Category: homework | ID: tc_19*

| Model | Avg | Std Dev | Completeness | Accuracy | Format | Domain | Clarity |
|-------|-----|---------|-------------|----------|--------|--------|---------|
| GPT-5.4 Nano | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| GPT-5.4 Mini | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |
| Gemini 3.1 Flash Lite | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |
| Gemma 4 26B A4B IT | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |
| Gemma 4 31B IT | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |

### Founders day assembly (event, not schedule_change)
*Category: event | ID: tc_20*

| Model | Avg | Std Dev | Completeness | Accuracy | Format | Domain | Clarity |
|-------|-----|---------|-------------|----------|--------|--------|---------|
| Gemma 4 26B A4B IT | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| Gemma 4 31B IT | 9.98 | 0.03 | 10.0 | 10.0 | 10.0 | 9.8 | 10.0 |
| GPT-5.4 Mini | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |
| Gemini 3.1 Flash Lite | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |
| GPT-5.4 Nano | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |

### Water polo results — sports
*Category: sports | ID: tc_21*

| Model | Avg | Std Dev | Completeness | Accuracy | Format | Domain | Clarity |
|-------|-----|---------|-------------|----------|--------|--------|---------|
| GPT-5.4 Mini | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |
| Gemini 3.1 Flash Lite | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |
| GPT-5.4 Nano | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |
| Gemma 4 26B A4B IT | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |
| Gemma 4 31B IT | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |

### Load shedding plan (admin, not announcement)
*Category: admin | ID: tc_22*

| Model | Avg | Std Dev | Completeness | Accuracy | Format | Domain | Clarity |
|-------|-----|---------|-------------|----------|--------|--------|---------|
| GPT-5.4 Mini | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| Gemini 3.1 Flash Lite | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| Gemma 4 26B A4B IT | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| Gemma 4 31B IT | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| GPT-5.4 Nano | 9.93 | 0.03 | 10.0 | 10.0 | 10.0 | 9.3 | 10.0 |

### Period swap — schedule_change
*Category: schedule_change | ID: tc_23*

| Model | Avg | Std Dev | Completeness | Accuracy | Format | Domain | Clarity |
|-------|-----|---------|-------------|----------|--------|--------|---------|
| Gemma 4 26B A4B IT | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| Gemma 4 31B IT | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| GPT-5.4 Mini | 9.97 | 0.03 | 10.0 | 10.0 | 10.0 | 9.7 | 10.0 |
| Gemini 3.1 Flash Lite | 9.97 | 0.03 | 10.0 | 10.0 | 10.0 | 9.7 | 10.0 |
| GPT-5.4 Nano | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |

### Musical auditions — event
*Category: event | ID: tc_24*

| Model | Avg | Std Dev | Completeness | Accuracy | Format | Domain | Clarity |
|-------|-----|---------|-------------|----------|--------|--------|---------|
| Gemini 3.1 Flash Lite | 9.98 | 0.03 | 10.0 | 10.0 | 10.0 | 9.8 | 10.0 |
| GPT-5.4 Mini | 9.97 | 0.03 | 10.0 | 10.0 | 10.0 | 9.7 | 10.0 |
| GPT-5.4 Nano | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |
| Gemma 4 26B A4B IT | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |
| Gemma 4 31B IT | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |

### Bus route delay — schedule_change
*Category: schedule_change | ID: tc_25*

| Model | Avg | Std Dev | Completeness | Accuracy | Format | Domain | Clarity |
|-------|-----|---------|-------------|----------|--------|--------|---------|
| GPT-5.4 Mini | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| GPT-5.4 Nano | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| Gemma 4 26B A4B IT | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| Gemini 3.1 Flash Lite | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |
| Gemma 4 31B IT | 9.95 | 0.0 | 10.0 | 10.0 | 10.0 | 9.5 | 10.0 |

### Chickenpox health notice — announcement (real Saheti content)
*Category: announcement | ID: tc_26*

| Model | Avg | Std Dev | Completeness | Accuracy | Format | Domain | Clarity |
|-------|-----|---------|-------------|----------|--------|--------|---------|
| GPT-5.4 Nano | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| Gemma 4 26B A4B IT | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| Gemma 4 31B IT | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| GPT-5.4 Mini | 9.98 | 0.03 | 10.0 | 10.0 | 10.0 | 9.8 | 10.0 |
| Gemini 3.1 Flash Lite | 9.97 | 0.03 | 10.0 | 10.0 | 10.0 | 9.7 | 10.0 |

### Head lice notice — announcement (real Saheti content)
*Category: announcement | ID: tc_27*

| Model | Avg | Std Dev | Completeness | Accuracy | Format | Domain | Clarity |
|-------|-----|---------|-------------|----------|--------|--------|---------|
| Gemini 3.1 Flash Lite | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| GPT-5.4 Nano | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| Gemma 4 26B A4B IT | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| Gemma 4 31B IT | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 |
| GPT-5.4 Mini | 9.98 | 0.03 | 10.0 | 10.0 | 10.0 | 9.8 | 10.0 |

## Reliability Analysis

Models with high standard deviation across runs may produce inconsistent results.

| Model | Avg Std Dev | Reliability |
|-------|-----------|-------------|
| GPT-5.4 Mini | 0.03 | High |
| Gemini 3.1 Flash Lite | 0.03 | High |
| GPT-5.4 Nano | 0.03 | High |
| Gemma 4 26B A4B IT | 0.03 | High |
| Gemma 4 31B IT | 0.03 | High |

---
*Generated by EvalPulse on 2026-04-16 21:16 UTC*