"""Multimodal perception v0.20.0: image content on Message, vision_chat, /v1 vision, CLI."""

from __future__ import annotations

import asyncio
import importlib

import pytest

from riptide_watergraph.cli import main
from riptide_watergraph.gateway import DemoGateway
from riptide_watergraph.interfaces.gateway import Message
from riptide_watergraph.service import image_to_data_uri, vision_chat

_IMG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="


# --------------------------- Message multimodal rendering ---------------------------

def test_message_to_dict_multimodal():
    parts = Message(role="user", content="describe", images=[_IMG]).to_dict()["content"]
    assert parts[0] == {"type": "text", "text": "describe"}
    assert parts[1]["type"] == "image_url" and parts[1]["image_url"]["url"] == _IMG
    # images without text -> only the image part
    only = Message(role="user", images=[_IMG]).to_dict()["content"]
    assert len(only) == 1 and only[0]["type"] == "image_url"
    # no images -> plain string content (unchanged)
    assert Message(role="user", content="hi").to_dict()["content"] == "hi"


# --------------------------- offline vision gateway ---------------------------

def test_demo_gateway_describes_images():
    res = asyncio.run(DemoGateway().complete(
        model="demo",
        messages=[Message(role="user", content="what is this?", images=[_IMG, _IMG])]))
    assert "2 image(s)" in (res.content or "")


# --------------------------- service helpers ---------------------------

@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RIPTIDE_WATERGRAPH_DISABLE_TRACING", "1")
    return tmp_path


def test_image_to_data_uri(tmp_path):
    img = tmp_path / "pic.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    uri = image_to_data_uri(str(img))
    assert uri.startswith("data:image/png;base64,")


def test_vision_chat_offline(env):
    answer = vision_chat("what is in this image?", [_IMG], offline=True)
    assert "image(s)" in answer


# --------------------------- /v1 vision ---------------------------

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CHECKPOINT_PATH", str(tmp_path / "cp.sqlite"))
    monkeypatch.setenv("RIPTIDE_WATERGRAPH_DISABLE_TRACING", "1")
    pytest.importorskip("fastapi")
    from riptide_watergraph.server import app
    from fastapi.testclient import TestClient
    return TestClient(app)


@pytest.fixture
def appmod():
    return importlib.import_module("riptide_watergraph.server.app")


def test_content_text_images_helper(appmod):
    f = appmod._content_text_images
    assert f("plain") == ("plain", [])
    text, imgs = f([{"type": "text", "text": "hi"},
                    {"type": "image_url", "image_url": {"url": "u1"}},
                    {"type": "image_url", "image_url": {}},   # no url -> skipped
                    {"type": "other"}])                       # unknown -> skipped
    assert text == "hi" and imgs == ["u1"]


def test_v1_vision_completion(client):
    body = client.post("/v1/chat/completions", json={
        "model": "demo", "offline": True,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": "what is in this picture?"},
            {"type": "image_url", "image_url": {"url": _IMG}},
        ]}],
    }).json()
    assert body["object"] == "chat.completion"
    assert "image(s)" in body["choices"][0]["message"]["content"]


def test_v1_vision_budget_402(client, appmod, monkeypatch):
    from riptide_watergraph.observability.cost import BudgetExceeded

    def _budget(*a, **k):
        raise BudgetExceeded("t", 1.0, 0.5)
    monkeypatch.setattr(appmod, "vision_chat", _budget)
    r = client.post("/v1/chat/completions", json={
        "offline": True,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": "x"},
            {"type": "image_url", "image_url": {"url": _IMG}}]}]})
    assert r.status_code == 402


# --------------------------- CLI ---------------------------

def test_cli_see_offline(env, tmp_path, capsys):
    img = tmp_path / "pic.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    code = main(["see", "what do you see?", "--image", str(img),
                 "--image", "https://example.com/x.png", "--offline"])
    assert code == 0
    out = capsys.readouterr().out
    assert "ANSWER" in out and "images:   2" in out
