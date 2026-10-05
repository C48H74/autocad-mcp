"""Cotas COM, plotagem PDF e XRecord contra o AutoCAD falso (a validação real fica em test_integration)."""
from dataclasses import replace

import pytest


@pytest.fixture
def work(ctx, tmp_path):
    ctx.cfg = replace(ctx.cfg, excel_allowed_dirs=(tmp_path,))
    ctx.conn.cfg = ctx.cfg
    return tmp_path


def test_add_dimension_kinds_and_single_undo(call, doc):
    n0 = len(doc.live())
    r = call("add_dimension", kind="linear", p1=[0, 0], p2=[1500, 0], location=[750, -200])
    assert r["ok"] and r["data"]["measurement"] == pytest.approx(1500)
    assert call("add_dimension", kind="linear", p1=[0, 0], p2=[0, 800], location=[-200, 400], angle_deg=90)["data"]["measurement"] == pytest.approx(800)
    assert call("add_dimension", kind="aligned", p1=[0, 0], p2=[300, 400], location=[100, 300])["data"]["measurement"] == pytest.approx(500)
    assert call("add_dimension", kind="radius", center=[0, 0], radius=60)["data"]["measurement"] == pytest.approx(60)
    assert call("add_dimension", kind="diameter", center=[0, 0], radius=60)["data"]["measurement"] == pytest.approx(120)
    assert call("add_dimension", kind="angular", vertex=[0, 0], p1=[100, 0], p2=[0, 100], location=[50, 50])["ok"]
    assert len(doc.live()) == n0 + 6
    assert doc.ctrl_z() and len(doc.live()) == n0 + 5  # um Ctrl+Z por cota


def test_add_dimension_validates(call):
    assert call("add_dimension", kind="bogus")["error"]["code"] == "invalid_parameter"
    assert call("add_dimension", kind="linear", p1=[0, 0], p2=[1, 1])["error"]["code"] == "invalid_parameter"
    assert call("add_dimension", kind="radius", center=[0, 0], radius=-3)["error"]["code"] == "invalid_parameter"


def test_plot_to_pdf_restores_state_and_respects_overwrite(call, doc, work):
    out = str(work / "s.pdf")
    r = call("plot_to_pdf", path=out, layout="Folha1")
    assert r["ok"] and (work / "s.pdf").read_bytes().startswith(b"%PDF")
    assert doc.vars["BACKGROUNDPLOT"] == 2 and doc.ActiveLayout.Name == "Model"
    assert doc.Layouts.Item("Folha1").ConfigName == "DWG To PDF.pc3"
    assert call("plot_to_pdf", path=out)["error"]["code"] == "invalid_parameter"
    assert call("plot_to_pdf", path=out, overwrite=True)["ok"]
    assert call("plot_to_pdf", path=str(work / "n.pdf"), layout="Nope")["error"]["code"] == "invalid_parameter"
    assert call("plot_to_pdf", path="/etc/x.pdf")["error"]["code"] == "operation_blocked"


def test_project_data_roundtrip(call):
    assert call("project_data_get")["data"]["values"] == {}
    assert call("project_data_set", key="REV", value="B - 2026-10-05")["ok"]
    assert call("project_data_set", key="REV", value="C")["ok"]  # substitui
    assert call("project_data_get", key="REV")["data"]["values"] == {"REV": "C"}
    assert call("project_data_get")["data"]["values"] == {"REV": "C"}
    assert call("project_data_get", key="X")["data"]["values"] == {"X": None}
    assert not call("project_data_set", key="", value="x")["ok"]
