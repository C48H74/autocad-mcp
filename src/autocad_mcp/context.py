"""Contexto global do servidor (config + conexão). Substituível nos testes."""

from __future__ import annotations

import threading
from dataclasses import dataclass

from autocad_mcp.config import Config, load_config
from autocad_mcp.connection import AutoCadConnection


@dataclass
class AppContext:
    cfg: Config
    conn: AutoCadConnection


_lock = threading.Lock()
_ctx: AppContext | None = None


def get_context() -> AppContext:
    global _ctx
    with _lock:
        if _ctx is None:
            cfg = load_config()
            _ctx = AppContext(cfg, AutoCadConnection(cfg))
        return _ctx


def set_context(ctx: AppContext | None) -> None:
    """Injeta (ou limpa) o contexto — usado por main() e pelos testes."""
    global _ctx
    with _lock:
        if _ctx is not None and ctx is not _ctx:
            _ctx.conn.close()
        _ctx = ctx
