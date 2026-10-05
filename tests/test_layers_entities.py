"""Etapa 2: camadas e consulta de entidades (AutoCAD falso)."""

import pytest


@pytest.fixture
def populated(doc):
    doc.Layers.Add("PIPE-A")
    doc.Layers.Add("PIPE-B")
    doc.Layers.Add("SUPORTES")
    doc.Layers.Add("LIXO")
    doc.Layers.Add("A.B")
    doc.Layers.Add("AxB")
    doc.Blocks.define("SUP-GUIDE", {"TAG": "", "TIPO": ""})
    ms = doc.model
    for i in range(30):
        doc.ActiveLayer = "PIPE-A"
        ms.AddLine([i, 0, 0], [i, 10, 0])
    doc.ActiveLayer = "PIPE-B"
    for i in range(5):
        ms.AddCircle([100 + i, 100, 0], 2)
    doc.ActiveLayer = "SUPORTES"
    ms.InsertBlock([50, 50, 0], "SUP-GUIDE", 1, 1, 1, 0)
    doc.ActiveLayer = "LIXO"
    ms.AddText("nota", [0, 0, 0], 2.5)
    ms.AddLine([500, 500, 0], [600, 600, 0])
    doc.ActiveLayer = "A.B"
    ms.AddLine([0, 0, 0], [1, 1, 0])
    doc.ActiveLayer = "AxB"
    ms.AddLine([0, 0, 0], [2, 2, 0])
    doc.ActiveLayer = "0"
    return doc


def test_list_layers_with_lowercase_color_quirk_filter_and_pagination(call, populated):
    r = call("list_layers", limit=3)
    assert r["ok"] and r["data"]["page"]["total"] == 7 and r["data"]["page"]["has_more"]
    assert r["data"]["layers"][0]["name"] == "0" and r["data"]["layers"][0]["color"] == 7
    r2 = call("list_layers", name_filter="pipe-*")
    assert [x["name"] for x in r2["data"]["layers"]] == ["PIPE-A", "PIPE-B"]
    r3 = call("list_layers", limit=3, offset=3)
    assert r3["data"]["page"]["offset"] == 3 and len(r3["data"]["layers"]) == 3


def test_create_layer_undo_and_idempotent(call, doc):
    r = call("create_layer", name="SUPORTES", color="green", linetype="HIDDEN")
    assert r["ok"] and r["data"]["created"] and r["data"]["layer"]["color"] == 3
    assert "HIDDEN" in doc.Linetypes.loaded  # carregado sob demanda
    again = call("create_layer", name="suportes")
    assert again["ok"] and again["data"]["created"] is False and any("já existe" in w for w in again["warnings"])
    assert doc.ctrl_z() and "SUPORTES" not in doc.Layers.names()  # um Ctrl+Z desfaz a criação


@pytest.mark.parametrize("kw", [{"name": "bad/name"}, {"name": ""}, {"name": "X", "color": 999}, {"name": "X", "linetype": "NAOEXISTE"}])
def test_create_layer_validation(call, kw):
    r = call("create_layer", **kw)
    assert not r["ok"] and r["error"]["code"] == "invalid_parameter"


def test_query_by_type_layer_pagination_and_units(call, populated):
    r = call("query_entities", type="LINE", layer="PIPE-A", limit=10)
    d = r["data"]
    assert r["ok"] and d["page"]["total"] == 30 and d["page"]["returned"] == 10 and d["page"]["next_offset"] == 10
    assert d["entities"][0]["geometry"]["length"] == 10.0 and d["units"] == "mm"
    last = call("query_entities", type="LINE", layer="PIPE-A", limit=10, offset=20)["data"]
    assert last["page"]["has_more"] is False and last["page"]["returned"] == 10


def test_query_wildcards_and_escaped_dots(call, populated):
    assert call("query_entities", layer="PIPE-*")["data"]["page"]["total"] == 35
    dot = call("query_entities", layer="A.B")["data"]  # '.' literal, não coringa: não pode casar 'AxB'
    assert dot["page"]["total"] == 1 and dot["entities"][0]["layer"] == "A.B"
    assert call("query_entities", type="line,circle", layer="PIPE-B")["data"]["page"]["total"] == 5


def test_query_by_bbox_modes(call, populated):
    inside = call("query_entities", bbox=[95, 95, 110, 110], layer="PIPE-B")["data"]
    assert inside["page"]["total"] == 5
    assert call("query_entities", type="LINE", bbox=[-1, -1, 12, 11], layer="PIPE-A")["data"]["page"]["total"] == 13
    assert call("query_entities", bbox=[0, 0, 1, 1], bbox_mode="diagonal")["error"]["code"] == "invalid_parameter"


def test_query_block_name_matches_dynamic_blocks_by_effective_name(call, doc):
    doc.Blocks.define("SUP-DYN", {"TAG": ""})
    from tests.fake_autocad import FakeBlockRef

    ref = FakeBlockRef(doc, "SUP-DYN", (1.0, 2.0, 0.0), anonymous=True)
    doc.model._add(ref)
    assert ref.Name.startswith("*U")
    r = call("query_entities", block_name="sup-*")
    assert r["ok"] and r["data"]["page"]["total"] == 1 and r["data"]["entities"][0]["geometry"]["block"] == "SUP-DYN"


def test_query_falls_back_to_python_filter_when_dxf_filter_fails(call, populated, ctx):
    from dataclasses import replace

    ctx.cfg = replace(ctx.cfg, scan_threshold=0)  # força o caminho de SelectionSet
    ctx.conn.cfg = ctx.cfg
    populated.reject_dxf_filters = True
    r = call("query_entities", type="LINE", layer="PIPE-A")
    assert r["ok"] and r["data"]["page"]["total"] == 30
    assert any("filtragem em Python" in w for w in r["warnings"])
    b = call("query_entities", block_name="SUP-GUIDE")
    assert b["data"]["page"]["total"] == 1


def test_selection_sets_never_leak(call, populated):
    call("query_entities", type="LINE")
    populated.reject_dxf_filters = True
    call("query_entities", type="LINE")
    call("check_layer_standard", allowed_layers=["PIPE-*"])
    assert populated.SelectionSets.Count == 0


def test_query_clamps_limit_with_warning(call, populated):
    r = call("query_entities", limit=100000)
    assert r["ok"] and any("limit reduzido" in w for w in r["warnings"])


def test_get_entity_details_and_errors(call, populated):
    line = populated.model.Item(0)
    r = call("get_entity", handle=line.Handle)
    e = r["data"]["entity"]
    assert r["ok"] and e["type"] == "LINE" and e["object_name"] == "AcDbLine" and e["geometry"]["angle_deg"] == 90.0
    assert e["bbox"]["max"] == [0.0, 10.0, 0.0] and r["data"]["units"] == "mm"
    assert call("get_entity", handle="FFFF")["error"]["code"] == "entity_not_found"
    assert call("get_entity", handle="xyz!")["error"]["code"] == "invalid_parameter"


def test_check_layer_standard_reports_offenders(call, populated):
    r = call("check_layer_standard", allowed_layers=["PIPE-*", "SUPORTES", "EIXOS"], limit=2)
    d = r["data"]
    assert r["ok"] and d["compliant"] is False
    by = {x["layer"]: x for x in d["offending_layers"]}
    assert set(by) == {"LIXO", "A.B", "AxB"}
    assert by["LIXO"]["entity_count"] == 2 and by["LIXO"]["types_in_sample"] == {"TEXT": 1, "LINE": 1}
    assert d["offending_entity_total"] == 4
    assert d["standard_layers_missing_in_drawing"] == ["EIXOS"]
    ok = call("check_layer_standard", allowed_layers=["PIPE-*", "SUPORTES", "LIXO", "A?B", "A.B"])
    assert ok["data"]["compliant"] is True
    assert call("check_layer_standard", allowed_layers=[])["error"]["code"] == "invalid_parameter"


def test_small_drawings_are_scanned_without_creating_selection_sets(call, populated, ctx):
    """No AutoCAD real, criar/apagar SelectionSet registra um passo de desfazer vazio (medido no Plant 3D 2021)."""
    from dataclasses import replace

    r = call("query_entities", type="LINE", layer="PIPE-A")
    assert r["ok"] and r["data"]["page"]["total"] == 30 and not r["warnings"]
    assert populated.SelectionSets.adds == 0
    ctx.cfg = replace(ctx.cfg, scan_threshold=0)
    ctx.conn.cfg = ctx.cfg
    big = call("query_entities", type="LINE", layer="PIPE-A")
    assert big["data"]["page"]["total"] == 30 and populated.SelectionSets.adds == 1
    assert any("passo de desfazer vazio" in w for w in big["warnings"])
