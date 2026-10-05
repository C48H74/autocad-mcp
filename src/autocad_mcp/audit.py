"""Trilha de auditoria JSONL opcional ([server].audit_log = true): uma linha por chamada de ferramenta.

Registra instante, ferramenta, se altera algo, resultado e código de erro. NÃO registra parâmetros nem dados
do desenho (podem conter informação de projeto). Falha de escrita nunca derruba a ferramenta.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any

from autocad_mcp.config import Config, default_log_dir

log = logging.getLogger("autocad_mcp.audit")
_lock = threading.Lock()


def audit_path(cfg: Config) -> Path:
    return (cfg.log_dir or default_log_dir()) / "audit.jsonl"


def record(cfg: Config, tool: str, mutates: bool, result: dict[str, Any]) -> None:
    if not cfg.audit_log:
        return
    err = result.get("error") or {}
    line = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "tool": tool, "mutates": mutates,
            "ok": bool(result.get("ok")), "error_code": err.get("code"), "read_only": cfg.read_only}
    try:
        path = audit_path(cfg)
        path.parent.mkdir(parents=True, exist_ok=True)
        with _lock, path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")
    except OSError as exc:
        log.warning("Falha ao gravar auditoria: %s", exc)
