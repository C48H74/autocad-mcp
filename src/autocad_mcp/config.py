"""Configuração (config.toml) e logging (stderr + arquivo rotativo).

REGRA CRÍTICA: stdout é exclusivo do protocolo MCP. Nada neste projeto usa print();
todo log vai para stderr e para logs/server.log (há um teste que varre o código por print()).
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

log = logging.getLogger("autocad_mcp.config")

_VALID_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}
_VALID_BINDINGS = {"dynamic", "gencache"}


@dataclass(frozen=True)
class Config:
    log_level: str = "INFO"
    log_dir: Path | None = None
    log_max_bytes: int = 2_000_000
    log_backups: int = 5
    default_limit: int = 50
    max_limit: int = 500
    max_batch_rows: int = 2000
    enable_lisp: bool = False
    read_only: bool = False
    allow_launch: bool = False
    prog_id: str = "AutoCAD.Application"
    com_binding: str = "dynamic"
    com_timeout_s: float = 120.0
    excel_allowed_dirs: tuple[Path, ...] = field(default_factory=tuple)  # lista única de E/S (ver paths.py)
    allow_any_path: bool = False  # só vale com lista vazia; operador libera todo o disco explicitamente
    scan_threshold: int = 3000  # até N entidades no modelo: varredura em Python (sem undo fantasma); acima: SelectionSet
    audit_log: bool = False  # JSONL em <logs>/audit.jsonl (sem parâmetros); ver audit.py
    profile: str = "full"  # lean | core | full: limita quantas ferramentas o cliente MCP enxerga

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Config:
        """Constrói a Config a partir do dict do TOML, validando e normalizando."""
        server = raw.get("server", {}) or {}
        limits = raw.get("limits", {}) or {}
        excel = raw.get("excel", {}) or {}
        logsec = raw.get("log", {}) or {}

        level = str(logsec.get("level", "INFO")).upper()
        if level not in _VALID_LEVELS:
            log.warning("log.level inválido (%s); usando INFO", level)
            level = "INFO"
        binding = str(server.get("com_binding", "dynamic")).lower()
        if binding not in _VALID_BINDINGS:
            log.warning("server.com_binding inválido (%s); usando dynamic", binding)
            binding = "dynamic"

        max_limit = max(1, int(limits.get("max_limit", 500)))
        default_limit = min(max(1, int(limits.get("default_limit", 50))), max_limit)
        log_dir = logsec.get("dir")
        return cls(
            log_level=level,
            log_dir=Path(log_dir) if log_dir else None,
            log_max_bytes=int(logsec.get("max_bytes", 2_000_000)),
            log_backups=int(logsec.get("backups", 5)),
            default_limit=default_limit,
            max_limit=max_limit,
            max_batch_rows=max(1, int(limits.get("max_batch_rows", 2000))),
            enable_lisp=bool(server.get("enable_lisp", False)),
            read_only=server.get("read_only", False) is not False,
            allow_launch=bool(server.get("allow_launch", False)),
            prog_id=str(server.get("prog_id", "AutoCAD.Application")),
            com_binding=binding,
            com_timeout_s=max(1.0, float(server.get("com_timeout_s", 120.0))),
            excel_allowed_dirs=tuple(Path(p) for p in ((raw.get("paths", {}) or {}).get("allowed_dirs")
                                                       or excel.get("allowed_dirs") or [])),
            allow_any_path=bool((raw.get("paths", {}) or {}).get("allow_any", False)),
            scan_threshold=max(0, int(limits.get("scan_threshold", 3000))),
            audit_log=bool(server.get("audit_log", False)),
            profile=_profile(server.get("profile", "full")),
        )


_VALID_PROFILES = ("lean", "core", "full")


def _profile(value: Any) -> str:
    v = str(value).strip().lower()
    if v not in _VALID_PROFILES:
        log.warning("server.profile inválido (%s); usando full", v)
        return "full"
    return v


def project_root() -> Path | None:
    """Raiz do projeto quando rodando do código-fonte (contém pyproject.toml), senão None."""
    root = Path(__file__).resolve().parents[2]
    return root if (root / "pyproject.toml").is_file() else None


def default_log_dir() -> Path:
    """<projeto>/logs em instalação de desenvolvimento; senão %LOCALAPPDATA%/autocad-mcp/logs.

    Não depende do CWD: o Claude Desktop inicia o servidor com um diretório de trabalho imprevisível.
    """
    root = project_root()
    if root is not None:
        return root / "logs"
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "autocad-mcp" / "logs"


def load_config() -> Config:
    """Ordem de busca: $AUTOCAD_MCP_CONFIG → <projeto>/config.toml → ./config.toml → defaults."""
    candidates: list[Path] = []
    env = os.environ.get("AUTOCAD_MCP_CONFIG")
    if env:
        candidates.append(Path(env))
    root = project_root()
    if root is not None:
        candidates.append(root / "config.toml")
    candidates.append(Path.cwd() / "config.toml")

    raw: dict[str, Any] = {}
    invalid_file = False
    for path in candidates:
        if path.is_file():
            try:
                with path.open("rb") as fh:
                    raw = tomllib.load(fh)
                log.info("Configuração carregada de %s", path)
            except (tomllib.TOMLDecodeError, OSError) as exc:
                invalid_file = True
                log.error("config.toml inválido (%s): %s — usando defaults", path, exc)
            break
    try:
        cfg = Config.from_dict(raw)
    except (TypeError, ValueError, AttributeError) as exc:
        log.error("Valor inválido no config.toml (%s) — usando defaults", exc)
        cfg = Config(read_only=True)
    if invalid_file:
        cfg = replace(cfg, read_only=True)
    env_dirs = os.environ.get("AUTOCAD_MCP_ALLOWED_DIRS", "").strip()
    if env_dirs:
        cfg = replace(cfg, excel_allowed_dirs=tuple(Path(p) for p in env_dirs.split(os.pathsep) if p.strip()))
    if not cfg.excel_allowed_dirs and not cfg.allow_any_path:
        from autocad_mcp.paths import default_workspace  # import tardio: paths importa config

        cfg = replace(cfg, excel_allowed_dirs=(default_workspace(),))
        log.warning("Nenhuma pasta permitida configurada: E/S de arquivos restrita a %s "
                    "([paths].allowed_dirs ou [paths].allow_any=true para mudar).", default_workspace())
    # Operator override survives invalid or missing configuration files.
    if os.environ.get("AUTOCAD_MCP_READ_ONLY", "").strip().lower() in {"1", "true", "yes", "on"}:
        cfg = replace(cfg, read_only=True)
    return cfg


def setup_logging(cfg: Config) -> Path | None:
    """stderr + logs/server.log com rotação. Idempotente. Se o arquivo não for gravável, só stderr."""
    root = logging.getLogger("autocad_mcp")
    root.setLevel(getattr(logging, cfg.log_level, logging.INFO))
    root.handlers.clear()
    root.propagate = False
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")

    stream_h = logging.StreamHandler(sys.stderr)  # NUNCA stdout
    stream_h.setFormatter(fmt)
    root.addHandler(stream_h)

    logfile: Path | None = None
    try:
        log_dir = cfg.log_dir or default_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        logfile = log_dir / "server.log"
        file_h = logging.handlers.RotatingFileHandler(
            logfile, maxBytes=cfg.log_max_bytes, backupCount=cfg.log_backups, encoding="utf-8"
        )
        file_h.setFormatter(fmt)
        root.addHandler(file_h)
    except OSError as exc:
        logfile = None
        root.warning("Sem arquivo de log (%s); seguindo só com stderr", exc)
    return logfile
