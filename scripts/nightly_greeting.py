import json
import re
import sys
from pathlib import Path

HERMES_HOME = Path.home() / ".hermes"
FEISHU_DOCS_SCRIPTS = HERMES_HOME / "my-skills/productivity/feishu-docs/scripts"
FEISHU_GROUPS_SKILL = HERMES_HOME / "my-skills/productivity/feishu-groups/SKILL.md"

sys.path.insert(0, str(FEISHU_DOCS_SCRIPTS))
import feishu_common

CHAT_ID_RE = re.compile(r"`(oc_[A-Za-z0-9_]+)`")

MESSAGE = "大家好，琛哥的「木马牛」下班了。牛马也是要休息的，大家没啥事儿也都早点休息，晚安！如果有什么要紧的不要紧的事儿，尽量都天亮了再说，祝大家好梦，各位晚安！[天色已晚] （其实我在床上玩手机，没睡着的话还是会回你们的。但你们千万别告诉我老板，琛哥是真的会拉我起来干活的[新月脸]）"


def load_group_ids(path=FEISHU_GROUPS_SKILL):
    """Read chat_ids from the Known Groups table in the feishu-groups skill."""
    in_known_groups = False
    group_ids = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            in_known_groups = line.strip() == "## Known Groups"
            continue
        if not in_known_groups or not line.startswith("|"):
            continue
        match = CHAT_ID_RE.search(line)
        if match and match.group(1) not in group_ids:
            group_ids.append(match.group(1))
    if not group_ids:
        raise RuntimeError(f"No Feishu group chat_ids found in {path}")
    return group_ids


def send_message(token, group_id, text):
    url = f"{feishu_common.API}/im/v1/messages?receive_id_type=chat_id"
    payload = {
        "receive_id": group_id,
        "msg_type": "text",
        "content": json.dumps({"text": text}, ensure_ascii=False),
    }
    res = feishu_common.do_req(token, url, method="POST", payload=payload)
    if res.get("code", 0):
        raise RuntimeError(f"Failed to send to {group_id}: {res}")
    print(f"Sent to {group_id}: {res}")


def main():
    token = feishu_common.get_tenant_token()
    for group_id in load_group_ids():
        send_message(token, group_id, MESSAGE)


if __name__ == "__main__":
    main()
