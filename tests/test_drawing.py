"""Etapa 5: desenho, edição, run_lisp."""

import pytest

from autocad_mcp.tools.advanced import paren_balance_ok


@pytest.fixture
def ddoc(doc):
    doc.Layers.Add("EIXOS")
    doc.journal.groups.clear()
    return doc


def test_draw_line_layer_units_and_undo(call, ddoc):
    r = call("draw_line", start=[0, 0], end=[3000, 4000], layer="eixos")
    e = r["data"]["entity"]
    assert r["ok"] and e["type"] == "LINE" and e["layer"] == "EIXOS" and e["geometry"]["length"] == 5000.0 and r["data"]["units"] == "mm"
    assert ddoc.model.Count == 1 and ddoc.ctrl_z() and ddoc.model.Count == 0


@pytest.mark.parametrize("tool,kw", [
    ("draw_line", {"start": [0, 0], "end": [0, 0]}),
    ("draw_line", {"start": [0, 0], "end": [1, 1], "layer": "NAO-EXISTE"}),
    ("draw_polyline", {"points": [[0, 0]]}),
    ("draw_polyline", {"points": [[0, 0], [1]]}),
    ("draw_circle", {"center": [0, 0], "radius": 0}),
    ("draw_circle", {"center": [0, 0], "radius": -3}),
    ("add_text", {"text": " ", "point": [0, 0], "height": 2}),
    ("add_text", {"text": "a", "point": [0, 0], "height": 0}),
    ("add_mtext", {"text": "a", "point": [0, 0], "width": 0}),
    ("move_entity", {"handle": "1", "displacement": [1]}),
    ("copy_entity", {"handle": "1", "displacement": [1, 1], "count": 0}),
    ("delete_entities", {"handles": []}),
])
def test_drawing_input_validation(call, ddoc, tool, kw):
    r = call(tool, **kw)
    assert not r["ok"] and r["error"]["code"] in ("invalid_parameter", "entity_not_found")
    assert ddoc.model.Count == 0


def test_polyline_flat_vs_3d_closed_and_elevation(call, ddoc):
    flat = call("draw_polyline", points=[[0, 0, 100], [1000, 0, 100], [1000, 500, 100]], closed=True, layer="EIXOS")
    g = flat["data"]["entity"]["geometry"]
    assert flat["ok"] and flat["data"]["entity"]["type"] == "LWPOLYLINE" and g["closed"] and g["vertex_count"] == 3 and g["elevation"] == 100.0
    p3 = call("draw_polyline", points=[[0, 0, 0], [1000, 0, 500]])
    assert p3["data"]["entity"]["type"] == "POLYLINE" and any("3D" in w for w in p3["warnings"])
    assert p3["data"]["entity"]["geometry"]["vertices"][1] == [1000.0, 0.0, 500.0]


def test_circle_text_mtext(call, ddoc):
    c = call("draw_circle", center=[500, 500], radius=25.4, layer="EIXOS")["data"]["entity"]["geometry"]
    assert c == {"center": [500.0, 500.0, 0.0], "radius": 25.4}
    t = call("add_text", text="PS-101", point=[10, 20], height=3.5, rotation=90)
    assert t["data"]["entity"]["geometry"]["text"] == "PS-101" and ddoc.model.Item(1).Rotation == pytest.approx(1.5707963, rel=1e-6)
    m = call("add_mtext", text="NOTA\\Pdois", point=[0, 0], width=800, height=3)
    assert m["ok"] and m["data"]["entity"]["type"] == "MTEXT" and ddoc.model.Item(2).Height == 3


def test_move_and_copy_array_with_and_without_copy_return_value(call, ddoc):
    h = call("draw_line", start=[0, 0], end=[100, 0])["data"]["entity"]["handle"]
    mv = call("move_entity", handle=h, displacement=[10, 5, 0])
    assert mv["data"]["entity"]["geometry"]["start"] == [10.0, 5.0, 0.0]
    ddoc.journal.groups.clear()
    cp = call("copy_entity", handle=h, displacement=[3000, 0], count=3)
    starts = [c["geometry"]["start"][0] for c in cp["data"]["copies"]]
    assert cp["ok"] and starts == [3010.0, 6010.0, 9010.0] and ddoc.model.Count == 4
    assert ddoc.ctrl_z() and ddoc.model.Count == 1  # 3 cópias + moves = 1 passo
    ddoc.copy_returns_none = True  # quirk real de algumas versões
    cp2 = call("copy_entity", handle=h, displacement=[500, 0])
    assert cp2["ok"] and cp2["data"]["copies"][0]["geometry"]["start"][0] == 510.0 and any("Copy()" in w for w in cp2["warnings"])
    assert call("move_entity", handle="FFFF", displacement=[1, 1])["error"]["code"] == "entity_not_found"


def test_delete_requires_confirm_dry_run_atomic_and_undo(call, ddoc):
    hs = [call("draw_line", start=[i, 0], end=[i, 5])["data"]["entity"]["handle"] for i in range(3)]
    ddoc.journal.groups.clear()
    dry = call("delete_entities", handles=hs, dry_run=True)
    assert dry["ok"] and dry["data"]["would_delete"] == 3 and dry["data"]["deleted"] == 0 and ddoc.model.Count == 3
    blocked = call("delete_entities", handles=hs)
    assert not blocked["ok"] and blocked["error"]["code"] == "confirmation_required" and ddoc.model.Count == 3
    assert blocked["error"]["details"]["would_delete"] == 3
    partial = call("delete_entities", handles=[hs[0], "DEAD"], confirm=True)
    assert not partial["ok"] and partial["error"]["code"] == "entity_not_found" and ddoc.model.Count == 3  # tudo-ou-nada
    done = call("delete_entities", handles=hs + [hs[0].lower()], confirm=True)  # duplicatas ignoradas
    assert done["ok"] and done["data"]["deleted"] == 3 and ddoc.model.Count == 0
    assert ddoc.ctrl_z() and ddoc.model.Count == 3  # um Ctrl+Z restaura os 3


def test_writes_blocked_when_readonly_or_command_active(call, ddoc, app):
    ddoc.ReadOnly = True
    r = call("draw_line", start=[0, 0], end=[1, 1])
    assert not r["ok"] and r["error"]["code"] == "operation_blocked" and "somente leitura" in r["error"]["message"]
    ddoc.ReadOnly = False
    app.set_command("PLINE")
    assert call("draw_circle", center=[0, 0], radius=1)["error"]["code"] == "operation_blocked"
    assert ddoc.model.Count == 0


def test_undo_mark_is_closed_even_when_the_operation_fails(call, ddoc):
    call("draw_line", start=[0, 0], end=[1, 1], layer="NAO-EXISTE")
    assert ddoc.journal.open is None
    assert call("draw_line", start=[0, 0], end=[1, 1])["ok"]  # não ficou marca aberta que quebre a próxima


# --- run_lisp -----------------------------------------------------------------------------------
@pytest.fixture
def lisp_on(ctx):
    from dataclasses import replace

    ctx.cfg = replace(ctx.cfg, enable_lisp=True)
    ctx.conn.cfg = ctx.cfg
    return ctx


def test_run_lisp_disabled_by_default(call, ddoc):
    r = call("run_lisp", expression='(setvar "USERS1" "x")', confirm=True)
    assert not r["ok"] and r["error"]["code"] == "lisp_disabled" and ddoc.sent_commands == []


def test_run_lisp_requires_confirm_validates_and_sends(call, ddoc, lisp_on, app):
    e = '(setvar "USERS1" "ok")'
    assert call("run_lisp", expression=e)["error"]["code"] == "confirmation_required" and ddoc.sent_commands == []
    for bad in ["", "setvar", "(setvar", '(princ "a") (princ "b"\n)', '(vl-file-delete "C:/x")', '(load "x.lsp")',
                '(startapp "calc")', "(" * 3, "(" + "a" * 2100 + ")"]:
        r = call("run_lisp", expression=bad, confirm=True)
        assert not r["ok"] and r["error"]["code"] == "invalid_parameter", bad
    app.polls_after_send = 2  # AutoCAD fica ocupado por 2 sondagens, depois ocioso
    ok = call("run_lisp", expression=e, confirm=True, wait_seconds=2)
    assert ok["ok"] and ok["data"]["completed"] and ddoc.sent_commands == [e + "\n"]
    app.polls_after_send = 10_000
    slow = call("run_lisp", expression=e, confirm=True, wait_seconds=0.3)
    assert slow["ok"] and slow["data"]["completed"] is False and any("assíncrono" in w for w in slow["warnings"])


def test_run_lisp_blocked_by_active_command(call, ddoc, lisp_on, app):
    app.set_command("LINE")
    assert call("run_lisp", expression="(princ)", confirm=True)["error"]["code"] == "operation_blocked"


@pytest.mark.parametrize("expr,ok", [
    ('(princ "a)b")', True), ("(a (b) c)", True), ("(a", False), ("a)", False), (")(", False),
    ('(princ "\\"(")', True), ('(princ "x") ; (comentario', True), ('(princ "aberta)', False),
])
def test_paren_balance(expr, ok):
    assert paren_balance_ok(expr) is ok
