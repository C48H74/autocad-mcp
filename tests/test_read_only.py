"""Read-only is enforced before COM or filesystem side effects, not merely hinted to a client."""
import asyncio
from dataclasses import replace
import importlib
from types import SimpleNamespace

import pytest

from autocad_mcp.config import Config, load_config
from autocad_mcp.server import TOOL_MODULES
from autocad_mcp.tools._base import execute


READS = {"status", "list_documents", "list_layers", "check_layer_standard", "query_entities", "get_entity",
         "list_block_definitions", "read_block_attributes", "system_capabilities", "snapshot_support_register",
         "audit_support_register", "compare_support_register", "dxf_info", "dxf_query", "dxf_get_entity",
         "dxf_read_attributes", "dxf_sql_query", "dxf_audit", "project_data_get"}


def test_every_tool_has_correct_mcp_annotation(mcp_server):
    for tool in asyncio.run(mcp_server.list_tools()):
        assert tool.annotations.readOnlyHint == (tool.name in READS), tool.name


def test_all_mutating_tools_block_before_connection_even_confirmed_or_dry_run(ctx, monkeypatch):
    ctx.cfg = replace(ctx.cfg, read_only=True, enable_lisp=True)
    def forbidden(*args, **kwargs):
        raise AssertionError("Read-only gate must run before COM")
    monkeypatch.setattr(ctx.conn, "run", forbidden)
    count = 0
    for module in TOOL_MODULES:
        for fn in importlib.import_module(module).TOOLS:
            if fn.__name__ in READS:
                continue
            count += 1
            result = asyncio.run(fn(confirm=True, dry_run=True))
            assert not result["ok"] and result["error"]["code"] == "operation_blocked", fn.__name__
    assert count == 31


def test_unclassified_new_tool_fails_closed(ctx, monkeypatch):
    ctx.cfg = replace(ctx.cfg, read_only=True)
    result = execute(lambda s: None, (), {}, needs_doc=False, coords=False)
    assert result["error"]["code"] == "operation_blocked"


def test_capabilities_work_without_com_and_report_config_truthfully(call, ctx, monkeypatch):
    ctx.cfg = replace(ctx.cfg, read_only=True, enable_lisp=True, allow_launch=True)
    monkeypatch.setattr(ctx.conn, "run", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("COM not allowed")))
    result = call("system_capabilities")
    assert result["ok"] and result["data"]["read_only"]
    assert not any(result["data"][k] for k in ["connection_verified", "lisp_enabled", "drawing_writes_enabled", "excel_writes_enabled", "auto_launch_enabled", "native_plant3d_database"])


def test_environment_override_survives_invalid_config(tmp_path, monkeypatch):
    path = tmp_path / "bad.toml"
    path.write_text("invalid == toml", encoding="utf-8")
    monkeypatch.setenv("AUTOCAD_MCP_CONFIG", str(path))
    monkeypatch.setenv("AUTOCAD_MCP_READ_ONLY", "1")
    assert load_config().read_only


def test_bad_values_cannot_disable_read_only(tmp_path, monkeypatch):
    assert Config.from_dict({"server": {"read_only": "false"}}).read_only
    path = tmp_path / "config.toml"
    path.write_text('[server]\nread_only = true\n[limits]\nmax_limit = "invalid"', encoding="utf-8")
    monkeypatch.setenv("AUTOCAD_MCP_CONFIG", str(path))
    assert load_config().read_only


def test_read_only_does_not_launch_autocad_even_when_launch_is_enabled(monkeypatch):
    from autocad_mcp import connection
    from autocad_mcp._com import com_error
    from autocad_mcp.errors import AutoCadNotRunningError
    def absent(*args):
        raise com_error(connection.MK_E_UNAVAILABLE, "not running", None, None)
    def launch(*args):
        pytest.fail("AutoCAD must not be launched")
    monkeypatch.setattr(connection, "HAS_PYWIN32", True)
    # default_app_factory attaches via pythoncom.GetActiveObject; patch exactly that (and the launch path).
    monkeypatch.setattr(connection, "pythoncom", SimpleNamespace(GetActiveObject=absent, IID_IDispatch=None))
    monkeypatch.setattr(connection, "pywintypes", SimpleNamespace(IID=lambda value: value, com_error=com_error))
    monkeypatch.setattr(connection, "win32client", SimpleNamespace(Dispatch=launch))
    with pytest.raises(AutoCadNotRunningError):
        connection.default_app_factory(Config(read_only=True, allow_launch=True))


def test_read_queries_and_snapshot_remain_available_in_read_only_mode(call, ctx, doc):
    ctx.cfg = replace(ctx.cfg, read_only=True)
    ctx.conn.cfg = ctx.cfg
    assert call("status")["data"]["server_read_only"]
    assert call("query_entities")["ok"]
    assert call("snapshot_support_register", block_filter="SUP-*")["ok"]
