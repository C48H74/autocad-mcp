"""Motor DXF offline: roda de verdade com ezdxf (sem AutoCAD, sem COM)."""
from dataclasses import replace

import pytest

from autocad_mcp.dxf_engine import sql_query


@pytest.fixture
def work(ctx, tmp_path):
    ctx.cfg = replace(ctx.cfg, excel_allowed_dirs=(tmp_path,))
    ctx.conn.cfg = ctx.cfg
    return tmp_path


@pytest.fixture
def dxf(work, call):
    p = str(work / "a.dxf")
    assert call("dxf_create", path=p)["ok"]
    assert call("dxf_define_block", path=p, name="SUP-GUIA",
                entities=[{"type": "circle", "center": [0, 0], "radius": 50}], attributes=["TAG", "TIPO"])["ok"]
    r = call("dxf_add_entities", path=p, entities=[
        {"type": "line", "start": [0, 0], "end": [300, 400], "layer": "EIXOS"},
        {"type": "circle", "center": [750, 300], "radius": 60},
        {"type": "insert", "block": "SUP-GUIA", "insert": [500, 0], "attributes": {"TAG": "S-01", "TIPO": "GUIA"}},
        {"type": "insert", "block": "SUP-GUIA", "insert": [900, 0], "attributes": {"TAG": "S-02", "TIPO": "FIXO"}},
    ])
    assert r["ok"] and r["data"]["added"] == 4
    return p


def test_info_and_query_roundtrip(call, dxf):
    info = call("dxf_info", path=dxf)["data"]
    assert info["units"] == "mm" and "EIXOS" in {layer["name"] for layer in info["layers"]}
    assert info["modelspace_counts"] == {"LINE": 1, "CIRCLE": 1, "INSERT": 2}
    q = call("dxf_query", path=dxf, type="LINE")["data"]
    assert q["page"]["total"] == 1
    assert q["entities"][0]["geometry"]["length"] == pytest.approx(500.0)
    h = q["entities"][0]["handle"]
    assert call("dxf_get_entity", path=dxf, handle=h)["data"]["entity"]["layer"] == "EIXOS"


def test_read_attributes_offline(call, dxf):
    rows = call("dxf_read_attributes", path=dxf, block_filter="SUP-*")["data"]
    assert rows["count"] == 2
    assert {r["attributes"]["TAG"] for r in rows["blocks"]} == {"S-01", "S-02"}


def test_sql_is_read_only_and_works(call, dxf):
    ok = call("dxf_sql_query", path=dxf, sql="SELECT tag, value FROM attributes WHERE tag='TIPO' ORDER BY value")
    assert ok["data"]["rows"] == [["TIPO", "FIXO"], ["TIPO", "GUIA"]]
    for bad in ["DROP TABLE entities", "SELECT 1; DELETE FROM entities", "SELECT * FROM entities; --",
                "ATTACH DATABASE 'x' AS y", "PRAGMA table_info(entities)"]:
        r = call("dxf_sql_query", path=dxf, sql=bad)
        assert not r["ok"] and r["error"]["code"] == "invalid_parameter", bad


def test_batch_is_atomic_on_invalid_entity(call, dxf):
    before = call("dxf_info", path=dxf)["data"]["modelspace_total"]
    r = call("dxf_add_entities", path=dxf, entities=[{"type": "line", "start": [0, 0], "end": [1, 1]},
                                                       {"type": "circle", "center": [0, 0], "radius": -5}])
    assert not r["ok"] and "entities[1]" in r["error"]["message"]
    assert call("dxf_info", path=dxf)["data"]["modelspace_total"] == before


def test_modify_and_output_path_preserves_original(call, dxf, work):
    h = call("dxf_query", path=dxf, type="INSERT")["data"]["entities"][0]["handle"]
    out = str(work / "rev1.dxf")
    r = call("dxf_modify_entities", path=dxf, handles=[h], attributes={"TAG": "S-99"}, translate=[10, 0, 0], output_path=out)
    assert r["ok"] and r["data"]["modified"] == 1
    assert "S-99" in {x["attributes"]["TAG"] for x in call("dxf_read_attributes", path=out)["data"]["blocks"]}
    assert "S-99" not in {x["attributes"]["TAG"] for x in call("dxf_read_attributes", path=dxf)["data"]["blocks"]}
    bad = call("dxf_modify_entities", path=dxf, handles=[h], attributes={"NAOEXISTE": "x"})
    assert not bad["ok"]


def test_delete_requires_confirm_dry_run_and_rejects_non_entities(call, dxf):
    h = call("dxf_query", path=dxf, type="CIRCLE")["data"]["entities"][0]["handle"]
    assert call("dxf_delete_entities", path=dxf, handles=[h])["error"]["code"] == "confirmation_required"
    assert call("dxf_delete_entities", path=dxf, handles=[h], dry_run=True)["data"]["would_delete"] == 1
    assert call("dxf_query", path=dxf, type="CIRCLE")["data"]["page"]["total"] == 1
    assert call("dxf_delete_entities", path=dxf, handles=[h], confirm=True)["data"]["deleted"] == 1
    assert call("dxf_query", path=dxf, type="CIRCLE")["data"]["page"]["total"] == 0
    nope = call("dxf_delete_entities", path=dxf, handles=["1"], confirm=True)  # handle de tabela interna
    assert not nope["ok"] and nope["error"]["code"] == "entity_not_found"


def test_dimensions_have_correct_measurements(call, dxf):
    r = call("dxf_add_dimensions", path=dxf, dimensions=[
        {"kind": "linear", "p1": [0, 0], "p2": [1500, 0], "base": [0, -200], "layer": "COTAS"},
        {"kind": "aligned", "p1": [0, 0], "p2": [300, 400], "offset": 30},
        {"kind": "radius", "center": [750, 300], "radius": 60},
        {"kind": "diameter", "center": [750, 300], "radius": 60},
    ])
    assert r["ok"], r
    m = [d["measurement"] for d in r["data"]["dimensions"]]
    assert m[0] == pytest.approx(1500) and m[1] == pytest.approx(500) and m[2] == pytest.approx(60) and m[3] == pytest.approx(120)
    assert call("dxf_query", path=dxf, type="DIMENSION", layer="COTAS")["data"]["page"]["total"] == 1
    assert not call("dxf_add_dimensions", path=dxf, dimensions=[{"kind": "bogus"}])["ok"]


def test_layout_viewport_and_pdf_png_export(call, dxf, work):
    r = call("dxf_create_layout", path=dxf, name="Folha1", paper="A3",
             viewports=[{"center": [210, 148], "width": 380, "height": 260, "view_center": [500, 200], "scale": 0.2}])
    assert r["ok"] and r["data"]["size_mm"] == [420, 297] and len(r["data"]["viewports"]) == 1
    assert not call("dxf_create_layout", path=dxf, name="Folha1")["ok"]  # duplicado
    for name, magic in (("m.pdf", b"%PDF"), ("l.pdf", b"%PDF"), ("l.png", b"\x89PNG")):
        res = call("dxf_export", path=dxf, output=str(work / name), layout=None if name == "m.pdf" else "Folha1")
        assert res["ok"], res
        assert (work / name).read_bytes().startswith(magic)
    assert not call("dxf_export", path=dxf, output=str(work / "x.exe"))["ok"]


def test_audit_clean_and_path_restrictions(call, dxf, work):
    assert call("dxf_audit", path=dxf)["data"]["clean"]
    outside = call("dxf_info", path="/etc/hosts.dxf")
    assert outside["error"]["code"] == "operation_blocked"
    escape = call("dxf_info", path=str(work / ".." / "etc.dxf"))
    assert not escape["ok"]
    assert call("dxf_create", path=dxf)["error"]["code"] == "invalid_parameter"  # sem overwrite
    assert call("dxf_create", path=dxf, overwrite=True)["ok"]


def test_sql_helper_requires_select(work, call, dxf):
    from autocad_mcp import dxf_engine

    with pytest.raises(Exception):
        sql_query(dxf_engine.open_doc(__import__("pathlib").Path(dxf)), "UPDATE entities SET layer='x'")


def test_support_symbols_are_inserted_with_attributes(call, work):
    dxf = str(work / "sym.dxf")
    assert call("dxf_create", path=dxf)["ok"]
    for i, kind in enumerate(["GUIA", "ANCORA", "APOIO", "MOLA"]):
        r = call("dxf_insert_support_symbol", path=dxf, kind=kind, insert=[i * 400, 1000], tag=f"S-1{i}", line="L-12", layer="SUPORTES")
        assert r["ok"], r
    rows = call("dxf_read_attributes", path=dxf, layer_filter="SUPORTES")["data"]["blocks"]
    assert {(r["attributes"]["TAG"], r["attributes"]["TIPO"], r["attributes"]["LINHA"]) for r in rows} == {
        ("S-10", "GUIA", "L-12"), ("S-11", "ANCORA", "L-12"), ("S-12", "APOIO", "L-12"), ("S-13", "MOLA", "L-12")}
    assert not call("dxf_insert_support_symbol", path=dxf, kind="XYZ", insert=[0, 0])["ok"]
    assert call("dxf_audit", path=dxf)["data"]["clean"]
    assert call("dxf_export", path=dxf, output=str(work / "s.png"))["ok"]


def test_ensure_layer_applies_color_and_linetype():
    from autocad_mcp import dxf_engine
    doc = dxf_engine.create_doc("R2018", "mm")
    dxf_engine.ensure_layer(doc, "TUBO", 5)
    dxf_engine.ensure_layer(doc, "EIXO", 1, "DASHED")
    assert doc.layers.get("TUBO").dxf.color == 5
    assert doc.layers.get("EIXO").dxf.color == 1 and doc.layers.get("EIXO").dxf.linetype == "DASHED"
