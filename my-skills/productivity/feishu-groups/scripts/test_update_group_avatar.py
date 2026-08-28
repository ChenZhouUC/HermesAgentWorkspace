from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

_SCRIPT = Path(__file__).with_name("update_group_avatar.py")
_SPEC = importlib.util.spec_from_file_location("feishu_group_avatar_helper", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
avatar = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = avatar
_SPEC.loader.exec_module(avatar)


def _write_home(tmp_path: Path) -> tuple[Path, Path]:
    home = tmp_path / ".hermes"
    home.mkdir()
    (home / "groups.yaml").write_text(
        """groups:
  - chat_id: oc_1234567890abcdef1234567890abcdef
    name: Example Group
    aliases: [Example]
""",
        encoding="utf-8",
    )
    image = home / "cache" / "images" / "avatar.png"
    image.parent.mkdir(parents=True)
    Image.new("RGB", (512, 256), "#336699").save(image)
    return home, image


class _Response:
    def __init__(self, *, data=None, code=0, msg="ok"):
        self.data = data
        self.code = code
        self.msg = msg

    def success(self):
        return self.code == 0


class _FakeImageApi:
    def __init__(self):
        self.uploaded = False

    def create(self, request):
        assert request.request_body.image_type == "avatar"
        assert request.request_body.image.read(8) == b"\x89PNG\r\n\x1a\n"
        self.uploaded = True
        return _Response(data=SimpleNamespace(image_key="secret-image-key"))


class _FakeChatApi:
    def __init__(self):
        self.reads = 0
        self.updated = False

    def get(self, request):
        assert request.chat_id == "oc_1234567890abcdef1234567890abcdef"
        self.reads += 1
        return _Response(
            data=SimpleNamespace(
                name="Example Group",
                avatar="old-avatar" if self.reads == 1 else "new-avatar",
            )
        )

    def update(self, request):
        assert request.chat_id == "oc_1234567890abcdef1234567890abcdef"
        assert request.request_body.avatar == "secret-image-key"
        self.updated = True
        return _Response()


class _FakeClient:
    def __init__(self):
        self.image_api = _FakeImageApi()
        self.chat_api = _FakeChatApi()
        self.im = SimpleNamespace(v1=SimpleNamespace(image=self.image_api, chat=self.chat_api))


def test_dry_run_resolves_alias_without_credentials(tmp_path, monkeypatch):
    home, image = _write_home(tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.delenv("FEISHU_APP_ID", raising=False)
    monkeypatch.delenv("FEISHU_APP_SECRET", raising=False)

    result = avatar.run(["--group", "Example", "--image", str(image), "--dry-run"])

    assert result == {
        "success": True,
        "dry_run": True,
        "group": "Example Group",
        "format": "PNG",
        "width": 512,
        "height": 256,
        "size_bytes": image.stat().st_size,
    }


def test_mutation_requires_exact_chat_id_confirmation(tmp_path, monkeypatch):
    home, image = _write_home(tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(home))

    with pytest.raises(avatar.AvatarUpdateError, match="confirm-chat-id"):
        avatar.run(["--group", "Example Group", "--image", str(image)])


def test_update_uses_official_sdk_shapes_and_hides_private_values(tmp_path, monkeypatch):
    home, image = _write_home(tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(home))
    client = _FakeClient()

    result = avatar.run(
        [
            "--group",
            "Example Group",
            "--image",
            str(image),
            "--confirm-chat-id",
            "oc_1234567890abcdef1234567890abcdef",
        ],
        client=client,
    )

    assert client.image_api.uploaded is True
    assert client.chat_api.updated is True
    assert result["success"] is True
    assert result["readback_changed"] is True
    rendered = json.dumps(result)
    assert "secret-image-key" not in rendered
    assert str(image) not in rendered
    assert "oc_1234567890abcdef1234567890abcdef" not in rendered


def test_rejects_symlink_and_oversized_dimensions(tmp_path):
    _, image = _write_home(tmp_path)
    link = tmp_path / "avatar-link.png"
    link.symlink_to(image)
    with pytest.raises(avatar.AvatarUpdateError, match="symbolic link"):
        avatar._validate_image(str(link))

    oversized = tmp_path / "oversized.png"
    Image.new("RGB", (4097, 1), "white").save(oversized)
    with pytest.raises(avatar.AvatarUpdateError, match="4096"):
        avatar._validate_image(str(oversized))


def test_rejects_unconfigured_group(tmp_path):
    home, _ = _write_home(tmp_path)
    with pytest.raises(avatar.AvatarUpdateError, match="not present"):
        avatar._resolve_group("Unknown", home / "groups.yaml")


def test_rejects_image_outside_hermes_media_roots(tmp_path, monkeypatch):
    home, _ = _write_home(tmp_path)
    outside = tmp_path / "outside.png"
    Image.new("RGB", (32, 32), "white").save(outside)
    monkeypatch.setenv("HERMES_HOME", str(home))

    with pytest.raises(avatar.AvatarUpdateError, match="outside the trusted"):
        avatar.run(["--group", "Example Group", "--image", str(outside), "--dry-run"])


def test_credentials_do_not_mix_partial_environment_with_dotenv(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "FEISHU_APP_ID=file-id\nFEISHU_APP_SECRET=file-secret\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("FEISHU_APP_ID", "environment-id")
    monkeypatch.delenv("FEISHU_APP_SECRET", raising=False)

    with pytest.raises(avatar.AvatarUpdateError, match="configured together"):
        avatar._credentials(env_file)
