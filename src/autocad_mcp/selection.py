"""SelectionSet com filtros DXF (rápido) e fallback de filtragem em Python (lento, mas robusto).

Limitação real da API COM: `SelectionSet.Select` com FilterType/FilterData via dispatch dinâmico falha
em algumas instalações. Nesse caso selecionamos tudo e filtramos em Python, avisando o usuário.
"""

from __future__ import annotations

import fnmatch
import logging
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from autocad_mcp._com import com_error, pythoncom
from autocad_mcp.entity_info import TYPE_ALIASES, block_name, dxf_type
from autocad_mcp.errors import InvalidParameterError
from autocad_mcp.geometry import dxf_filter, dxf_pattern, normalize_bbox, to_variant_point
from autocad_mcp.session import Session, safe_get

log = logging.getLogger("autocad_mcp.selection")

AC_SELECT_WINDOW, AC_SELECT_CROSSING, AC_SELECT_ALL = 0, 1, 5


def expand_types(type_: str | None) -> str | None:
    """'block' → 'INSERT'; 'line,circle' → 'LINE,CIRCLE'. Aceita curingas DXF."""
    if not type_:
        return None
    parts = []
    for raw in type_.split(","):
        t = raw.strip().upper()
        if t:
            parts.append(TYPE_ALIASES.get(t, t))
    return ",".join(parts) or None


class Selection:
    """Resultado de uma seleção: contagem, iteração paginada e filtro Python opcional."""

    def __init__(self, ss: Any, py_filter: Callable[[Any], bool] | None) -> None:
        self._ss = ss
        self._py = py_filter

    @property
    def raw_count(self) -> int:
        return int(self._ss.Count)

    def iter_all(self) -> Iterator[Any]:
        for i in range(self.raw_count):
            ent = self._ss.Item(i)
            if self._py is None or self._py(ent):
                yield ent

    def page(self, offset: int, limit: int) -> tuple[list[Any], int]:
        """(entidades da página, total). Sem filtro Python só toca nos itens da página."""
        if self._py is None:
            total = self.raw_count
            return [self._ss.Item(i) for i in range(offset, min(offset + limit, total))], total
        items = list(self.iter_all())
        return items[offset:offset + limit], len(items)


class ScanSelection(Selection):
    """Varredura direta do ModelSpace em Python. Não cria SelectionSet: no AutoCAD real criar/apagar um
    SelectionSet registra um passo de desfazer vazio (o primeiro Ctrl+Z do usuário não faria nada visível)."""

    def __init__(self, items: list[Any], py_filter: Callable[[Any], bool] | None) -> None:
        super().__init__(None, py_filter)
        self._items = items

    @property
    def raw_count(self) -> int:
        return len(self._items)

    def iter_all(self) -> Iterator[Any]:
        for ent in self._items:
            if self._py is None or self._py(ent):
                yield ent

    def page(self, offset: int, limit: int) -> tuple[list[Any], int]:
        if self._py is None:
            return self._items[offset:offset + limit], len(self._items)
        items = list(self.iter_all())
        return items[offset:offset + limit], len(items)


@contextmanager
def selection(
    s: Session,
    *,
    types: str | None = None,
    layer: str | None = None,
    block: str | None = None,
    bbox: Any = None,
    bbox_mode: str = "window",
    extra_filter: Callable[[Any], bool] | None = None,
) -> Iterator[Selection]:
    """Cria um SelectionSet temporário (nome único), aplica filtros e SEMPRE o apaga ao sair.

    `block` casa pelo nome efetivo (inclui blocos dinâmicos, cujo `Name` é anônimo) — por isso
    é conferido em Python depois de o DXF filtrar por INSERT. Aceita curingas * e ?.
    """
    types = expand_types(types)
    if block and types not in (None, "INSERT"):
        raise InvalidParameterError("block_name só faz sentido com type='INSERT' (ou sem type).")
    if block:
        types = "INSERT"

    pairs: list[tuple[int, Any]] = []
    if types:
        pairs.append((0, types))
    if layer:
        pairs.append((8, dxf_pattern(layer)))

    if bbox is not None:
        p1, p2 = normalize_bbox(bbox)
        if bbox_mode not in ("window", "crossing"):
            raise InvalidParameterError("bbox_mode deve ser 'window' ou 'crossing'.")
        mode = AC_SELECT_WINDOW if bbox_mode == "window" else AC_SELECT_CROSSING
        pts: tuple[Any, Any] = (to_variant_point(p1), to_variant_point(p2))
    else:
        mode, pts = AC_SELECT_ALL, (pythoncom.Missing, pythoncom.Missing)

    block_rx = block.casefold() if block else None

    def py_block_match(ent: Any) -> bool:
        return fnmatch.fnmatchcase(block_name(ent).casefold(), block_rx)  # type: ignore[arg-type]

    def python_filter(ent: Any) -> bool:
        if types:
            wanted = [t.strip() for t in types.split(",")]
            if not any(fnmatch.fnmatchcase(dxf_type(str(safe_get(ent, "ObjectName", default=""))), w) for w in wanted):
                return False
        if layer and not fnmatch.fnmatchcase(str(safe_get(ent, "Layer", default="")).casefold(), layer.casefold()):
            return False
        return True

    ms = s.model_space
    if bbox is None and int(ms.Count) <= s.cfg.scan_threshold:
        # Caminho sem undo fantasma (validado no Plant 3D 2021): itera o ModelSpace e filtra em Python.
        def scan_filter(ent: Any) -> bool:
            if types or layer:
                if not python_filter(ent):
                    return False
            return all(c(ent) for c in ([py_block_match] if block_rx else []) + ([extra_filter] if extra_filter else []))

        yield ScanSelection([ms.Item(i) for i in range(int(ms.Count))], scan_filter)
        return

    s.warn("Desenho grande: usei SelectionSet, que adiciona um passo de desfazer vazio (o 1º Ctrl+Z pode não ter efeito visível).")
    ss = s.doc.SelectionSets.Add("MCP_" + uuid.uuid4().hex[:12])
    try:
        used_python_filter = False

        def plain_select() -> None:
            # Sem filtro: em "select all" os pontos são dispensáveis (nem passamos Missing).
            if mode == AC_SELECT_ALL:
                ss.Select(mode)
            else:
                ss.Select(mode, pts[0], pts[1])

        try:
            if pairs:
                ft, fd = dxf_filter(pairs)
                ss.Select(mode, pts[0], pts[1], ft, fd)
            else:
                plain_select()
        except com_error as exc:
            if not pairs:
                raise
            log.warning("Select com filtro DXF falhou (%s); filtrando em Python", exc)
            s.warn("Filtro DXF indisponível nesta instalação; usei filtragem em Python (mais lenta em desenhos grandes).")
            ss.Clear()
            plain_select()
            used_python_filter = True

        checks: list[Callable[[Any], bool]] = []
        if used_python_filter and (types or layer):
            checks.append(python_filter)
        if block_rx:
            checks.append(py_block_match)
        if extra_filter:
            checks.append(extra_filter)
        combined = (lambda e: all(c(e) for c in checks)) if checks else None
        yield Selection(ss, combined)
    finally:
        try:
            ss.Delete()
        except com_error:
            log.warning("Não consegui apagar o SelectionSet temporário")
