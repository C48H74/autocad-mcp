"""Resolução e restrição de caminhos de arquivo (DXF, PDF, imagens, planilhas).

Uma única lista de pastas permitidas (`[paths].allowed_dirs`, com `[excel].allowed_dirs` como alias legado)
vale para toda E/S de arquivos do servidor. No uso real (`load_config`) a lista nunca fica vazia por acidente:
sem configuração, só a pasta de trabalho `~/autocad-mcp-workspace` é aceita; liberar tudo exige
`[paths].allow_any = true` (decisão explícita do operador).
"""

from __future__ import annotations

import os
from pathlib import Path

from autocad_mcp.config import Config
from autocad_mcp.errors import InvalidParameterError, OperationBlockedError

WORKSPACE_ENV = "AUTOCAD_MCP_WORKSPACE"


def default_workspace() -> Path:
    env = os.environ.get(WORKSPACE_ENV)
    return Path(env) if env else Path.home() / "autocad-mcp-workspace"


def resolve_path(path: str, cfg: Config, *, write: bool, suffixes: tuple[str, ...] | None = None,
                 must_exist: bool | None = None) -> Path:
    """Expande, normaliza e valida `path`. Levanta erro de domínio claro; nunca devolve caminho fora da lista."""
    if not path or not str(path).strip():
        raise InvalidParameterError("Informe o caminho do arquivo.")
    p = Path(os.path.expandvars(os.path.expanduser(str(path).strip()))).resolve()
    if suffixes and p.suffix.lower() not in suffixes:
        raise InvalidParameterError(f"Extensão '{p.suffix}' não suportada aqui; use uma de {list(suffixes)}.")
    allowed = cfg.excel_allowed_dirs
    if allowed and not any(p.is_relative_to(d.resolve()) for d in allowed):
        raise OperationBlockedError(
            f"Caminho fora das pastas permitidas ([paths].allowed_dirs): {[str(d) for d in allowed]}"
        )
    exists_required = (not write) if must_exist is None else must_exist
    if write:
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise InvalidParameterError(f"Não consegui criar a pasta de destino: {exc}") from exc
    if exists_required and not p.is_file():
        raise InvalidParameterError(f"Arquivo não encontrado: {p}")
    return p
