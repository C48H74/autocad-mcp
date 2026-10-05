"""Fixtures: contexto com AutoCAD falso + helper para chamar ferramentas via FastMCP (schema real)."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from autocad_mcp.config import Config
from autocad_mcp.connection import AutoCadConnection
from autocad_mcp.context import AppContext, set_context
from autocad_mcp.server import build_server
from tests.fake_autocad import FakeApp, FakeDoc


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    """Retries de 'AutoCAD ocupado' não devem atrasar os testes."""
    monkeypatch.setattr("autocad_mcp.connection._sleep", lambda s: None)


@pytest.fixture
def cfg() -> Config:
    return Config(default_limit=50, max_limit=500, com_timeout_s=10.0)


@pytest.fixture
def app() -> FakeApp:
    return FakeApp([FakeDoc("SUPORTES-01.dwg", units=4)])


@pytest.fixture
def doc(app: FakeApp) -> FakeDoc:
    return app.docs[0]


@pytest.fixture
def ctx(cfg: Config, app: FakeApp):
    conn = AutoCadConnection(cfg, app_factory=lambda _cfg: app)
    context = AppContext(cfg, conn)
    set_context(context)
    yield context
    set_context(None)


@pytest.fixture
def mcp_server(ctx):
    return build_server()


@pytest.fixture
def call(mcp_server):
    """call('tool', param=...) -> dict do envelope {ok, data, warnings, error}."""

    def _call(tool: str, /, **kwargs: Any) -> dict[str, Any]:
        result = asyncio.run(mcp_server.call_tool(tool, kwargs))
        content = result[0] if isinstance(result, tuple) else result
        if isinstance(result, dict):
            return result
        texts = [c.text for c in content if getattr(c, "type", "") == "text"]
        return json.loads(texts[0])

    return _call
