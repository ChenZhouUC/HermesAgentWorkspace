---
name: hacker-news
description: Fetch the latest tech and AI news from Hacker News using the official Firebase API. Bypasses browser anti-bot captchas.
category: feeds
tags: [news, tech, ai, research, api]
---

# Hacker News API Fetcher

## Trigger

Use this skill when the user asks for the latest AI news, tech news, or recent developments, especially if standard `browser_navigate` or `web_search` tools fail due to CAPTCHAs, stealth warnings, or Cloudflare blocks (e.g., DuckDuckGo Lite blocking automated browsers).

## Approach

Instead of scraping search engine web pages which are prone to bot detection, use the `execute_code` tool to query the Hacker News Firebase REST API directly. It is fast, requires no API keys, and returns clean, structured JSON data.

## Implementation Script

Run the following Python script via `execute_code` to fetch and filter news. Adjust the `keywords` list based on what the user is looking for (or remove the filter entirely for general news).

```python
import urllib.request
import json
import ssl
import re

# Bypass SSL verification issues if they occur
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# 1. Get Top Stories IDs
req = urllib.request.Request("https://hacker-news.firebaseio.com/v0/topstories.json")
try:
    with urllib.request.urlopen(req, context=ctx) as response:
        # Fetch top 150 to ensure enough pool for filtering
        top_ids = json.loads(response.read().decode())[:150]
except Exception as e:
    print(f"Error fetching top stories: {e}")
    exit(1)

# 2. Define keywords (Modify as needed based on the user's prompt)
keywords = [r'\bai\b', 'llm', 'gpt', 'claude', 'gemini', 'openai', 'anthropic', 'deepseek', 'llama']
pattern = re.compile('|'.join(keywords), re.IGNORECASE)

# 3. Fetch individual items and filter
results = []
for item_id in top_ids:
    url = f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, context=ctx) as response:
            item = json.loads(response.read().decode())
            title = item.get('title', '')

            # If looking for general news, skip the if-statement
            if pattern.search(title):
                results.append(item)
                if len(results) >= 8: # Limit results to save time
                    break
    except Exception:
        continue

if not results:
    print("No matching news found.")
else:
    for r in results:
        print(f"- {r.get('title', '')}\n  {r.get('url', 'No URL')}\n")
```

## Pitfalls & Guidelines

- **Rate/Time Limit**: Always limit the initial `topstories.json` slice (e.g., `[:150]`) and `break` the loop once you have ~8 results. Requesting all 500 items sequentially will take too long and timeout.
- **Error Handling**: Wrap the individual item fetches in `try/except` blocks to ignore deleted or failed items and keep the loop running.
- **Regex Boundaries**: When matching short acronyms like "AI", use word boundaries (`r'\bai\b'`) so you don't match words like "said" or "aim".
