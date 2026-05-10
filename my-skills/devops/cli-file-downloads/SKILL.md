---
name: cli-file-downloads
description: Patterns and workarounds for downloading large or slow files via CLI within the agent's constraints (timeout handling, resuming, bypassing blocks).
category: devops
---

# CLI File Downloads

When downloading files using `curl` or `wget`, the agent's foreground terminal environment has a strict execution timeout (typically 180 seconds). Slow servers, severe rate-limiting, or large files will cause the command to time out and abort midway.

## Core Workflow for Large/Slow Downloads

1. **Probe First (Optional):** Run a quick foreground `curl -I` or a fast download attempt to check if the server is responsive, verify headers, and get the expected file size.
2. **Background the Task:** If the file is large or the server is heavily throttling (e.g., 60 KB/s), **never** leave it in the foreground. Invoke the `terminal` tool with `background=true` and `notify_on_complete=true` so the agent isn't blocked while the download runs.
3. **Resume Partials:** If a foreground download timed out and left a partial file on disk, **always resume it** instead of starting over.
   - **`curl`:** Use the `-C -` flag (continue).
     **CRITICAL PITFALL**: You MUST combine `-C -` with `-f` (`--fail`). If the server returns a 50x/40x error page during a resume attempt, `curl` will normally append that HTML error page to your binary file, silently corrupting it. `-f` prevents this. Example: `curl -f -C - -L -o myfile.pdf "<URL>"`
   - **`wget`:** Use the `-c` flag.

## Highly Unstable Connections (The Loop Strategy)

If a server frequently drops connections, throttles aggressively, or returns intermittent 503s (like Libgen CDNs), a single background `curl` command will likely hit an error and exit before finishing.

Instead of manual retries, use the provided robust loop script. It checks `curl` exit codes, correctly handles 503s vs partial disconnects, and loops persistently.

- **Execute via the `terminal` tool** with `background=true`, `notify_on_complete=true`, and `command="/Users/chenzhou/.hermes/my-skills/devops/cli-file-downloads/scripts/robust_curl_resume.sh \"<URL>\" \"<FILE>\" \"<REFERER>\""`.

## Anti-Scraping / CDN Bypasses

When downloading from strict or overloaded file-hosts (e.g., Libgen CDNs, academic archives, direct IP links):

- **User-Agent:** Many servers return 503 or 403 to default `curl` agents. Always spoof a standard browser:
  `-A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"`
- **Referer:** If the direct download link fails, it often requires the origin page as a referer. Use `-e "<referer_url>"` in `curl`.
- **Redirects:** Always include `-L` in `curl` to follow `301/302` redirects, which are extremely common in CDNs.
- **Shadow Libraries & Cloudflare Blocks (Anna's Archive, Libgen):**
  - **USE THE `libgen-downloader` SKILL:** Instead of manual curl loops, load the `libgen-downloader` skill which automates CID extraction and proxy routing for Libgen.

## Pitfalls & Edge Cases

- **The "Fake Progress" / Dead Mirror Trap:** When dealing with extremely hostile or overloaded mirrors (like Libgen's `cdn*.booksdl.lc` nodes), the server might start returning a `200 OK` but instantly stall with 0 bytes transferred, or repeatedly drop the connection after only a few KB. If the robust loop script is stuck in an endless cycle of reconnecting without making meaningful progress, **do not keep looping**. Abandon the mirror and advise the user to switch to a healthier node (e.g., IPFS or Cloudflare mirrors).
- **Silent File Corruption:** Never forget `-f` when using `-C -`. Without `-f`, a 503 error page will be seamlessly appended to a binary file by `curl`, breaking the file.
- **Truncated PDFs & Corruption:** If a PDF download persistently fails near the very end (e.g., 95%+ complete), **DO NOT assume the file is usable**. While some lenient tools can render partial PDFs, strict readers will refuse to open them because the `xref` table and `%%EOF` marker are located at the absolute end of the file. If the file cannot be opened, you must either:
  1. Switch to a completely different mirror or protocol (e.g., IPFS, Cloudflare, or a different CDN node) to fetch the complete file.
  2. Attempt to repair the broken PDF using a tool like `qpdf --show-npages` or `mutool clean` if the user is willing to accept a potentially incomplete repair. Never push a broken file to the user as "good enough" without verifying it can actually be opened.
