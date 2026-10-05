"""Consulta de entidades: filtro por tipo/camada/bloco/área, e propriedades completas por handle."""

from __future__ import annotations

from typing import Any

from autocad_mcp.entity_info import describe
from autocad_mcp.selection import selection
from autocad_mcp.session import Session
from autocad_mcp.tools._base import com_tool


@com_tool(coords=True, mutates=False)
def query_entities(
    s: Session,
    type: str | None = None,
    layer: str | None = None,
    block_name: str | None = None,
    bbox: list[float] | None = None,
    bbox_mode: str = "window",
    limit: int = 0,
    offset: int = 0,
) -> dict[str, Any]:
    """Busca entidades por filtros (via SelectionSet + códigos DXF) e devolve resumo paginado.

    QUANDO USAR: para "achar" coisas no desenho: todas as linhas da camada X, blocos de um tipo,
    textos numa região. Para propriedades completas use get_entity(handle).
    Parâmetros: type (nome DXF: LINE, CIRCLE, LWPOLYLINE, TEXT, MTEXT, INSERT...; lista com vírgula;
    apelidos: block, polyline), layer (curinga * e ?), block_name (só INSERT; usa o nome efetivo, então
    pega blocos dinâmicos), bbox ([xmin, ymin, xmax, ymax] na unidade do desenho; bbox_mode "window" =
    inteiramente dentro, "crossing" = toca a janela), limit/offset (paginação; limit 0 = padrão).
    Exemplo: query_entities(type="INSERT", block_name="SUP-*", layer="SUPORTES", limit=25).
    """
    lim, off = s.page_args(limit, offset)
    with selection(s, types=type, layer=layer, block=block_name, bbox=bbox, bbox_mode=bbox_mode) as sel:
        items, total = sel.page(off, lim)
        rows = [describe(s, e) for e in items]
    return {"entities": rows, "page": s.page_info(total, off, lim, len(rows))}


@com_tool(coords=True, mutates=False)
def get_entity(s: Session, handle: str) -> dict[str, Any]:
    """Propriedades completas de UMA entidade pelo handle (geometria, cor, tipo de linha, atributos de bloco).

    QUANDO USAR: depois de query_entities/read_block_attributes, para inspecionar um item específico.
    Parâmetros: handle (string hexadecimal, ex. "2F1A"). Exemplo: get_entity("2F1A").
    """
    return {"entity": describe(s, s.find_entity(handle), detail=True)}


TOOLS = [query_entities, get_entity]
