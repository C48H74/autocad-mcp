"""Decorator das ferramentas: executa o corpo na thread COM e monta o envelope {ok, data, warnings, error}."""

from __future__ import annotations

import asyncio
import functools
import inspect
import logging
import threading
import traceback
import typing
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from autocad_mcp import audit
from autocad_mcp._com import com_error
from autocad_mcp.context import get_context
from autocad_mcp.errors import AutoCadMcpError, OperationBlockedError, map_com_error
from autocad_mcp.models import ErrorInfo, ToolResult

log = logging.getLogger("autocad_mcp.tools")


def build_error(exc: BaseException) -> ErrorInfo:
    if isinstance(exc, AutoCadMcpError):
        return ErrorInfo(code=exc.code, message=str(exc), details=exc.details)
    if isinstance(exc, ValidationError):
        return ErrorInfo(code="validation_error", message="Parâmetros inválidos", details=exc.errors(include_url=False, include_context=False))
    if isinstance(exc, com_error):
        mapped = map_com_error(exc)
        return ErrorInfo(code=mapped.code if type(mapped) is not AutoCadMcpError else "com_error", message=str(mapped))
    log.error("Erro inesperado: %s", "".join(traceback.format_exception(exc)))
    return ErrorInfo(code="internal_error", message=f"{type(exc).__name__}: {exc}")


def execute(fn: Callable[..., Any], args: tuple, kwargs: dict, *, needs_doc: bool, coords: bool, mutates: bool = True) -> dict[str, Any]:
    """Executa `fn(session, *args, **kwargs)` na thread COM e devolve o envelope como dict."""
    ctx = get_context()
    holder: dict[str, Any] = {}

    def job(session: Any) -> Any:
        holder["session"] = session
        data = fn(session, *args, **kwargs)
        if coords and isinstance(data, dict) and session.has_document:
            data.setdefault("units", session.units_name)
            data.setdefault("units_code", session.units_code)
        return data

    try:
        if ctx.cfg.read_only and mutates:
            raise OperationBlockedError("Modo somente leitura: ferramenta bloqueada, inclusive dry_run/confirm.")
        data = ctx.conn.run(job, needs_doc=needs_doc)
        session = holder.get("session")
        result = ToolResult(ok=True, data=data, warnings=list(session.warnings) if session else []).to_dict()
    except BaseException as exc:  # noqa: BLE001 - toda falha vira envelope
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        session = holder.get("session")
        result = ToolResult(ok=False, warnings=list(session.warnings) if session else [], error=build_error(exc)).to_dict()
    audit.record(ctx.cfg, getattr(fn, "__name__", "?"), mutates, result)
    return result


def com_tool(*, needs_doc: bool = True, coords: bool = False, mutates: bool = True) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Registra uma função `f(s: Session, **params)` como ferramenta assíncrona sem o parâmetro `s`.

    O corpo roda na thread COM; a coroutine só espera no executor (não bloqueia o loop do MCP).
    Os type hints são resolvidos aqui (o FastMCP não enxergaria os globals do módulo da ferramenta).
    """

    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        hints = typing.get_type_hints(fn)
        sig = inspect.signature(fn)
        params = [p.replace(annotation=hints.get(p.name, p.annotation)) for p in list(sig.parameters.values())[1:]]

        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None, lambda: execute(fn, args, kwargs, needs_doc=needs_doc, coords=coords, mutates=mutates)
            )

        wrapper.__signature__ = sig.replace(parameters=params, return_annotation=dict[str, Any])  # type: ignore[attr-defined]
        wrapper.__annotations__ = {p.name: p.annotation for p in params} | {"return": dict[str, Any]}
        wrapper.__wrapped_impl__ = fn  # type: ignore[attr-defined]
        wrapper.__mcp_read_only__ = not mutates  # type: ignore[attr-defined]
        return wrapper

    return deco


def local_read_tool(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Pure reads/computations with the same envelope, without COM attachment."""
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
        try:
            return ToolResult(ok=True, data=fn(*args, **kwargs)).to_dict()
        except Exception as exc:
            return ToolResult(ok=False, error=build_error(exc)).to_dict()
    wrapper.__mcp_read_only__ = True
    return wrapper


_LOCAL_LOCK = threading.RLock()  # um cliente MCP pode disparar chamadas concorrentes sobre o mesmo arquivo


def local_tool(*, mutates: bool = True) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Ferramenta local (sem COM: arquivos DXF/PDF, SQLite). Assíncrona; respeita read_only antes de qualquer E/S."""

    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        def run(args: tuple, kwargs: dict) -> dict[str, Any]:
            cfg = get_context().cfg
            try:
                if mutates and cfg.read_only:
                    raise OperationBlockedError("Modo somente leitura: ferramenta bloqueada, inclusive dry_run/confirm.")
                with _LOCAL_LOCK:
                    result = ToolResult(ok=True, data=fn(*args, **kwargs)).to_dict()
            except Exception as exc:  # noqa: BLE001
                result = ToolResult(ok=False, error=build_error(exc)).to_dict()
            audit.record(cfg, fn.__name__, mutates, result)
            return result

        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, lambda: run(args, kwargs))

        wrapper.__mcp_read_only__ = not mutates  # type: ignore[attr-defined]
        return wrapper

    return deco
