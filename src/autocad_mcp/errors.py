"""Exceções de domínio e mapeamento de erros COM do AutoCAD.

Cada exceção carrega um `code` estável que vai para `error.code` na resposta JSON.
"""

from __future__ import annotations

from typing import Any

from autocad_mcp._com import com_error

# HRESULTs relevantes (comparados como inteiros SEM sinal — ver `_hresult`)
RPC_E_CALL_REJECTED = 0x80010001         # -2147418111: AutoCAD ocupado (regra 4)
RPC_E_SERVERCALL_RETRYLATER = 0x8001010A  # -2147417846
RPC_E_DISCONNECTED = 0x80010108          # -2147417848: canal COM morto
CO_E_OBJNOTCONNECTED = 0x800401FD        # -2147220995
RPC_S_SERVER_UNAVAILABLE = 0x800706BA    # -2147023174
MK_E_UNAVAILABLE = 0x800401E3            # -2147221021: nada no ROT (AutoCAD fechado)

_BUSY_TEXTS = ("call was rejected by callee", "chamada foi rejeitada", "llamada rechazada")
_DISCONNECT_TEXTS = ("disconnected from its clients", "servidor rpc não está disponível",
                     "the rpc server is unavailable")


class AutoCadMcpError(Exception):
    """Erro base do servidor."""

    code = "error"

    def __init__(self, message: str, *, details: Any = None) -> None:
        super().__init__(message)
        self.details = details


class AutoCadNotRunningError(AutoCadMcpError):
    code = "autocad_not_running"


class AutoCadBusyError(AutoCadMcpError):
    code = "autocad_busy"


class DocumentError(AutoCadMcpError):
    code = "document_error"


class EntityNotFoundError(AutoCadMcpError):
    code = "entity_not_found"


class InvalidParameterError(AutoCadMcpError):
    code = "invalid_parameter"


class ConfirmationRequiredError(AutoCadMcpError):
    """Operação destrutiva sem confirm=true. `details` traz a prévia do que seria feito."""

    code = "confirmation_required"


class OperationBlockedError(AutoCadMcpError):
    code = "operation_blocked"


class ExcelIntegrationError(AutoCadMcpError):
    code = "excel_error"


class LispDisabledError(AutoCadMcpError):
    code = "lisp_disabled"


def _hresult(err: BaseException) -> int:
    """HRESULT sem sinal (pywin32 entrega com sinal: -2147418111 == 0x80010001)."""
    value = getattr(err, "hresult", None)
    if value is None:
        value = err.args[0] if err.args else 0
    try:
        return int(value) & 0xFFFFFFFF
    except (TypeError, ValueError):
        return 0


def com_error_message(err: BaseException) -> str:
    """Melhor mensagem humana possível de um com_error."""
    args = getattr(err, "args", ())
    strerror = args[1] if len(args) > 1 and isinstance(args[1], str) else None
    excep = args[2] if len(args) > 2 else None
    desc = source = None
    if isinstance(excep, tuple):
        if len(excep) > 2 and isinstance(excep[2], str) and excep[2].strip():
            desc = excep[2].strip()
        if len(excep) > 1 and isinstance(excep[1], str) and excep[1].strip():
            source = excep[1].strip()
    msg = desc or (strerror.strip() if strerror else None) or source or "erro COM desconhecido"
    return f"{msg} (HRESULT {_hresult(err):#010x})"


def is_busy_error(err: BaseException) -> bool:
    """True se o AutoCAD rejeitou a chamada por estar ocupado (RPC_E_CALL_REJECTED)."""
    if not isinstance(err, com_error):
        return False
    if _hresult(err) in (RPC_E_CALL_REJECTED, RPC_E_SERVERCALL_RETRYLATER):
        return True
    text = com_error_message(err).lower()
    return any(t in text for t in _BUSY_TEXTS)


def is_disconnect_error(err: BaseException) -> bool:
    """True se o canal COM morreu (AutoCAD fechado/crash) e é preciso reconectar."""
    if not isinstance(err, com_error):
        return False
    if _hresult(err) in (RPC_E_DISCONNECTED, CO_E_OBJNOTCONNECTED, RPC_S_SERVER_UNAVAILABLE):
        return True
    text = com_error_message(err).lower()
    return any(t in text for t in _DISCONNECT_TEXTS)


def map_com_error(err: BaseException) -> AutoCadMcpError:
    """Converte com_error na exceção de domínio apropriada."""
    if is_busy_error(err):
        return AutoCadBusyError(
            "O AutoCAD está ocupado: a chamada foi rejeitada (RPC_E_CALL_REJECTED) mesmo após "
            "os retries. Finalize o comando ativo (Esc) ou feche o diálogo aberto e tente de novo."
        )
    if is_disconnect_error(err):
        return AutoCadNotRunningError(
            "O canal COM com o AutoCAD foi perdido (AutoCAD fechado ou reiniciado). "
            "Reabra o AutoCAD e chame status() de novo."
        )
    return AutoCadMcpError(f"Falha na chamada COM ao AutoCAD: {com_error_message(err)}")
