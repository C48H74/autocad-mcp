"""Desenho e edição básica: linhas, polilinhas, círculos, textos, mover/copiar/apagar."""

from __future__ import annotations

from typing import Any

from autocad_mcp.entity_info import describe
from autocad_mcp.errors import EntityNotFoundError, InvalidParameterError
from autocad_mcp.geometry import (
    deg_to_rad,
    flatten_xy,
    flatten_xyz,
    normalize_point,
    to_variant_doubles,
    to_variant_point,
)
from autocad_mcp.session import Session
from autocad_mcp.tools._base import com_tool

_MAX_COPIES = 500


def _place(s: Session, ent: Any, layer: str | None) -> dict[str, Any]:
    if layer:
        ent.Layer = layer
    return {"entity": describe(s, ent)}


def _positive(value: float, name: str) -> float:
    v = float(value)
    if not v > 0 or v == float("inf"):
        raise InvalidParameterError(f"{name} deve ser um número > 0.")
    return v


@com_tool(coords=True)
def draw_line(s: Session, start: list[float], end: list[float], layer: str | None = None) -> dict[str, Any]:
    """Desenha uma linha no espaço modelo. Desfazível com um Ctrl+Z.

    QUANDO USAR: eixos, referências e traçados simples. Parâmetros: start/end ([x, y] ou [x, y, z] na unidade
    do desenho), layer (existente; opcional — sem layer usa a camada ativa). Exemplo: draw_line([0, 0], [1500, 0], layer="EIXOS").
    """
    a, b = normalize_point(start, name="start"), normalize_point(end, name="end")
    if a == b:
        raise InvalidParameterError("start e end são iguais (linha de comprimento zero).")
    lay = s.ensure_layer(layer)
    with s.undo_mark():
        ent = s.model_space.AddLine(to_variant_point(a), to_variant_point(b))
        return _place(s, ent, lay)


@com_tool(coords=True)
def draw_polyline(s: Session, points: list[list[float]], closed: bool = False, layer: str | None = None) -> dict[str, Any]:
    """Desenha uma polilinha por vértices. Todos os Z iguais → polilinha leve 2D (com elevação); Z variados → polilinha 3D.

    QUANDO USAR: contornos, traçados de linha de tubulação em planta, perímetros. Parâmetros: points (≥ 2
    pontos [x, y] ou [x, y, z]), closed (fecha a figura), layer. Exemplo: draw_polyline([[0,0],[1000,0],[1000,500]], closed=true, layer="EIXOS").
    """
    if not isinstance(points, list) or len(points) < 2:
        raise InvalidParameterError("points precisa ter ao menos 2 pontos.")
    pts = [normalize_point(p, name=f"points[{i}]") for i, p in enumerate(points)]
    lay = s.ensure_layer(layer)
    flat_z = len({p[2] for p in pts}) == 1
    with s.undo_mark():
        if flat_z:
            ent = s.model_space.AddLightWeightPolyline(to_variant_doubles(flatten_xy(pts)))
            if pts[0][2] != 0.0:
                ent.Elevation = pts[0][2]
        else:
            ent = s.model_space.Add3DPoly(to_variant_doubles(flatten_xyz(pts)))
            s.warn("Z variado: criada polilinha 3D (AcDb3dPolyline).")
        if closed:
            ent.Closed = True
        return _place(s, ent, lay)


@com_tool(coords=True)
def draw_circle(s: Session, center: list[float], radius: float, layer: str | None = None) -> dict[str, Any]:
    """Desenha um círculo. QUANDO USAR: furos, bocais em planta, marcações.

    Parâmetros: center ([x, y] ou [x, y, z]), radius (> 0, unidade do desenho), layer. Exemplo: draw_circle([500, 500], 25.4, layer="EIXOS").
    """
    c = normalize_point(center, name="center")
    r = _positive(radius, "radius")
    lay = s.ensure_layer(layer)
    with s.undo_mark():
        return _place(s, s.model_space.AddCircle(to_variant_point(c), r), lay)


@com_tool(coords=True)
def add_text(s: Session, text: str, point: list[float], height: float, rotation: float = 0.0, layer: str | None = None) -> dict[str, Any]:
    """Adiciona texto de linha única. QUANDO USAR: rótulos curtos (TAG, cota, nota).

    Parâmetros: text, point (inserção), height (> 0, unidade do desenho), rotation (GRAUS), layer.
    Exemplo: add_text("PS-101", [1250, 830], 3.5, layer="TEXTO").
    """
    if not str(text).strip():
        raise InvalidParameterError("text vazio.")
    p = normalize_point(point, name="point")
    h = _positive(height, "height")
    lay = s.ensure_layer(layer)
    with s.undo_mark():
        ent = s.model_space.AddText(str(text), to_variant_point(p), h)
        if rotation:
            ent.Rotation = deg_to_rad(rotation)
        return _place(s, ent, lay)


@com_tool(coords=True)
def add_mtext(s: Session, text: str, point: list[float], width: float, height: float | None = None, layer: str | None = None) -> dict[str, Any]:
    """Adiciona texto de várias linhas (MText). QUANDO USAR: notas e legendas; use \\P para quebra de linha.

    Parâmetros: text, point (canto de inserção), width (> 0, largura da caixa), height (altura do texto; opcional), layer.
    Exemplo: add_mtext("NOTA 1:\\PVer suporte tipo GUIA", [0, -200], 800, height=3.5, layer="TEXTO").
    """
    if not str(text).strip():
        raise InvalidParameterError("text vazio.")
    p = normalize_point(point, name="point")
    w = _positive(width, "width")
    lay = s.ensure_layer(layer)
    with s.undo_mark():
        ent = s.model_space.AddMText(to_variant_point(p), w, str(text))
        if height:
            ent.Height = _positive(height, "height")
        return _place(s, ent, lay)


@com_tool(coords=True)
def move_entity(s: Session, handle: str, displacement: list[float]) -> dict[str, Any]:
    """Move uma entidade por um vetor de deslocamento. Desfazível com Ctrl+Z.

    QUANDO USAR: reposicionar um item já localizado (query_entities). Parâmetros: handle, displacement ([dx, dy] ou
    [dx, dy, dz], unidade do desenho). Exemplo: move_entity("2F1A", [100, 0, 0]).
    """
    d = normalize_point(displacement, name="displacement")
    ent = s.find_entity(handle)
    with s.undo_mark():
        ent.Move(to_variant_point((0, 0, 0)), to_variant_point(d))
    return {"entity": describe(s, ent)}


@com_tool(coords=True)
def copy_entity(s: Session, handle: str, displacement: list[float], count: int = 1) -> dict[str, Any]:
    """Copia uma entidade `count` vez(es), cada cópia deslocada mais um `displacement` (arranjo linear).

    QUANDO USAR: repetir um item em passo constante (ex. suportes a cada 3000). Máx. 500 cópias.
    Parâmetros: handle, displacement ([dx, dy(, dz)]), count (≥ 1). Exemplo: copy_entity("2F1A", [3000, 0, 0], count=5).
    """
    d = normalize_point(displacement, name="displacement")
    if not 1 <= int(count) <= _MAX_COPIES:
        raise InvalidParameterError(f"count deve estar entre 1 e {_MAX_COPIES}.")
    src = s.find_entity(handle)
    copies = []
    with s.undo_mark():
        for i in range(1, int(count) + 1):
            new = src.Copy()
            if new is None:  # limitação: em algumas versões Copy() não devolve o objeto
                s.warn("Copy() não retornou o objeto nesta versão; usei a última entidade do espaço modelo.")
                ms = s.model_space
                new = ms.Item(int(ms.Count) - 1)
            new.Move(to_variant_point((0, 0, 0)), to_variant_point((d[0] * i, d[1] * i, d[2] * i)))
            copies.append(describe(s, new))
    return {"copies": copies, "count": len(copies)}


@com_tool(coords=False)
def delete_entities(s: Session, handles: list[str], confirm: bool = False, dry_run: bool = False) -> dict[str, Any]:
    """Apaga entidades pelos handles. DESTRUTIVO: exige confirm=true. Tudo-ou-nada; um Ctrl+Z desfaz.

    QUANDO USAR: só quando o usuário pediu para apagar. FLUXO: dry_run=true lista o que seria apagado;
    depois confirm=true. Se algum handle não existir, nada é apagado e o erro lista os ausentes.
    Parâmetros: handles (lista de strings hex), confirm, dry_run. Exemplo: delete_entities(["2F1A", "2F1B"], dry_run=true).
    """
    if not handles:
        raise InvalidParameterError("Informe ao menos um handle.")
    if len(handles) > s.cfg.max_batch_rows:
        raise InvalidParameterError(f"Máximo de {s.cfg.max_batch_rows} handles por chamada.")
    unique = list(dict.fromkeys(str(h).strip().upper() for h in handles))
    found, missing = [], []
    for h in unique:
        try:
            found.append(s.find_entity(h))
        except EntityNotFoundError:
            missing.append(h)
    if missing:
        raise EntityNotFoundError(f"Handles inexistentes: {missing}. Nada foi apagado.", details={"missing": missing})
    preview = {
        "dry_run": dry_run,
        "would_delete": len(found),
        "entities": [describe(s, e) for e in found[: s.cfg.max_limit]],
    }
    if dry_run:
        return {**preview, "deleted": 0}
    s.require_confirm(confirm, f"apagar {len(found)} entidade(s)", preview)
    with s.undo_mark():
        for e in found:
            e.Delete()
    return {"deleted": len(found), "handles": unique, "undo": "Ctrl+Z restaura as entidades apagadas."}


TOOLS = [draw_line, draw_polyline, draw_circle, add_text, add_mtext, move_entity, copy_entity, delete_entities]
