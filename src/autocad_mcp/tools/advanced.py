"""Escape avançado: AutoLISP via SendCommand (desligado por padrão)."""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from autocad_mcp.errors import InvalidParameterError, LispDisabledError
from autocad_mcp.session import Session
from autocad_mcp.tools._base import com_tool

log = logging.getLogger("autocad_mcp.lisp")
_MAX_LEN = 2000
# Defesa em profundidade (contornável): funções que tocam arquivos, registro, processos e COM externo.
_BLOCKED = re.compile(
    r"(?:\b(?:vl-file-delete|vl-file-rename|vl-file-copy|vl-mkdir|vl-registry-write|vl-registry-delete|startapp|"
    r"vlax-create-object|vlax-get-or-create-object|arxload|dos_[a-z0-9_]+)\b|\(\s*load\s)",
    re.IGNORECASE,
)


def paren_balance_ok(expr: str) -> bool:
    """Parênteses balanceados, ignorando strings "..." (com \\") e comentários ; até o fim."""
    depth, in_str, esc = 0, False, False
    for ch in expr:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == ";":
            break
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0 and not in_str


@com_tool()
def run_lisp(s: Session, expression: str, confirm: bool = False, wait_seconds: float = 3.0) -> dict[str, Any]:
    """Executa UMA expressão AutoLISP no AutoCAD via SendCommand. Desligado por padrão (enable_lisp no config.toml).

    QUANDO USAR: só quando nenhuma outra ferramenta faz o serviço (ex.: comando específico do Plant 3D).
    LIMITAÇÕES REAIS: SendCommand é ASSÍNCRONO e NÃO devolve o resultado do LISP — para ler um valor, faça o LISP
    gravá-lo em uma variável de sistema (SETVAR "USERS1" ...) e leia com outra ferramenta/no AutoCAD; não entra
    no agrupamento de undo do servidor (o AutoCAD cria o próprio passo). Exige confirm=true; expressão em uma
    linha, ≤ 2000 caracteres, parênteses balanceados; funções de arquivo/registro/processo são bloqueadas
    (defesa parcial, não é sandbox). Toda execução é registrada no log.
    Parâmetros: expression, confirm, wait_seconds (espera até 30 s o AutoCAD ficar ocioso).
    Exemplo: run_lisp('(setvar "USERS1" (rtos (getvar "DIMSCALE")))', confirm=true).
    """
    if not s.cfg.enable_lisp:
        raise LispDisabledError(
            "run_lisp está desabilitado. Defina `enable_lisp = true` em [server] no config.toml e reinicie o servidor."
        )
    expr = (expression or "").strip()
    if not expr:
        raise InvalidParameterError("expression vazia.")
    if len(expr) > _MAX_LEN:
        raise InvalidParameterError(f"expression excede {_MAX_LEN} caracteres.")
    if re.search(r"[\r\n\x00-\x08\x0b\x0c\x0e-\x1f]", expr):
        raise InvalidParameterError("expression deve ter uma única linha, sem caracteres de controle.")
    if not expr.startswith(("(", "!")):
        raise InvalidParameterError("expression deve ser uma forma LISP: começar com '(' (ou '!' para ler variável).")
    if not paren_balance_ok(expr):
        raise InvalidParameterError("Parênteses/aspas desbalanceados na expressão.")
    hit = _BLOCKED.search(expr)
    if hit:
        raise InvalidParameterError(f"Função bloqueada em run_lisp: '{hit.group(0).strip()}'.")
    s.require_confirm(confirm, "executar AutoLISP arbitrário", {"expression": expr})
    s.assert_writable()
    log.warning("run_lisp executando: %s", expr)
    s.doc.SendCommand(expr + "\n")
    deadline = time.monotonic() + max(0.0, min(float(wait_seconds), 30.0))
    completed = s.active_command() is None
    while not completed and time.monotonic() < deadline:
        time.sleep(0.1)
        completed = s.active_command() is None
    if not completed:
        s.warn("O AutoCAD ainda estava processando ao fim da espera (SendCommand é assíncrono).")
    return {"sent": expr, "completed": completed,
            "note": "SendCommand não retorna valores; o resultado do LISP não é capturado."}


TOOLS = [run_lisp]
