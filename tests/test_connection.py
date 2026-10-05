"""Retry, proxy, worker COM e conexão — com AutoCAD falso."""

import threading

import pytest

from autocad_mcp import connection as C
from autocad_mcp._com import com_error
from autocad_mcp.connection import AutoCadConnection, ComProxy, ComWorker, call_with_retry
from autocad_mcp.errors import (
    AutoCadBusyError,
    AutoCadNotRunningError,
    DocumentError,
    is_busy_error,
    is_disconnect_error,
    map_com_error,
)
from tests.fake_autocad import FakeApp, FakeDoc, busy, disconnected, fail


def test_hresult_signed_and_unsigned_are_recognised_as_busy():
    assert is_busy_error(com_error(-2147418111, "x", None, None))
    assert is_busy_error(com_error(0x80010001, "x", None, None))
    assert is_busy_error(com_error(1, "Call was rejected by callee.", None, None))
    assert not is_busy_error(fail("outro erro"))
    assert not is_busy_error(ValueError("x"))
    assert is_disconnect_error(disconnected())


def test_retry_succeeds_after_transient_busy(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr(C, "_sleep", sleeps.append)
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 4:
            raise busy()
        return "ok"

    assert call_with_retry(flaky) == "ok"
    assert calls["n"] == 4 and sleeps == [0.2, 0.4, 0.8]


def test_retry_gives_up_after_five_retries_with_backoff_0_2_to_3_2(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr(C, "_sleep", sleeps.append)
    calls = {"n": 0}

    def always_busy():
        calls["n"] += 1
        raise busy()

    with pytest.raises(AutoCadBusyError):
        call_with_retry(always_busy)
    assert calls["n"] == 6  # 1 chamada + 5 retries
    assert sleeps == [0.2, 0.4, 0.8, 1.6, 3.2]


def test_retry_does_not_swallow_real_errors():
    with pytest.raises(com_error):
        call_with_retry(lambda: (_ for _ in ()).throw(fail("boom")))


def test_proxy_retries_property_reads_and_method_calls(app):
    app.reject_next(2)
    proxy = ComProxy(app)
    assert proxy.Name == "AutoCAD"  # 2 rejeições absorvidas
    doc = proxy.ActiveDocument
    assert isinstance(doc, ComProxy) and doc.Name == "SUPORTES-01.dwg"
    line = doc.ModelSpace.AddLine([0, 0, 0], [3, 4, 0])  # método retornando objeto COM
    assert isinstance(line, ComProxy) and line.Length == pytest.approx(5.0)


def test_proxy_unwraps_proxies_passed_as_arguments(app):
    proxy = ComProxy(app)
    doc = proxy.ActiveDocument
    ss = doc.SelectionSets.Add("X")
    assert ss.Name == "X"
    doc.SelectionSets.Item("X").Delete()


def test_worker_runs_all_jobs_on_one_dedicated_thread():
    w = ComWorker()
    names = set()
    threads = [threading.Thread(target=lambda: names.add(w.submit(lambda: threading.current_thread().name))) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert names == {"autocad-com"}
    w.shutdown()


def test_worker_reentrancy_does_not_deadlock():
    w = ComWorker()
    assert w.submit(lambda: w.submit(lambda: 42), timeout=2) == 42
    w.shutdown()


def test_worker_timeout_reports_probable_modal_dialog():
    w = ComWorker()
    gate = threading.Event()
    w_thread_job = threading.Thread(target=lambda: w.submit(gate.wait))
    w_thread_job.start()
    while not w.thread.is_alive():
        pass
    with pytest.raises(AutoCadBusyError, match="modal"):
        w.submit(lambda: 1, timeout=0.3)
    gate.set()
    w_thread_job.join()
    w.shutdown()


def test_connection_fails_cleanly_when_autocad_is_closed(cfg):
    def factory(_cfg):
        raise AutoCadNotRunningError("AutoCAD não está aberto")

    conn = AutoCadConnection(cfg, app_factory=factory)
    with pytest.raises(AutoCadNotRunningError, match="não está aberto"):
        conn.run(lambda s: s.doc.Name)
    conn.close()


def test_connection_reconnects_after_disconnect(cfg):
    first, second = FakeApp([FakeDoc("A.dwg")]), FakeApp([FakeDoc("B.dwg")])
    apps = iter([first, second])
    conn = AutoCadConnection(cfg, app_factory=lambda _c: next(apps))
    assert conn.run(lambda s: s.doc.Name) == "A.dwg"
    first.dead = True
    assert conn.run(lambda s: s.doc.Name) == "B.dwg"  # sonda detecta canal morto e reconecta
    conn.close()


def test_connection_busy_probe_is_retried_transparently(cfg, app):
    conn = AutoCadConnection(cfg, app_factory=lambda _c: app)
    conn.run(lambda s: None)
    app.reject_next(3)
    assert conn.run(lambda s: s.doc.Name) == "SUPORTES-01.dwg"
    conn.close()


def test_no_document_open_is_a_clean_error(cfg):
    empty = FakeApp([FakeDoc()])
    empty.docs = []
    conn = AutoCadConnection(cfg, app_factory=lambda _c: empty)
    with pytest.raises(DocumentError, match="Nenhum desenho"):
        conn.run(lambda s: s.doc)
    assert conn.run(lambda s: "ok", needs_doc=False) == "ok"
    conn.close()


def test_map_com_error_generic():
    e = map_com_error(fail("Nome inválido"))
    assert "Nome inválido" in str(e)
