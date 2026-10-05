"""Contrato das ferramentas: 26 registradas, docstrings úteis para a IA, schemas sem parâmetro interno."""

import asyncio

EXPECTED = {
    "status", "list_documents", "set_active_document", "save_document", "zoom_extents",
    "list_layers", "create_layer", "check_layer_standard",
    "query_entities", "get_entity",
    "draw_line", "draw_polyline", "draw_circle", "add_text", "add_mtext", "move_entity", "copy_entity", "delete_entities",
    "list_block_definitions", "insert_block", "read_block_attributes", "update_block_attributes",
    "export_blocks_to_excel", "import_blocks_from_excel", "sync_attributes_from_excel",
    "run_lisp", "system_capabilities", "snapshot_support_register", "audit_support_register", "compare_support_register",
    "dxf_info", "dxf_query", "dxf_get_entity", "dxf_read_attributes", "dxf_sql_query", "dxf_audit", "dxf_create",
    "dxf_create_layer", "dxf_add_entities", "dxf_define_block", "dxf_modify_entities", "dxf_delete_entities",
    "dxf_add_dimensions", "dxf_create_layout", "dxf_export", "dxf_insert_support_symbol",
    "add_dimension", "plot_to_pdf", "project_data_set", "project_data_get",
}


def test_all_50_tools_registered(mcp_server):
    tools = asyncio.run(mcp_server.list_tools())
    assert {t.name for t in tools} == EXPECTED and len(tools) == 50


def test_tool_descriptions_say_when_to_use_and_give_an_example(mcp_server):
    for t in asyncio.run(mcp_server.list_tools()):
        d = t.description or ""
        assert "QUANDO USAR" in d, t.name
        assert "Exemplo" in d or "Parâmetros" in d, t.name
        assert len(d) > 120, t.name


def test_schemas_hide_the_session_parameter_and_type_the_rest(mcp_server):
    by = {t.name: t for t in asyncio.run(mcp_server.list_tools())}
    for name, t in by.items():
        assert "s" not in t.inputSchema.get("properties", {}), name
    assert by["insert_block"].inputSchema["required"] == ["name", "point"]
    assert by["update_block_attributes"].inputSchema["required"] == ["attributes"]
    assert "filter" in by["update_block_attributes"].inputSchema["properties"]
    assert set(by["import_blocks_from_excel"].inputSchema["properties"]) >= {"path", "sheet", "mapping", "dry_run", "confirm"}
    for destructive in ("delete_entities", "save_document", "run_lisp"):
        assert "confirm" in by[destructive].inputSchema["properties"], destructive
    for batch in ("import_blocks_from_excel", "sync_attributes_from_excel", "update_block_attributes", "delete_entities"):
        assert "dry_run" in by[batch].inputSchema["properties"], batch


def test_envelope_shape_and_internal_errors_are_contained(call, ctx):
    assert set(call("status")) == {"ok", "data", "warnings", "error"}
    from autocad_mcp.tools import _base

    def boom(s):
        raise RuntimeError("bug inesperado")

    res = _base.execute(boom, (), {}, needs_doc=True, coords=False)
    assert res["ok"] is False and res["error"]["code"] == "internal_error" and "bug inesperado" in res["error"]["message"]
    assert set(res) == {"ok", "data", "warnings", "error"}


def test_profiles_only_name_real_tools_and_shrink_the_surface(ctx):
    from dataclasses import replace

    from autocad_mcp.server import PROFILE_TOOLS, build_server

    for name, tools in PROFILE_TOOLS.items():
        assert tools <= EXPECTED, (name, tools - EXPECTED)
    sizes = {}
    for profile in ("lean", "core", "full"):
        ctx.cfg = replace(ctx.cfg, profile=profile)
        sizes[profile] = len(asyncio.run(build_server().list_tools()))
    assert sizes["lean"] == len(PROFILE_TOOLS["lean"]) < sizes["core"] == len(PROFILE_TOOLS["core"]) < sizes["full"] == 50


def test_invalid_profile_falls_back_to_full():
    from autocad_mcp.config import Config

    assert Config.from_dict({"server": {"profile": "xyz"}}).profile == "full"
    assert Config.from_dict({"server": {"profile": "LEAN"}}).profile == "lean"
