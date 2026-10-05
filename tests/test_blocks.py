"""Etapa 3: blocos e atributos (AutoCAD falso)."""

import pytest


@pytest.fixture
def bdoc(doc):
    doc.Layers.Add("SUPORTES")
    doc.Layers.Add("OUTRA")
    doc.Blocks.define("SUP-GUIDE", {"TAG": "", "TIPO": "GUIA", "LINHA": ""})
    doc.Blocks.define("SUP-SHOE", {"TAG": "", "TIPO": "SHOE"})
    doc.Blocks.define("SEM-ATT")
    doc.Blocks.define("XREF-1", is_xref=True)
    doc.journal.groups.clear()  # dados de preparo não contam como histórico de undo
    return doc


def _insert(call, tag, x=0, block="SUP-GUIDE", **kw):
    return call("insert_block", name=block, point=[x, 0, 0], layer="SUPORTES", attributes={"TAG": tag, **kw})


def test_list_block_definitions_with_tags_pagination_and_instances(call, bdoc):
    _insert(call, "PS-1")
    r = call("list_block_definitions", count_instances=True)
    d = r["data"]
    assert r["ok"] and [b["name"] for b in d["blocks"]] == ["SEM-ATT", "SUP-GUIDE", "SUP-SHOE"]  # sem layouts/xref
    guide = next(b for b in d["blocks"] if b["name"] == "SUP-GUIDE")
    assert [a["tag"] for a in guide["attributes"]] == ["TAG", "TIPO", "LINHA"] and guide["attributes"][1]["default"] == "GUIA"
    assert guide["instances"] == 1
    assert call("list_block_definitions", name_filter="sup-s*")["data"]["blocks"][0]["name"] == "SUP-SHOE"
    assert call("list_block_definitions", limit=1, offset=1)["data"]["blocks"][0]["name"] == "SUP-GUIDE"
    assert len(call("list_block_definitions", include_xrefs=True)["data"]["blocks"]) == 4


def test_insert_block_sets_attributes_units_and_single_undo(call, bdoc):
    r = call("insert_block", name="sup-guide", point=[1250.5, 830], scale=2, rotation=90, layer="SUPORTES",
             attributes={"tag": "PS-101", "LINHA": "10-P-1001", "XXX": "a"})
    d = r["data"]
    assert r["ok"] and d["units"] == "mm"
    b = d["block"]
    assert b["block"] == "SUP-GUIDE" and b["position"] == [1250.5, 830.0, 0.0] and b["rotation_deg"] == 90.0
    assert b["scale"] == [2.0, 2.0, 2.0] and b["layer"] == "SUPORTES"
    assert b["attributes"] == {"TAG": "PS-101", "TIPO": "GUIA", "LINHA": "10-P-1001"}
    assert any("XXX" in w for w in r["warnings"])
    assert bdoc.model.Count == 1
    assert bdoc.ctrl_z() and bdoc.model.Count == 0  # inserção + atributos = UM passo
    assert not bdoc.ctrl_z()


def test_insert_block_errors(call, bdoc):
    r = call("insert_block", name="SUP-GUYDE", point=[0, 0])
    assert not r["ok"] and r["error"]["code"] == "invalid_parameter" and "SUP-GUIDE" in r["error"]["message"]
    assert call("insert_block", name="SUP-GUIDE", point=[0, 0], layer="NOPE")["error"]["code"] == "invalid_parameter"
    assert call("insert_block", name="SUP-GUIDE", point=[0])["error"]["code"] == "invalid_parameter"
    assert call("insert_block", name="SUP-GUIDE", point=[0, 0], scale=0)["error"]["code"] == "invalid_parameter"
    assert call("insert_block", name="SUP-GUIDE", point=[0, 0], attributes={"TAG": None})["error"]["code"] == "invalid_parameter"
    assert bdoc.model.Count == 0
    ok = call("insert_block", name="SUP-GUIDE", point=[0, 0], layer="NOVA", create_missing_layer=True)
    assert ok["ok"] and "NOVA" in bdoc.Layers.names()
    assert bdoc.ctrl_z() and "NOVA" not in bdoc.Layers.names() and bdoc.model.Count == 0  # camada + bloco: 1 passo
    warn = call("insert_block", name="SEM-ATT", point=[0, 0], attributes={"TAG": "x"})
    assert any("não tem atributos" in w for w in warn["warnings"])


def test_insert_is_blocked_while_a_command_is_active(call, bdoc, app):
    app.set_command("LINE")
    r = call("insert_block", name="SUP-GUIDE", point=[0, 0])
    assert not r["ok"] and r["error"]["code"] == "operation_blocked" and "LINE" in r["error"]["message"]
    assert bdoc.model.Count == 0


def test_read_block_attributes_filters_pagination_and_dynamic(call, bdoc):
    for i in range(7):
        _insert(call, f"PS-{i}", x=i * 100, LINHA="L1" if i % 2 else "L2")
    _insert(call, "SH-1", x=999, block="SUP-SHOE")
    r = call("read_block_attributes", block_name="SUP-GUIDE", limit=3)
    d = r["data"]
    assert d["page"]["total"] == 7 and d["page"]["returned"] == 3 and d["page"]["has_more"]
    assert d["blocks"][0]["attributes"]["TAG"] == "PS-0" and d["units"] == "mm"
    assert call("read_block_attributes", block_name="SUP-*")["data"]["page"]["total"] == 8
    assert call("read_block_attributes", layer="OUTRA")["data"]["page"]["total"] == 0


def test_update_single_handle_fill_empty_needs_no_confirm_but_overwrite_does(call, bdoc):
    h = _insert(call, "PS-1")["data"]["block"]["handle"]
    fill = call("update_block_attributes", attributes={"LINHA": "10-P-1001"}, handle=h)  # vazio → preenchido
    assert fill["ok"] and fill["data"]["applied"] and fill["data"]["overwrites_existing_values"] == 0
    over = call("update_block_attributes", attributes={"LINHA": "OUTRA"}, handle=h)  # sobrescreve
    assert not over["ok"] and over["error"]["code"] == "confirmation_required"
    assert over["error"]["details"]["changes"][0]["changes"]["LINHA"] == {"from": "10-P-1001", "to": "OUTRA"}
    assert call("read_block_attributes")["data"]["blocks"][0]["attributes"]["LINHA"] == "10-P-1001"  # nada mudou
    assert call("update_block_attributes", attributes={"LINHA": "OUTRA"}, handle=h, confirm=True)["data"]["applied"]
    assert call("read_block_attributes")["data"]["blocks"][0]["attributes"]["LINHA"] == "OUTRA"


def test_update_dry_run_writes_nothing_and_mass_update_needs_confirm_and_one_undo(call, bdoc):
    for i in range(10):
        _insert(call, f"PS-{i}", x=i)
    flt = {"block_name": "SUP-GUIDE", "where": {"TIPO": "guia"}}  # where casa sem diferenciar caixa
    dry = call("update_block_attributes", attributes={"TIPO": "ANCORA"}, filter=flt, dry_run=True)
    assert dry["ok"] and dry["data"]["matched"] == 10 and dry["data"]["to_change"] == 10 and not dry["data"]["applied"]
    assert all(b["attributes"]["TIPO"] == "GUIA" for b in call("read_block_attributes")["data"]["blocks"])
    blocked = call("update_block_attributes", attributes={"TIPO": "ANCORA"}, filter=flt)
    assert not blocked["ok"] and blocked["error"]["code"] == "confirmation_required"
    assert blocked["error"]["details"]["to_change"] == 10
    groups_before = len(bdoc.journal.groups)
    done = call("update_block_attributes", attributes={"TIPO": "ANCORA"}, filter=flt, confirm=True)
    assert done["ok"] and done["data"]["applied"] and done["data"]["to_change"] == 10
    assert len(bdoc.journal.groups) == groups_before + 1  # lote inteiro = 1 passo de undo
    assert all(b["attributes"]["TIPO"] == "ANCORA" for b in call("read_block_attributes")["data"]["blocks"])
    assert bdoc.ctrl_z()
    assert all(b["attributes"]["TIPO"] == "GUIA" for b in call("read_block_attributes")["data"]["blocks"])


def test_update_argument_validation_and_noop(call, bdoc):
    h = _insert(call, "PS-1")["data"]["block"]["handle"]
    assert call("update_block_attributes", attributes={"A": "1"})["error"]["code"] == "invalid_parameter"
    assert call("update_block_attributes", attributes={"A": "1"}, handle=h, filter={"layer": "X"})["error"]["code"] == "invalid_parameter"
    assert call("update_block_attributes", attributes={}, handle=h)["error"]["code"] == "invalid_parameter"
    assert call("update_block_attributes", attributes={"A": "1"}, filter={"blok": "x"})["error"]["code"] == "invalid_parameter"
    same = call("update_block_attributes", attributes={"TAG": "PS-1"}, handle=h)
    assert same["ok"] and same["data"]["to_change"] == 0 and same["data"]["unchanged"] == 1
    line = bdoc.model.AddLine([0, 0, 0], [1, 1, 0])
    assert call("update_block_attributes", attributes={"TAG": "x"}, handle=line.Handle)["error"]["code"] == "invalid_parameter"
    unk = call("update_block_attributes", attributes={"ZZZ": "1"}, handle=h)
    assert unk["ok"] and any("ZZZ" in w for w in unk["warnings"])
