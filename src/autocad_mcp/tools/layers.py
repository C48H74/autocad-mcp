"""Camadas: listar, criar e checar padrão."""

from __future__ import annotations

import fnmatch
from typing import Any

from autocad_mcp._com import com_error
from autocad_mcp.entity_info import dxf_type
from autocad_mcp.errors import InvalidParameterError
from autocad_mcp.selection import selection
from autocad_mcp.session import Session, safe_get, safe_set
from autocad_mcp.tools._base import com_tool

_COLOR_NAMES = {
    "red": 1, "vermelho": 1, "yellow": 2, "amarelo": 2, "green": 3, "verde": 3, "cyan": 4, "ciano": 4,
    "blue": 5, "azul": 5, "magenta": 6, "white": 7, "branco": 7, "black": 7, "preto": 7,
}


def _parse_color(color: int | str) -> int:
    if isinstance(color, str):
        c = color.strip().casefold()
        if c in _COLOR_NAMES:
            return _COLOR_NAMES[c]
        if not c.isdigit():
            raise InvalidParameterError(f"Cor inválida: {color!r}. Use 1-255 ou {sorted(set(_COLOR_NAMES))}.")
        color = int(c)
    if not 1 <= int(color) <= 255:
        raise InvalidParameterError("Cor deve estar entre 1 e 255 (índice ACI).")
    return int(color)


def _layer_info(lay: Any) -> dict[str, Any]:
    return {
        "name": str(lay.Name),
        "color": safe_get(lay, "Color", default=None),
        "linetype": safe_get(lay, "Linetype", default=None),
        "on": bool(safe_get(lay, "LayerOn", default=True)),
        "frozen": bool(safe_get(lay, "Freeze", default=False)),
        "locked": bool(safe_get(lay, "Lock", default=False)),
        "plottable": bool(safe_get(lay, "Plottable", default=True)),
        "description": str(safe_get(lay, "Description", default="") or ""),
    }


@com_tool(mutates=False)
def list_layers(s: Session, name_filter: str | None = None, limit: int = 0, offset: int = 0) -> dict[str, Any]:
    """Lista as camadas do desenho: nome, cor (ACI), tipo de linha, ligada, congelada, bloqueada.

    QUANDO USAR: para conhecer a estrutura de camadas antes de desenhar, inserir blocos ou checar padrão.
    Parâmetros: name_filter (curinga * e ?, ex. "PIPE-*"; opcional), limit (0 = padrão do servidor),
    offset (paginação). Exemplo: list_layers(name_filter="SUP*", limit=20).
    """
    lim, off = s.page_args(limit, offset)
    layers = s.doc.Layers
    items = [_layer_info(layers.Item(i)) for i in range(int(layers.Count))]
    if name_filter:
        pat = name_filter.casefold()
        items = [x for x in items if fnmatch.fnmatchcase(x["name"].casefold(), pat)]
    items.sort(key=lambda x: x["name"].casefold())
    page = items[off:off + lim]
    return {"layers": page, "page": s.page_info(len(items), off, lim, len(page))}


@com_tool()
def create_layer(s: Session, name: str, color: int | str = 7, linetype: str = "Continuous") -> dict[str, Any]:
    """Cria uma camada (se já existir, não altera nada e avisa).

    QUANDO USAR: antes de desenhar/inserir em uma camada nova. Não é destrutivo.
    Parâmetros: name (sem < > / \\ " : ; ? * | , = `), color (índice ACI 1-255 ou nome: red/vermelho,
    yellow, green, cyan, blue, magenta, white), linetype (deve estar carregado; HIDDEN/CENTER/DASHED/PHANTOM
    são carregados de acad.lin automaticamente). Exemplo: create_layer("SUPORTES", color="green", linetype="Continuous").
    """
    n = s.validate_layer_name(name)
    aci = _parse_color(color)
    existing = {x.casefold(): x for x in s.layer_names()}
    if n.casefold() in existing:
        s.warn(f"A camada '{existing[n.casefold()]}' já existe; nada foi alterado.")
        return {"created": False, "name": existing[n.casefold()]}
    lt = (linetype or "Continuous").strip()
    linetypes = s.doc.Linetypes
    try:
        linetypes.Item(lt)
    except com_error:  # COM: chave não encontrada → tenta carregar de acad.lin
        try:
            linetypes.Load(lt, "acad.lin")
        except com_error as exc:
            raise InvalidParameterError(
                f"Tipo de linha '{lt}' não está carregado e não foi encontrado em acad.lin."
            ) from exc
    with s.undo_mark():
        lay = s.doc.Layers.Add(n)
        safe_set(lay, ("Color",), aci)
        safe_set(lay, ("Linetype",), lt)
    return {"created": True, "layer": _layer_info(lay)}


@com_tool(coords=False, mutates=False)
def check_layer_standard(
    s: Session, allowed_layers: list[str], ignore_layers: list[str] | None = None, limit: int = 20
) -> dict[str, Any]:
    """Relata entidades do espaço modelo em camadas FORA do padrão informado (não altera nada).

    QUANDO USAR: auditoria de desenho antes da entrega ("tem algo fora das camadas do padrão?").
    Parâmetros: allowed_layers (nomes ou padrões com * e ?, ex. ["PIPE-*", "SUPORTES"]),
    ignore_layers (padrão ["0", "Defpoints"]), limit (máx. de entidades de amostra por camada).
    Retorna, por camada fora do padrão: contagem, tipos e handles de amostra; e as camadas do padrão que
    não existem no desenho. Não verifica o conteúdo interno de blocos.
    Exemplo: check_layer_standard(["PIPE-*", "SUPORTES", "EIXOS"]).
    """
    if not allowed_layers:
        raise InvalidParameterError("Informe ao menos uma camada/padrão em allowed_layers.")
    allowed = [a.casefold() for a in allowed_layers]
    ignored = [i.casefold() for i in (ignore_layers if ignore_layers is not None else ["0", "Defpoints"])]
    sample_n = max(0, min(int(limit), s.cfg.max_limit))

    def matches(name: str, patterns: list[str]) -> bool:
        return any(fnmatch.fnmatchcase(name.casefold(), p) for p in patterns)

    names = s.layer_names()
    offending, total_entities = [], 0
    for name in sorted(names, key=str.casefold):
        if matches(name, allowed) or matches(name, ignored):
            continue
        with selection(s, layer=name) as sel:
            items, total = sel.page(0, sample_n)
            if total == 0:
                continue
            types: dict[str, int] = {}
            sample = []
            for ent in items:
                t = dxf_type(str(safe_get(ent, "ObjectName", default="")))
                types[t] = types.get(t, 0) + 1
                sample.append({"handle": str(ent.Handle), "type": t})
        total_entities += total
        offending.append({"layer": name, "entity_count": total, "types_in_sample": types, "sample": sample})

    existing = {n.casefold() for n in names}
    missing = [a for a in allowed_layers if not any(c in a for c in "*?") and a.casefold() not in existing]
    return {
        "compliant": not offending,
        "offending_layers": offending,
        "offending_entity_total": total_entities,
        "standard_layers_missing_in_drawing": missing,
        "note": "Só o espaço modelo é verificado; entidades dentro de definições de bloco não são analisadas.",
    }


TOOLS = [list_layers, create_layer, check_layer_standard]
