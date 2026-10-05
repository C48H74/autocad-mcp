"""Integração com o AutoCAD REAL — só Windows, AutoCAD aberto num desenho de TESTE.

Rode:  pytest -m autocad
Segurança: os testes se recusam a tocar em qualquer desenho cujo nome não comece com "MCP_TEST"
(veja no README como montar o desenho de teste: camadas, bloco SUP-TEST com atributos TAG/TIPO/LINHA).
"""

from __future__ import annotations

import time

import pytest

from autocad_mcp._com import HAS_PYWIN32

pytestmark = [pytest.mark.autocad, pytest.mark.skipif(not HAS_PYWIN32, reason="requer Windows + pywin32")]


@pytest.fixture(scope="module")
def live():
    from autocad_mcp.config import Config
    from autocad_mcp.connection import AutoCadConnection
    from autocad_mcp.context import AppContext, set_context
    from autocad_mcp.errors import AutoCadMcpError

    cfg = Config(com_timeout_s=60.0)
    conn = AutoCadConnection(cfg)
    try:
        name = conn.run(lambda s: str(s.doc.Name))
    except AutoCadMcpError as exc:
        pytest.skip(f"AutoCAD indisponível: {exc}")
    if not name.upper().startswith("MCP_TEST"):
        pytest.skip(f"Desenho ativo '{name}' não é um desenho de teste (nome deve começar com MCP_TEST).")
    set_context(AppContext(cfg, conn))
    yield conn
    set_context(None)


@pytest.fixture
def call_live(live):
    import asyncio
    import json

    from autocad_mcp.server import build_server

    server = build_server()

    def _call(tool, /, **kw):
        res = asyncio.run(server.call_tool(tool, kw))
        content = res[0] if isinstance(res, tuple) else res
        return json.loads(content[0].text)

    return _call


def _wait_idle(live, seconds=10.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if live.run(lambda s: s.active_command()) is None:
            return
        time.sleep(0.2)
    raise AssertionError("AutoCAD não ficou ocioso")


def test_status_reports_units_and_version(call_live):
    r = call_live("status")
    assert r["ok"] and r["data"]["document"]["units"] and r["data"]["application"]["version"]


def test_layer_line_roundtrip_and_delete_needs_confirm(call_live):
    assert call_live("create_layer", name="MCP_TMP", color="green")["ok"]
    line = call_live("draw_line", start=[0, 0, 0], end=[300, 400, 0], layer="MCP_TMP")
    assert line["ok"] and line["data"]["entity"]["geometry"]["length"] == pytest.approx(500.0)
    h = line["data"]["entity"]["handle"]
    assert call_live("get_entity", handle=h)["data"]["entity"]["layer"] == "MCP_TMP"
    q = call_live("query_entities", type="LINE", layer="MCP_TMP")
    assert q["ok"] and q["data"]["page"]["total"] >= 1
    assert call_live("delete_entities", handles=[h])["error"]["code"] == "confirmation_required"
    assert call_live("delete_entities", handles=[h], confirm=True)["data"]["deleted"] == 1


def test_block_definitions_list_contains_test_block(call_live):
    r = call_live("list_block_definitions", name_filter="SUP-TEST")
    assert r["ok"] and r["data"]["blocks"], "crie o bloco SUP-TEST (ver README)"
    assert {a["tag"] for a in r["data"]["blocks"][0]["attributes"]} >= {"TAG", "TIPO", "LINHA"}


def test_import_100_blocks_and_one_undo_reverts_everything(live, call_live, tmp_path):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["TAG", "TIPO", "X", "Y", "Z", "LINHA"])
    stamp = time.strftime("%H%M%S")  # TAGs únicas por execução: sobras de execuções anteriores viram "update", não "insert"
    for i in range(100):
        ws.append([f"MCPT{stamp}-{i:03d}", "GUIA", i * 300.0, 5000.0, 0.0, f"L-{i}"])
    path = tmp_path / "mcp_test_100.xlsx"
    wb.save(path)

    def count():
        return call_live("query_entities", type="INSERT", block_name="SUP-TEST", limit=1)["data"]["page"]["total"]

    before = count()
    r = call_live("import_blocks_from_excel", path=str(path), block_name="SUP-TEST", key_tag="TAG")
    assert r["ok"] and r["data"]["inserted"] == 100 and r["data"]["errors"] == 0
    assert count() == before + 100
    live.run(lambda s: s.doc.SendCommand("_.U "))  # equivale a UM Ctrl+Z; SendCommand é assíncrono
    # Não confie em "ocioso" logo após SendCommand (o comando pode nem ter começado): aguarde o efeito.
    end = time.monotonic() + 15.0
    while time.monotonic() < end and count() != before:
        time.sleep(0.3)
    _wait_idle(live)
    assert count() == before, "um único desfazer deve reverter os 100 blocos"


def test_native_dimension_measures_and_deletes(call_live):
    assert call_live("create_layer", name="MCP_TMP", color="green")["ok"]
    r = call_live("add_dimension", kind="linear", p1=[0, 0, 0], p2=[1500, 0, 0], location=[750, -200, 0], layer="MCP_TMP")
    assert r["ok"], r
    assert r["data"]["measurement"] == pytest.approx(1500.0)
    h = r["data"]["handle"]
    assert call_live("get_entity", handle=h)["data"]["entity"]["type"] == "DIMENSION"
    assert call_live("add_dimension", kind="diameter", center=[0, 0, 0], radius=60, layer="MCP_TMP")["data"]["measurement"] == pytest.approx(120.0)
    q = call_live("query_entities", type="DIMENSION", layer="MCP_TMP")
    handles = [e["handle"] for e in q["data"]["entities"]]
    assert call_live("delete_entities", handles=handles, confirm=True)["data"]["deleted"] == len(handles)


def test_plot_to_pdf_with_real_plotter(call_live, tmp_path):
    out = tmp_path / "mcp_plot.pdf"
    r = call_live("plot_to_pdf", path=str(out), layout="Model", overwrite=True)
    assert r["ok"], r
    assert out.read_bytes().startswith(b"%PDF") and out.stat().st_size > 1000


def test_project_data_xrecord_roundtrip(call_live):
    stamp = time.strftime("%H%M%S")
    assert call_live("project_data_set", key="MCP_TEST_REV", value=f"B-{stamp}")["ok"]
    assert call_live("project_data_get", key="MCP_TEST_REV")["data"]["values"] == {"MCP_TEST_REV": f"B-{stamp}"}
