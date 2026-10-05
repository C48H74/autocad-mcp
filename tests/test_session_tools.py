"""status / documentos / salvar / zoom via FastMCP (schema real das ferramentas)."""

from autocad_mcp.server import build_server


def test_status_ok_with_units(call, doc):
    r = call("status")
    assert r["ok"] and r["error"] is None
    d = r["data"]
    assert d["connected"] and d["application"]["name"] == "AutoCAD"
    assert d["document"]["name"] == "SUPORTES-01.dwg"
    assert d["document"]["units"] == "mm" and d["document"]["units_code"] == 4
    assert d["document"]["model_space_entities"] == 0
    assert d["command_active"] is False


def test_status_reports_active_command(call, app):
    app.set_command("LINE")
    r = call("status")
    assert r["ok"] and r["data"]["command_active"] and r["data"]["active_command"] == "LINE"
    assert any("Comando ativo" in w for w in r["warnings"])


def test_status_when_autocad_closed_fails_cleanly(cfg):
    from autocad_mcp.connection import AutoCadConnection
    from autocad_mcp.context import AppContext, set_context
    from autocad_mcp.errors import AutoCadNotRunningError

    def factory(_c):
        raise AutoCadNotRunningError("AutoCAD não está aberto. Abra o AutoCAD.")

    set_context(AppContext(cfg, AutoCadConnection(cfg, app_factory=factory)))
    try:
        import asyncio, json
        res = asyncio.run(build_server().call_tool("status", {}))
        payload = json.loads((res[0] if isinstance(res, tuple) else res)[0].text)
    finally:
        set_context(None)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "autocad_not_running"
    assert "não está aberto" in payload["error"]["message"]


def test_status_without_drawing_still_ok(call, app):
    app.docs = []
    r = call("status")
    assert r["ok"] and r["data"]["document"] is None
    assert any("sem nenhum desenho" in w for w in r["warnings"])


def test_list_and_set_active_document(call, app):
    from tests.fake_autocad import FakeDoc

    other = FakeDoc("OUTRO.dwg")
    other.app = app
    app.docs.append(other)
    r = call("list_documents")
    assert [d["name"] for d in r["data"]["documents"]] == ["SUPORTES-01.dwg", "OUTRO.dwg"]
    assert r["data"]["documents"][0]["active"] is True
    assert call("set_active_document", name="outro.DWG")["data"]["active"]["name"] == "OUTRO.dwg"
    assert app.active is other
    bad = call("set_active_document", name="nao-existe.dwg")
    assert not bad["ok"] and bad["error"]["code"] == "document_error"


def test_save_requires_confirm(call, doc):
    r = call("save_document")
    assert not r["ok"] and r["error"]["code"] == "confirmation_required" and doc.save_count == 0
    ok = call("save_document", confirm=True)
    assert ok["ok"] and doc.save_count == 1


def test_save_refuses_unnamed_drawing_and_blocks_on_active_command(call, doc, app):
    doc.Path = ""
    r = call("save_document", confirm=True)
    assert not r["ok"] and "SALVARCOMO" in r["error"]["message"] and doc.save_count == 0
    doc.Path = "C:\\proj"
    app.set_command("PLINE")
    blocked = call("save_document", confirm=True)
    assert not blocked["ok"] and blocked["error"]["code"] == "operation_blocked"


def test_zoom_extents(call, app):
    assert call("zoom_extents")["ok"] and app.zoomed == 1


def test_busy_autocad_is_absorbed_by_retry_in_tool_call(call, app):
    app.reject_next(4)
    assert call("status")["ok"]
