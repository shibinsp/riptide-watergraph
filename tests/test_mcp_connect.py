"""Track v0.10.0: the gated + allowlisted MCP connect flow.

Fully offline — a ``FakeMcpClient`` stands in for a real stdio MCP server (the server's
``_build_mcp_client`` is monkeypatched), so no subprocess or ``[mcp]`` SDK is needed.
"""

from __future__ import annotations

import importlib

import pytest

from riptide_watergraph.interfaces.tools import ToolSpec
from riptide_watergraph.tools import (
    clear_dynamic_specs,
    default_registry,
    dynamic_specs,
    register_dynamic_spec,
    remove_dynamic_specs,
)

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from riptide_watergraph.mcp import FakeMcpClient, McpToolInfo  # noqa: E402

# One allowlisted server. ``command`` is harmless — the fake client ignores it.
ALLOWLIST = '[{"name":"fs","command":"echo","args":[],"prefix":"fs.","description":"demo fs"}]'


def _fake_client(cfg):
    """A two-tool fake MCP server: one read-only, one mutating."""
    return FakeMcpClient(
        {
            "echo": (
                McpToolInfo(
                    name="echo",
                    description="Echo the provided text",
                    read_only=True,
                    input_schema={
                        "type": "object",
                        "properties": {"text": {"type": "string"}},
                        "required": ["text"],
                        "additionalProperties": False,
                    },
                ),
                lambda text: f"echo: {text}",
            ),
            "remove_file": (
                McpToolInfo(name="remove_file", description="Delete a file (mutating)"),
                lambda **kw: "removed",
            ),
        }
    )


@pytest.fixture
def appmod(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CHECKPOINT_PATH", str(tmp_path / "cp.sqlite"))
    monkeypatch.setenv("RIPTIDE_WATERGRAPH_DISABLE_TRACING", "1")
    monkeypatch.setenv("RIPTIDE_MCP_SERVERS", ALLOWLIST)
    # The package re-exports the FastAPI instance as ``server.app``; import the module.
    m = importlib.import_module("riptide_watergraph.server.app")
    monkeypatch.setattr(m, "_build_mcp_client", _fake_client)
    clear_dynamic_specs()
    m._mcp_connected.clear()
    yield m
    clear_dynamic_specs()
    m._mcp_connected.clear()


@pytest.fixture
def client(appmod):
    return TestClient(appmod.app)


def test_dynamic_store_roundtrip():
    """register/remove/clear flow the dynamic specs into and out of default_registry()."""
    clear_dynamic_specs()
    base = len(default_registry().all_specs())
    register_dynamic_spec(
        ToolSpec(
            name="dyn.ping",
            description="d",
            json_schema={"type": "object", "properties": {}},
            side_effecting=False,
            handler=lambda **kw: "ok",
        )
    )
    assert len(default_registry().all_specs()) == base + 1
    assert "dyn.ping" in [s.name for s in dynamic_specs()]
    assert remove_dynamic_specs(["dyn.ping"]) == ["dyn.ping"]
    assert len(default_registry().all_specs()) == base
    clear_dynamic_specs()


def test_mcp_disabled_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RIPTIDE_MCP_SERVERS", ALLOWLIST)
    monkeypatch.delenv("RIPTIDE_ENABLE_MCP_CONNECT", raising=False)
    m = importlib.import_module("riptide_watergraph.server.app")
    c = TestClient(m.app)
    st = c.get("/api/mcp").json()
    assert st["enabled"] is False
    assert [s["name"] for s in st["servers"]] == ["fs"]
    assert st["servers"][0]["connected"] is False
    # Connecting is refused while the gate is off.
    assert c.post("/api/mcp/connect", json={"name": "fs"}).status_code == 403


def test_connect_registers_tools_then_disconnect_removes(client, monkeypatch):
    monkeypatch.setenv("RIPTIDE_ENABLE_MCP_CONNECT", "1")
    base = client.get("/api/meta").json()["tool_count"]

    r = client.post("/api/mcp/connect", json={"name": "fs"})
    assert r.status_code == 200
    assert set(r.json()["tools"]) == {"fs.echo", "fs.remove_file"}

    meta = client.get("/api/meta").json()
    assert meta["tool_count"] == base + 2
    assert meta["mcp"] == {"enabled": True, "connected": 1}

    # The read-only MCP tool runs through the Tool Runner; the mutating one is refused.
    assert (
        client.post("/api/tools/fs.echo/invoke", json={"arguments": {"text": "hi"}}).json()["result"]
        == "echo: hi"
    )
    assert client.post("/api/tools/fs.remove_file/invoke", json={"arguments": {}}).status_code == 400

    server = client.get("/api/mcp").json()["servers"][0]
    assert server["connected"] is True
    assert set(server["tools"]) == {"fs.echo", "fs.remove_file"}

    d = client.post("/api/mcp/disconnect", json={"name": "fs"}).json()
    assert d["servers"][0]["connected"] is False
    assert client.get("/api/meta").json()["tool_count"] == base


def test_connect_unknown_server_404(client, monkeypatch):
    monkeypatch.setenv("RIPTIDE_ENABLE_MCP_CONNECT", "1")
    assert client.post("/api/mcp/connect", json={"name": "nope"}).status_code == 404
