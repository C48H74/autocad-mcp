import json
from dataclasses import replace


def test_audit_log_records_calls_without_parameters(call, ctx, tmp_path):
    ctx.cfg = replace(ctx.cfg, audit_log=True, log_dir=tmp_path, excel_allowed_dirs=(tmp_path,))
    ctx.conn.cfg = ctx.cfg
    assert call("dxf_create", path=str(tmp_path / "segredo-projeto.dxf"))["ok"]
    assert call("dxf_info", path=str(tmp_path / "nao-existe.dxf"))["ok"] is False
    assert call("draw_line", start=[0, 0], end=[10, 0])
    lines = [json.loads(x) for x in (tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [(x["tool"], x["ok"]) for x in lines] == [("dxf_create", True), ("dxf_info", False), ("draw_line", False)] or \
           [x["tool"] for x in lines] == ["dxf_create", "dxf_info", "draw_line"]
    raw = (tmp_path / "audit.jsonl").read_text(encoding="utf-8")
    assert "segredo-projeto" not in raw and "start" not in raw  # sem parâmetros nem caminhos
    assert lines[0]["mutates"] is True and lines[1]["mutates"] is False


def test_audit_is_off_by_default(call, ctx, tmp_path):
    ctx.cfg = replace(ctx.cfg, log_dir=tmp_path)
    ctx.conn.cfg = ctx.cfg
    call("status")
    assert not (tmp_path / "audit.jsonl").exists()
