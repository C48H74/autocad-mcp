"""Servidor MCP (FastMCP, transporte stdio). stdout pertence ao protocolo — nunca use print()."""

from __future__ import annotations

import atexit
import importlib
import logging
import sys

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from autocad_mcp import __version__
from autocad_mcp.config import load_config, setup_logging
from autocad_mcp.context import AppContext, get_context, set_context
from autocad_mcp.connection import AutoCadConnection

log = logging.getLogger("autocad_mcp.server")

TOOL_MODULES = (
    "autocad_mcp.tools.session",
    "autocad_mcp.tools.layers",
    "autocad_mcp.tools.entities",
    "autocad_mcp.tools.drawing",
    "autocad_mcp.tools.blocks",
    "autocad_mcp.tools.excel",
    "autocad_mcp.tools.advanced",
    "autocad_mcp.tools.quality",
    "autocad_mcp.tools.dxf",
    "autocad_mcp.tools.cad_extras",
)

# Perfis limitam quantas ferramentas o cliente enxerga (menos ferramentas = menos tokens/confusão).
# "full" = todas. Nomes inexistentes são ignorados; um teste garante que os perfis só citam ferramentas reais.
PROFILE_TOOLS: dict[str, frozenset[str]] = {
    "lean": frozenset({"status", "system_capabilities", "list_layers", "query_entities", "get_entity", "draw_line",
                       "draw_polyline", "add_text", "dxf_info", "dxf_query", "dxf_add_entities", "dxf_add_dimensions",
                       "dxf_export"}),
    "core": frozenset({"status", "system_capabilities", "list_documents", "save_document", "zoom_extents", "list_layers",
                       "create_layer", "query_entities", "get_entity", "draw_line", "draw_polyline", "draw_circle",
                       "add_text", "add_mtext", "move_entity", "delete_entities", "list_block_definitions",
                       "insert_block", "read_block_attributes", "update_block_attributes", "add_dimension",
                       "plot_to_pdf", "snapshot_support_register", "audit_support_register",
                       "compare_support_register", "dxf_info", "dxf_query", "dxf_get_entity", "dxf_read_attributes",
                       "dxf_sql_query", "dxf_audit", "dxf_create", "dxf_add_entities", "dxf_add_dimensions",
                       "dxf_create_layout", "dxf_export", "dxf_insert_support_symbol"}),
}

INSTRUCTIONS = (
    "Controla o AutoCAD aberto (COM). Comece SEMPRE por status(). Escritas são desfeitas com um único "
    "Ctrl+Z; operações destrutivas exigem confirm=true e as em lote aceitam dry_run=true (faça dry_run "
    "primeiro). Toda resposta é {ok, data, warnings, error}; coordenadas vêm com a unidade do desenho."
)


def build_server() -> FastMCP:
    """Cria o FastMCP e registra todas as ferramentas disponíveis."""
    mcp = FastMCP("autocad-mcp", instructions=INSTRUCTIONS)
    try:
        allowed = PROFILE_TOOLS.get(get_context().cfg.profile)
    except RuntimeError:  # sem contexto (import/inspeção): registra tudo
        allowed = None
    for mod_name in TOOL_MODULES:
        try:
            module = importlib.import_module(mod_name)
        except ModuleNotFoundError as exc:
            if exc.name == mod_name:  # módulo de etapa ainda inexistente
                log.debug("Módulo %s ausente; ignorado", mod_name)
                continue
            raise
        for fn in module.TOOLS:
            if allowed is not None and fn.__name__ not in allowed:
                continue
            read_only = getattr(fn, "__mcp_read_only__", False)
            mcp.tool(annotations=ToolAnnotations(readOnlyHint=read_only, destructiveHint=not read_only))(fn)
    return mcp


def main() -> None:
    cfg = load_config()
    logfile = setup_logging(cfg)
    log.info("autocad-mcp %s iniciando (stdio). log=%s lisp=%s", __version__, logfile, cfg.enable_lisp)
    set_context(AppContext(cfg, AutoCadConnection(cfg)))
    atexit.register(lambda: set_context(None))
    mcp = build_server()
    try:
        mcp.run(transport="stdio")
    except KeyboardInterrupt:
        pass
    finally:
        get_context().conn.close()
        sys.stderr.flush()


if __name__ == "__main__":
    main()
