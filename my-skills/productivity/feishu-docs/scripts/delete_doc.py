import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from feishu_common import get_tenant_token


def delete_doc(doc_token):
    token = get_tenant_token()
    url = f"https://open.feishu.cn/open-apis/drive/v1/files/{doc_token}?type=docx"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"}, method="DELETE")
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"Delete successful for {doc_token}:", resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.read().decode()}")
        sys.exit(1)
    except Exception as e:
        print(f"Failed to delete {doc_token}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python delete_doc.py <doc_token>")
        sys.exit(1)
    delete_doc(sys.argv[1])
