"""Session: visão do AutoCAD entregue a cada ferramenta (roda sempre na thread COM)."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from autocad_mcp._com import com_error
from autocad_mcp.config import Config
from autocad_mcp.errors import (
    ConfirmationRequiredError,
    DocumentError,
    EntityNotFoundError,
    InvalidParameterError,
    OperationBlockedError,
    com_error_message,
)
from autocad_mcp.geometry import units_name
from autocad_mcp.models import PageInfo

log = logging.getLogger("autocad_mcp.session")
_HANDLE_RE = re.compile(r"^[0-9A-Fa-f]{1,16}$")
_BAD_LAYER_CHARS = set('<>/\\":;?*|,=`')


def safe_get(obj: Any, *names: str, default: Any = None) -> Any:
    """Lê a primeira propriedade COM que existir (typelibs do AutoCAD variam em caixa: Color/color)."""
    for name in names:
        for variant in dict.fromkeys((name, name[:1].lower() + name[1:], name.lower())):
            try:
                return getattr(obj, variant)
            except (AttributeError, com_error):
                continue
    return default


def safe_set(obj: Any, names: tuple[str, ...], value: Any) -> None:
    last: Exception | None = None
    for name in names:
        for variant in dict.fromkeys((name, name[:1].lower() + name[1:], name.lower())):
            try:
                setattr(obj, variant, value)
                return
            except (AttributeError, com_error) as exc:
                last = exc
    raise InvalidParameterError(f"Não foi possível definir {names[0]}: {last}")


class Session:
    def __init__(self, cfg: Config, app: Any, doc: Any) -> None:
        self.cfg = cfg
        self.app = app
        self._doc = doc
        self.warnings: list[str] = []
        self._units: int | None = None
        self._undo_depth = 0

    # -- básicos --
    @property
    def doc(self) -> Any:
        if self._doc is None:
            raise DocumentError("Nenhum desenho aberto no AutoCAD.")
        return self._doc

    @property
    def has_document(self) -> bool:
        return self._doc is not None

    @property
    def model_space(self) -> Any:
        return self.doc.ModelSpace

    def warn(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)

    # -- unidades (regra 8) --
    @property
    def units_code(self) -> int:
        if self._units is None:
            try:
                self._units = int(self.doc.GetVariable("INSUNITS"))
            except (com_error, TypeError, ValueError):
                self._units = 0
                self.warn("Não foi possível ler INSUNITS; unidade tratada como 'sem unidade'.")
        return self._units

    @property
    def units_name(self) -> str:
        return units_name(self.units_code)

    # -- paginação (regra 9) --
    def page_args(self, limit: int | None, offset: int | None) -> tuple[int, int]:
        lim = self.cfg.default_limit if not limit else int(limit)
        off = int(offset or 0)
        if lim < 0 or off < 0:
            raise InvalidParameterError("limit e offset devem ser >= 0")
        if lim > self.cfg.max_limit:
            self.warn(f"limit reduzido de {lim} para o máximo configurado ({self.cfg.max_limit}).")
            lim = self.cfg.max_limit
        return lim, off

    @staticmethod
    def page_info(total: int, offset: int, limit: int, returned: int) -> dict[str, Any]:
        return PageInfo.build(total, offset, limit, returned).model_dump()

    # -- estado do AutoCAD --
    def active_command(self) -> str | None:
        """Nome do comando ativo, ou None se o AutoCAD está quiescente (regra 4)."""
        try:
            if bool(self.app.GetAcadState().IsQuiescent):
                return None
        except (com_error, AttributeError):
            try:
                if int(self.doc.GetVariable("CMDACTIVE")) == 0:
                    return None
            except (com_error, TypeError, ValueError):
                return None
        try:
            names = str(self.doc.GetVariable("CMDNAMES")).strip()
        except (com_error, TypeError):
            names = ""
        return names or "desconhecido"

    def assert_writable(self) -> None:
        if self.cfg.read_only:
            raise OperationBlockedError("Modo somente leitura ativado no servidor.")
        if bool(safe_get(self.doc, "ReadOnly", default=False)):
            raise OperationBlockedError("O desenho está aberto como somente leitura.")
        cmd = self.active_command()
        if cmd:
            raise OperationBlockedError(
                f"Há um comando ativo no AutoCAD ({cmd}). Pressione Esc no AutoCAD e tente novamente."
            )

    # -- undo (regra 6) --
    @contextmanager
    def undo_mark(self) -> Iterator[None]:
        """Agrupa tudo o que ocorrer no bloco em UM passo de Ctrl+Z. Aninhável."""
        if self._undo_depth > 0:
            yield
            return
        self.assert_writable()
        try:
            self.doc.StartUndoMark()
        except com_error as exc:
            raise OperationBlockedError(
                "Não foi possível abrir o grupo de desfazer (StartUndoMark): " + com_error_message(exc)
            ) from exc
        self._undo_depth += 1
        try:
            yield
        finally:
            self._undo_depth -= 1
            try:
                self.doc.EndUndoMark()
            except com_error:
                log.exception("Falha em EndUndoMark")

    # -- confirmação (regra 7) --
    @staticmethod
    def require_confirm(confirm: bool, what: str, preview: Any = None) -> None:
        if not confirm:
            raise ConfirmationRequiredError(
                f"Operação destrutiva/em massa ({what}). Revise a prévia em `error.details` e repita a "
                "chamada com confirm=true (ou use dry_run=true para só simular).",
                details=preview,
            )

    # -- entidades --
    def find_entity(self, handle: str) -> Any:
        if not isinstance(handle, str) or not _HANDLE_RE.match(handle.strip()):
            raise InvalidParameterError(f"Handle inválido: {handle!r} (esperado hexadecimal, ex.: '2F1A')")
        try:
            ent = self.doc.HandleToObject(handle.strip().upper())
        except com_error as exc:
            raise EntityNotFoundError(f"Nenhuma entidade com o handle {handle!r} neste desenho.") from exc
        if ent is None:
            raise EntityNotFoundError(f"Nenhuma entidade com o handle {handle!r} neste desenho.")
        return ent

    # -- camadas --
    def layer_names(self) -> list[str]:
        layers = self.doc.Layers
        return [str(layers.Item(i).Name) for i in range(int(layers.Count))]

    @staticmethod
    def validate_layer_name(name: str) -> str:
        n = (name or "").strip()
        if not n or len(n) > 255 or any(c in _BAD_LAYER_CHARS for c in n):
            raise InvalidParameterError(
                f"Nome de camada inválido: {name!r} (vazio, > 255 caracteres ou contém < > / \\ \" : ; ? * | , = `)"
            )
        return n

    def ensure_layer(self, name: str | None, *, create: bool = False) -> str | None:
        """Valida que a camada existe (ou a cria). Retorna o nome canônico."""
        if not name:
            return None
        n = self.validate_layer_name(name)
        existing = {x.casefold(): x for x in self.layer_names()}
        if n.casefold() in existing:
            return existing[n.casefold()]
        if not create:
            raise InvalidParameterError(
                f"A camada '{n}' não existe. Crie-a com create_layer ou passe create_missing_layer=true."
            )
        self.doc.Layers.Add(n)
        self.warn(f"Camada '{n}' criada automaticamente.")
        return n
