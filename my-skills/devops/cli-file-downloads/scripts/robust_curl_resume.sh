#!/bin/bash
# robust_curl_resume.sh
# Safely downloads/resumes a file from flaky servers (e.g., CDNs returning intermittent 503s).
# Usage: ./robust_curl_resume.sh "<URL>" "<OUTPUT_FILE>" [REFERER]

URL="$1"
FILE="$2"
REF="${3:-}"

if [ -z "$URL" ] || [ -z "$FILE" ]; then
    echo "Usage: $0 <URL> <OUTPUT_FILE> [REFERER]"
    exit 1
fi

UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"

# Build referer arg if provided
REF_ARG=""
if [ -n "$REF" ]; then
    REF_ARG="-e $REF"
fi

echo "Starting robust download for $FILE..."
while true; do
    # -f: Fail fast on HTTP errors (CRITICAL for resuming to avoid appending HTML to binary)
    # -C -: Resume broken downloads
    # --connect-timeout 15: Don't hang forever on dead IPs
    # --max-time 600: Refresh connection every 10 mins max to avoid silent freezes
    curl -f -C - -A "$UA" $REF_ARG -L --connect-timeout 15 --max-time 600 -o "$FILE" "$URL"
    EXIT_CODE=$?

    if [ $EXIT_CODE -eq 0 ]; then
        echo "Success: Download complete."
        break
    elif [ $EXIT_CODE -eq 33 ]; then
        echo "Range error (Code 33): Usually means the file is already fully downloaded."
        break
    elif [ $EXIT_CODE -eq 22 ]; then
        echo "HTTP Error (Code 22): Probably 503/403. Retrying in 10s..."
    elif [ $EXIT_CODE -eq 18 ]; then
        echo "Partial File (Code 18): Connection dropped midway. Resuming in 5s..."
        sleep 5
        continue
    else
        echo "Other Error (Code $EXIT_CODE). Retrying in 10s..."
    fi
    sleep 10
done
