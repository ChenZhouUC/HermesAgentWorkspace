"""Download a Feishu file attachment (/file/TOKEN) to ~/.hermes/tmp and print its path.

Links look like ``https://domain.feishu.cn/file/TOKEN`` — typically .xlsx/.docx/.pdf
uploaded into chat. These are NOT docs; feishu_doc_read won't read them. After
downloading, Hermes's ``read_file`` tool auto-extracts .docx/.xlsx to text
(see references/file-attachment-download.md).

The destination ~/.hermes/tmp is inside the group sandbox's read roots, so the
agent can ``read_file`` the result directly.

Usage:
  python download_feishu_file.py <file_url_or_token> [dest_dir]
"""

import json
import mimetypes
import os
import sys
import urllib.parse
import urllib.request

import feishu_common as fc

DEFAULT_DEST = "~/.hermes/tmp"
_EXT_BY_CTYPE = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/pdf": ".pdf",
    "text/csv": ".csv",
    "text/plain": ".txt",
}


def extract_file_token(url_or_token):
    s = (url_or_token or "").strip()
    if "/file/" in s:
        s = s.split("/file/", 1)[1]
    return s.split("?", 1)[0].split("#", 1)[0].strip("/")


def _filename_from(content_disposition, content_type, file_token):
    # Prefer the server-provided filename (handles RFC 5987 filename*=UTF-8''...).
    cd = content_disposition or ""
    for marker in ("filename*=UTF-8''", "filename*=utf-8''"):
        if marker in cd:
            raw = cd.split(marker, 1)[1].split(";", 1)[0].strip().strip('"')
            name = urllib.parse.unquote(raw)
            if name:
                return name
    if "filename=" in cd:
        name = cd.split("filename=", 1)[1].split(";", 1)[0].strip().strip('"')
        if name:
            return name
    ext = _EXT_BY_CTYPE.get((content_type or "").split(";", 1)[0].strip())
    if not ext:
        ext = mimetypes.guess_extension((content_type or "").split(";", 1)[0].strip() or "") or ".bin"
    return f"feishu_{file_token}{ext}"


def download_file(url_or_token, dest_dir=DEFAULT_DEST):
    file_token = extract_file_token(url_or_token)
    token = fc.get_tenant_token()
    url = f"{fc.API}/drive/v1/files/{file_token}/download"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=120) as resp:  # urllib follows 3xx redirects
        data = resp.read()
        ctype = resp.headers.get("Content-Type", "")
        fname = _filename_from(resp.headers.get("Content-Disposition", ""), ctype, file_token)
    # Some failures come back as HTTP 200 + a JSON error envelope, not binary.
    if ctype.split(";", 1)[0].strip() == "application/json":
        try:
            err = json.loads(data)
            if isinstance(err, dict) and err.get("code"):
                raise RuntimeError(f"Feishu download error: code={err.get('code')} msg={err.get('msg')!r}")
        except json.JSONDecodeError:
            pass
    dest_dir = os.path.expanduser(dest_dir)
    os.makedirs(dest_dir, exist_ok=True)
    path = os.path.join(dest_dir, os.path.basename(fname))
    with open(path, "wb") as f:
        f.write(data)
    return path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python download_feishu_file.py <file_url_or_token> [dest_dir]")
        sys.exit(1)
    dest = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_DEST
    out_path = download_file(sys.argv[1], dest)
    print(out_path)
    print(f'\n下载完成。用 read_file 抽取内容(.docx/.xlsx 自动转文本):\n  read_file("{out_path}")')
