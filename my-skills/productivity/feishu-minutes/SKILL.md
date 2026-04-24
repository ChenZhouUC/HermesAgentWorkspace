---
name: feishu-minutes
description: Guide for reading and extracting content from Feishu/Lark Minutes (飞书妙记) via OpenAPI.
---

# Feishu Minutes (飞书妙记) Reader

This skill provides the standard operating procedure for extracting full transcripts and meeting notes from Feishu/Lark Minutes URLs.

## 🎯 Trigger Conditions

- The user provides a Feishu Minutes link (e.g., `https://*.feishu.cn/minutes/obcn...`) and asks to read, summarize, or extract the meeting content.
- The user asks to get the transcript of a recorded Feishu meeting.

## 📋 Prerequisites & Permissions

To use the OpenAPI, the Feishu App configured in `~/.hermes/.env` (`FEISHU_APP_ID` & `FEISHU_APP_SECRET`) **MUST** have the following permissions granted and **PUBLISHED** in the Feishu Developer Console:

- `minutes:minutes`
- `minutes:minutes:readonly`
- `minutes:minutes.basic:read`

If these are missing, the API will return HTTP 400 with `code: 99991672` (Access denied).

## 🛠️ Step-by-Step Implementation

### 1. Extract the Minute Token

The token is the unique identifier at the end of the Minutes URL.
URL: `https://whales.feishu.cn/minutes/obcn8ktpq4eh85jp821mib7g`
Token: `obcn8ktpq4eh85jp821mib7g` (typically 24 characters).

### 2. Python Extraction Script

Use `execute_code` with the following standard script to fetch the transcript.

```python
import os
import requests
from dotenv import load_dotenv

# 1. Load credentials
load_dotenv(os.path.expanduser('~/.hermes/.env'))
APP_ID = os.getenv('FEISHU_APP_ID')
APP_SECRET = os.getenv('FEISHU_APP_SECRET')

if not APP_ID or not APP_SECRET:
    print("Error: Missing FEISHU_APP_ID or FEISHU_APP_SECRET.")
    exit(1)

# 2. Get Tenant Access Token (TAT)
token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
tat_res = requests.post(token_url, json={"app_id": APP_ID, "app_secret": APP_SECRET}).json()
tat = tat_res.get("tenant_access_token")

if not tat:
    print(f"Failed to get TAT: {tat_res}")
    exit(1)

# 3. Fetch Transcript (Returns Plain Text, NOT JSON)
minute_token = "YOUR_MINUTE_TOKEN_HERE"
headers = {"Authorization": f"Bearer {tat}"}
transcript_url = f"https://open.feishu.cn/open-apis/minutes/v1/minutes/{minute_token}/transcript"

res = requests.get(transcript_url, headers=headers)
res.encoding = 'utf-8' # CRITICAL: Fixes Chinese character encoding

if res.status_code == 200:
    transcript_text = res.text
    print(f"Successfully retrieved {len(transcript_text)} characters.")
    print("--- Snippet ---")
    print(transcript_text[:1000])
else:
    print(f"API Error {res.status_code}: {res.text}")
```

## ⚠️ Critical Pitfalls & Gotchas

1. **The `/transcript` endpoint returns PLAIN TEXT, not JSON!**
   - **Do NOT** call `res.json()` on the response from the transcript endpoint. It will throw a `json.decoder.JSONDecodeError: Extra data`.
   - Always use `res.text`. The returned format looks like: `2026-04-24 15:32:12 CST|21分钟 48秒\n\n关键词:\n设备、链路... \n\nSpeaker Name\n[Dialogue content]`
2. **Missing `utf-8` Encoding:**
   - The `requests` library might default to `ISO-8859-1` for plain text responses, causing Chinese characters to become gibberish. Always explicitly set `res.encoding = 'utf-8'` before reading `res.text`.
3. **Fallback Strategy (Browser Injection):**
   - If the API fails due to unapproved permissions (`99991672`) and the user cannot grant them immediately, fallback to using `browser_navigate` to open the URL, click "Show More", and extract text via `browser_console` using JavaScript DOM selection. _Warning: The browser UI may truncate transcripts with a "Quota Reached" warning, so the API is always preferred._
