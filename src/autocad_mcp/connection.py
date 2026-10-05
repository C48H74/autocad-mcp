"""Conexão COM: retry com backoff, proxy que aplica o retry a TODA chamada, worker de thread única.

Decisões (todas explicadas porque a API COM impõe limitações reais):

* Uma única thread COM (`ComWorker`) faz CoInitialize/CoUninitialize e executa todo acesso ao
  AutoCAD. O FastMCP roda ferramentas em threads variadas; objetos COM de um apartment STA só
  podem ser usados na thread que os criou.
* RPC_E_CALL_REJECTED acontece ANTES de a chamada executar (o AutoCAD recusa a entrada), então
  repetir a chamada individual não duplica escritas. Por isso o retry é *por chamada* (via
  `ComProxy`), nunca por job inteiro.
* Diálogo modal aberto no AutoCAD bloqueia a chamada COM sem devolver erro: só o timeout de
  `submit()` detecta isso. A thread worker fica presa até o AutoCAD responder — jobs seguintes
  esperam na fila (ver troubleshooting no README).
"""

from __future__ import annotations

import concurrent.futures
import logging
import queue
import threading
import time
from collections.abc import Callable
from typing import Any, TypeVar

from autocad_mcp._com import HAS_PYWIN32, com_error, pythoncom, pywintypes, win32client
from autocad_mcp.config import Config
from autocad_mcp.errors import (
    MK_E_UNAVAILABLE,
    AutoCadBusyError,
    AutoCadMcpError,
    AutoCadNotRunningError,
    DocumentError,
    _hresult,
    is_busy_error,
    is_disconnect_error,
    map_com_error,
)

log = logging.getLogger("autocad_mcp.connection")
T = TypeVar("T")

#: Espera (s) antes de cada nova tentativa: 1 chamada + 5 retries, de 0.2s até 3.2s.
RETRY_DELAYS: tuple[float, ...] = (0.2, 0.4, 0.8, 1.6, 3.2)
_sleep = time.sleep  # substituível nos testes


def call_with_retry(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Executa `fn`; se o AutoCAD rejeitar por ocupado, repete com backoff exponencial."""
    total = len(RETRY_DELAYS) + 1
    for attempt in range(total):
        try:
            return fn(*args, **kwargs)
        except com_error as exc:
            if not is_busy_error(exc):
                raise
            if attempt == total - 1:
                raise map_com_error(exc) from exc
            delay = RETRY_DELAYS[attempt]
            log.warning("AutoCAD ocupado (tentativa %d/%d); repetindo em %.1fs", attempt + 1, total, delay)
            _sleep(delay)
    raise AssertionError("inalcançável")  # pragma: no cover


# --- Proxy com retry ---------------------------------------------------------------------------
def is_com(obj: Any) -> bool:
    """Objeto COM (CDispatch/gen_py têm `_oleobj_`; os fakes de teste marcam `_is_com_`)."""
    return hasattr(obj, "_oleobj_") or getattr(obj, "_is_com_", False) is True


def _unwrap(value: Any) -> Any:
    if isinstance(value, ComProxy):
        return object.__getattribute__(value, "_o")
    if isinstance(value, list):
        return [_unwrap(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_unwrap(v) for v in value)
    return value


def _wrap(value: Any) -> Any:
    if isinstance(value, ComProxy):
        return value
    if is_com(value):
        return ComProxy(value)
    if isinstance(value, (tuple, list)):
        if value and any(is_com(v) for v in value):
            return tuple(_wrap(v) for v in value)
        return value
    if callable(value) and not isinstance(value, type):
        def method(*args: Any, **kwargs: Any) -> Any:
            return _wrap(call_with_retry(value, *_unwrap(args), **{k: _unwrap(v) for k, v in kwargs.items()}))

        return method
    return value


class ComProxy:
    """Envolve um objeto COM: toda leitura/escrita/chamada passa por `call_with_retry`."""

    __slots__ = ("_o",)

    def __init__(self, obj: Any) -> None:
        object.__setattr__(self, "_o", obj)

    @property
    def raw(self) -> Any:
        return object.__getattribute__(self, "_o")

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        return _wrap(call_with_retry(getattr, self.raw, name))

    def __setattr__(self, name: str, value: Any) -> None:
        call_with_retry(setattr, self.raw, name, _unwrap(value))

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return _wrap(call_with_retry(self.raw, *_unwrap(args), **{k: _unwrap(v) for k, v in kwargs.items()}))

    def __repr__(self) -> str:
        return f"<ComProxy {type(self.raw).__name__}>"


# --- Worker de thread única --------------------------------------------------------------------
class ComWorker:
    """Uma thread dedicada: CoInitialize na entrada, CoUninitialize na saída, fila de jobs."""

    def __init__(self, name: str = "autocad-com") -> None:
        self._q: queue.Queue[tuple[concurrent.futures.Future[Any], Callable[[], Any]] | None] = queue.Queue()
        self._thread = threading.Thread(target=self._run, name=name, daemon=True)
        self._start_lock = threading.Lock()

    @property
    def thread(self) -> threading.Thread:
        return self._thread

    def _ensure_started(self) -> None:
        with self._start_lock:
            if not self._thread.is_alive() and not self._thread.ident:
                self._thread.start()

    def _run(self) -> None:
        pythoncom.CoInitialize()
        log.debug("Worker COM iniciado (CoInitialize)")
        try:
            while True:
                item = self._q.get()
                if item is None:
                    break
                fut, fn = item
                if not fut.set_running_or_notify_cancel():
                    continue
                try:
                    fut.set_result(fn())
                except BaseException as exc:  # noqa: BLE001 - repassa ao chamador
                    fut.set_exception(exc)
        finally:
            pythoncom.CoUninitialize()
            log.debug("Worker COM encerrado (CoUninitialize)")

    def submit(self, fn: Callable[[], T], timeout: float | None = None) -> T:
        """Executa `fn` na thread COM e espera o resultado."""
        if threading.current_thread() is self._thread:  # reentrância: evita deadlock
            return fn()
        self._ensure_started()
        fut: concurrent.futures.Future[T] = concurrent.futures.Future()
        self._q.put((fut, fn))
        try:
            return fut.result(timeout)
        except concurrent.futures.TimeoutError as exc:
            fut.cancel()
            raise AutoCadBusyError(
                f"Timeout de {timeout:.0f}s esperando o AutoCAD. Provável diálogo modal aberto ou comando "
                "longo em execução: feche o diálogo/pressione Esc no AutoCAD. Chamadas seguintes ficam na "
                "fila até o AutoCAD voltar a responder."
            ) from exc

    def shutdown(self) -> None:
        if self._thread.is_alive():
            self._q.put(None)
            self._thread.join(timeout=5)


# --- Conexão -----------------------------------------------------------------------------------
AppFactory = Callable[[Config], Any]


def default_app_factory(cfg: Config) -> Any:
    """Anexa ao AutoCAD já aberto (ROT). Só inicia um novo se `allow_launch=true`."""
    if not HAS_PYWIN32:
        raise AutoCadNotRunningError(
            "pywin32 não está disponível (este servidor só funciona no Windows com `pip install pywin32`)."
        )
    try:
        clsid = pywintypes.IID(cfg.prog_id)
    except com_error as exc:
        raise AutoCadNotRunningError(
            f"ProgID '{cfg.prog_id}' não está registrado no Windows: o AutoCAD está instalado? "
            "Ajuste `server.prog_id` no config.toml."
        ) from exc
    try:
        unk = pythoncom.GetActiveObject(clsid)
        dispatch = unk.QueryInterface(pythoncom.IID_IDispatch)
        log.info("Anexado ao AutoCAD em execução (%s)", cfg.prog_id)
    except com_error as exc:
        if _hresult(exc) != MK_E_UNAVAILABLE and not is_disconnect_error(exc):
            raise map_com_error(exc) from exc
        if not cfg.allow_launch or cfg.read_only:
            raise AutoCadNotRunningError(
                "AutoCAD não está aberto. Abra o AutoCAD (e um desenho) e tente de novo; "
                "ou defina `allow_launch = true` no config.toml para o servidor iniciá-lo."
            ) from exc
        log.info("AutoCAD fechado; iniciando (allow_launch=true)")
        dispatch = win32client.Dispatch(cfg.prog_id)
        dispatch.Visible = True
        return dispatch
    if cfg.com_binding == "gencache":
        try:
            tlb = dispatch.GetTypeInfo().GetContainingTypeLib()[0]
            attr = tlb.GetLibAttr()
            win32client.gencache.EnsureModule(attr[0], attr[1], attr[3], attr[4])
            return win32client.Dispatch(dispatch)
        except Exception as exc:  # noqa: BLE001 - cache gen_py é best-effort
            log.warning("gencache indisponível (%s); usando dispatch dinâmico", exc)
    return win32client.dynamic.Dispatch(dispatch)


class AutoCadConnection:
    """Mantém a referência ao AutoCAD e entrega `Session`s — SEMPRE dentro da thread COM."""

    def __init__(self, cfg: Config, app_factory: AppFactory | None = None) -> None:
        self.cfg = cfg
        self._factory = app_factory or default_app_factory
        self._raw_app: Any = None
        self.worker = ComWorker()

    # -- API pública (qualquer thread) --
    def run(self, job: Callable[[Any], T], *, needs_doc: bool = True, timeout: float | None = None) -> T:
        """Roda `job(session)` na thread COM. Erros COM viram exceções de domínio."""
        return self.worker.submit(lambda: self._execute(job, needs_doc), timeout or self.cfg.com_timeout_s)

    def close(self) -> None:
        self.worker.shutdown()

    # -- internos (thread COM) --
    def _execute(self, job: Callable[[Any], T], needs_doc: bool) -> T:
        from autocad_mcp.session import Session  # import tardio: evita ciclo

        try:
            app = ComProxy(self._ensure_app())
            doc = None
            try:
                if app.Documents.Count > 0:
                    doc = app.ActiveDocument
            except com_error as exc:
                if is_disconnect_error(exc):
                    raise
                doc = None
            if needs_doc and doc is None:
                raise DocumentError("Nenhum desenho aberto no AutoCAD. Abra ou crie um desenho e tente de novo.")
            return job(Session(self.cfg, app, doc))
        except com_error as exc:
            if is_disconnect_error(exc):
                log.warning("Canal COM perdido; a próxima chamada reconecta")
                self._raw_app = None
            raise map_com_error(exc) from exc
        except AutoCadMcpError:
            raise

    def _ensure_app(self) -> Any:
        if self._raw_app is not None:
            try:
                _ = call_with_retry(getattr, self._raw_app, "Name")  # sonda de vida
                return self._raw_app
            except com_error as exc:
                if not is_disconnect_error(exc):
                    raise
                log.info("Conexão anterior morta; reconectando")
                self._raw_app = None
        self._raw_app = self._factory(self.cfg)
        return self._raw_app
