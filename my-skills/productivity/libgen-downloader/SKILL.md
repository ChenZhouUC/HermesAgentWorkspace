---
name: libgen-downloader
description: Robustly download books from Libgen/Anna's Archive using IPFS CID extraction and proxy fallback to bypass 503 errors and TLS blocking.
category: productivity
---

# Libgen/Anna's Archive Robust Downloader (GenFetch)

**WHEN TO USE:**
Use this skill when the user provides a Libgen MD5, an `edition.php` URL, or an Anna's Archive link and asks to download the book. Standard `curl` or `requests` will frequently fail due to Cloudflare protection, 503 Rate Limits, or TLS/SNI blocking by the ISP.

**CORE STRATEGY:**
Do NOT attempt to download the `.pdf` or `.epub` file directly via HTTP from Libgen mirrors. Instead, extract the **IPFS CID (Content Identifier)** and download the file from a public IPFS gateway.

## Step-by-Step Execution

### 1. Extract the IPFS CID

You must first obtain the unique IPFS hash (`bafy...` or `Qm...`) for the book.

- **If the user provides an MD5:** Use `web_search` or API endpoints (via proxy if necessary) to query the MD5 and find its corresponding CID.
- **If the user provides a Libgen URL (e.g., `libgen.bz/edition.php?id=...`):**
  Use Python (`requests`) with the user's local proxy (e.g., `127.0.0.1:7897`) to fetch the HTML content of the page.
  Use regex to extract the CID:
  ```python
  import re
  # Look for the CID in the href links
  match = re.search(r'ipfs/([a-zA-Z0-9]+)', html_content)
  cid = match.group(1) if match else None
  ```

### 2. Download via Public IPFS Gateway

Once you have the CID, use `curl` via the terminal tool to download the file from a reliable public gateway.

**Critical `curl` parameters:**

- `-x http://127.0.0.1:7897` (or the user's specified proxy) - _Crucial for bypassing local SNI blocking._
- `-sL` (Silent + Follow Redirects).
- `-f` (Fail silently on server errors) - _Prevents writing 503 HTML error pages into the binary file._

**Execution Command:**

```bash
# Example using ipfs.io. If it fails, try cloudflare-ipfs.com/ipfs/ or dweb.link/ipfs/
curl -sL -f -x http://127.0.0.1:7897 "https://ipfs.io/ipfs/<CID>" -o ~/.hermes/tmp/<filename>
```

_Note: Always save to `~/.hermes/tmp/` unless the user specifies otherwise. If the file is large (>50MB), consider running it in the background (`background=true`, `notify_on_complete=true`)._

### 3. Verification

After the download completes, verify the file size and type:

```bash
ls -lh ~/.hermes/tmp/<filename>
file ~/.hermes/tmp/<filename>
```

If `file` reports HTML document text, the download failed and captured an error page. Delete it and retry with a different IPFS gateway.

## Pitfalls & Troubleshooting

- **TLS/EOF Errors:** If your Python script encounters `[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol`, the IDC node or GFW is blocking the domain. You MUST use the user's local proxy (`proxies={'http': 'http://127.0.0.1:7897', 'https': 'http://127.0.0.1:7897'}`) for all HTTP requests.
- **Proxy Not Working:** If the proxy connects but still throws SSLError on Libgen domains, the proxy server itself is blocking pirate sites (Fake Wall). Fallback to searching Google Cache or Anna's Archive for the CID, or ask the user to extract the CID from their browser manually.
- **Never use `libgen-api`:** Do not install or use the `libgen-api` Python package. It hardcodes `libgen.is`, which will crash if the domain is blocked. Always write custom request logic.
