"""Sobe o servidor de verdade (subprocesso, transporte stdio) e conversa JSON-RPC cru.

Prova o critério "nenhuma saída em stdout além do protocolo" e que status() falha de forma limpa
com o AutoCAD fechado (aqui: sem pywin32/AutoCAD → autocad_not_running).
"""

import json
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _spawn(tmp_path: Path):
    logs = tmp_path / "logs"
    cfg = tmp_path / "config.toml"
    cfg.write_text(f"[log]\ndir = '{logs.as_posix()}'\nlevel = 'INFO'\n", encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "AUTOCAD_MCP_CONFIG": str(cfg),
           "AUTOCAD_MCP_WORKSPACE": str(tmp_path / "ws"), "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.Popen(
        [sys.executable, "-m", "autocad_mcp"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", env=env, cwd=tmp_path,  # CWD alheio ao projeto, como no Claude Desktop
    )
    lines: queue.Queue[str] = queue.Queue()
    threading.Thread(target=lambda: [lines.put(l) for l in proc.stdout], daemon=True).start()
    return proc, lines, logs


def _send(proc, msg):
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()


def _collect(lines: queue.Queue, ids: set[int], timeout: float = 40.0):
    got, raw = {}, []
    while ids - got.keys():
        line = lines.get(timeout=timeout)
        raw.append(line)
        msg = json.loads(line)  # QUALQUER linha em stdout que não seja JSON quebra aqui
        assert msg.get("jsonrpc") == "2.0", line
        if "id" in msg:
            got[msg["id"]] = msg
    return got, raw


def test_server_speaks_only_jsonrpc_on_stdout_lists_50_tools_and_status_fails_cleanly(tmp_path):
    proc, lines, logs = _spawn(tmp_path)
    try:
        _send(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "pytest", "version": "0"}}})
        _send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        _send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        _send(proc, {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "status", "arguments": {}}})
        got, raw = _collect(lines, {1, 2, 3})
        assert got[1]["result"]["serverInfo"]["name"] == "autocad-mcp"
        assert len(got[2]["result"]["tools"]) == 50
        payload = json.loads(got[3]["result"]["content"][0]["text"])
        assert set(payload) == {"ok", "data", "warnings", "error"}
        if not payload["ok"]:  # sem AutoCAD/pywin32 (CI, Linux) → falha limpa e explicativa
            assert payload["error"]["code"] == "autocad_not_running" and payload["error"]["message"]
    finally:
        proc.stdin.close()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
    err = proc.stderr.read()
    assert "iniciando (stdio)" in err
    assert (logs / "server.log").is_file() and "iniciando" in (logs / "server.log").read_text(encoding="utf-8")


def test_dxf_tools_over_real_stdio_keep_stdout_clean_and_enforce_workspace(tmp_path):
    proc, lines, _logs = _spawn(tmp_path)
    ws = tmp_path / "ws"
    calls = [
        ("dxf_create", {"path": str(ws / "t.dxf")}),
        ("dxf_add_entities", {"path": str(ws / "t.dxf"), "entities": [{"type": "line", "start": [0, 0], "end": [100, 50]}]}),
        ("dxf_add_dimensions", {"path": str(ws / "t.dxf"), "dimensions": [{"kind": "linear", "p1": [0, 0], "p2": [100, 0], "base": [0, -20]}]}),
        ("dxf_export", {"path": str(ws / "t.dxf"), "output": str(ws / "t.pdf")}),
        ("dxf_info", {"path": str(tmp_path / "fora.dxf")}),
    ]
    try:
        _send(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "pytest", "version": "0"}}})
        _send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        for i, (name, args) in enumerate(calls, start=10):
            _send(proc, {"jsonrpc": "2.0", "id": i, "method": "tools/call", "params": {"name": name, "arguments": args}})
        got, _raw = _collect(lines, {1, *range(10, 10 + len(calls))}, timeout=90.0)
        res = [json.loads(got[i]["result"]["content"][0]["text"]) for i in range(10, 10 + len(calls))]
        assert [r["ok"] for r in res[:4]] == [True] * 4, res
        assert res[4]["error"]["code"] == "operation_blocked"
        assert (ws / "t.pdf").read_bytes().startswith(b"%PDF")
    finally:
        proc.stdin.close()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
