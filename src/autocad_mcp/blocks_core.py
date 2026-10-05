"""Operações de bloco/atributo compartilhadas por tools/blocks.py e tools/excel.py."""

from __future__ import annotations

import difflib
from typing import Any

from autocad_mcp.entity_info import attributes_of, block_name
from autocad_mcp.errors import InvalidParameterError
from autocad_mcp.geometry import (
    deg_to_rad,
    format_cell,
    from_com_point,
    normalize_point,
    rad_to_deg,
    to_variant_point,
)
from autocad_mcp.session import Session, safe_get

MAX_ATTDEF_SCAN = 5000


def definition_names(s: Session, *, include_xrefs: bool = False) -> dict[str, str]:
    """{nome_casefold: nome_canônico} das definições de bloco úteis (sem layouts/anônimos)."""
    blocks = s.doc.Blocks
    out: dict[str, str] = {}
    for i in range(int(blocks.Count)):
        b = blocks.Item(i)
        name = str(b.Name)
        if name.startswith("*") or bool(safe_get(b, "IsLayout", default=False)):
            continue
        if bool(safe_get(b, "IsXRef", default=False)) and not include_xrefs:
            continue
        out[name.casefold()] = name
    return out


def resolve_definition(s: Session, name: str, known: dict[str, str] | None = None) -> str:
    """Nome canônico da definição ou erro com sugestões de nomes parecidos."""
    known = known if known is not None else definition_names(s)
    key = (name or "").strip().casefold()
    if key in known:
        return known[key]
    close = difflib.get_close_matches(key, list(known), n=5, cutoff=0.5)
    hint = f" Parecidos: {[known[c] for c in close]}." if close else ""
    raise InvalidParameterError(
        f"O bloco '{name}' não existe neste desenho (só definições existentes podem ser inseridas).{hint}"
        " Use list_block_definitions."
    )


def attribute_definitions(block: Any) -> list[dict[str, Any]]:
    tags = []
    for j in range(min(int(block.Count), MAX_ATTDEF_SCAN)):
        e = block.Item(j)
        if str(safe_get(e, "ObjectName", default="")) == "AcDbAttributeDefinition":
            tags.append({
                "tag": str(e.TagString).upper(),
                "prompt": str(safe_get(e, "PromptString", default="") or ""),
                "default": str(safe_get(e, "TextString", default="") or ""),
                "constant": bool(safe_get(e, "Constant", default=False)),
            })
    return tags


def clean_attributes(attrs: dict[str, Any] | None) -> dict[str, str]:
    """{tag: valor} normalizado: tags em MAIÚSCULAS, valores em texto. None é recusado (use '' p/ limpar)."""
    out: dict[str, str] = {}
    for k, v in (attrs or {}).items():
        tag = str(k).strip().upper()
        if not tag:
            raise InvalidParameterError("Tag de atributo vazia.")
        if v is None:
            raise InvalidParameterError(f"Valor nulo para a tag {tag}; use texto vazio ('') para limpar o atributo.")
        out[tag] = format_cell(v)
    return out


def plan_attribute_changes(ref: Any, wanted: dict[str, str]) -> tuple[dict[str, tuple[str, str]], list[str]]:
    """(mudanças {tag: (antigo, novo)}, tags inexistentes no bloco). Não escreve nada."""
    current = attributes_of(ref)
    changes: dict[str, tuple[str, str]] = {}
    unknown: list[str] = []
    for tag, new in wanted.items():
        if tag not in current:
            unknown.append(tag)
        elif current[tag] != new:
            changes[tag] = (current[tag], new)
    return changes, unknown


def apply_attributes(ref: Any, wanted: dict[str, str]) -> dict[str, tuple[str, str]]:
    """Escreve os atributos (só os que mudam). Chamar dentro de undo_mark."""
    changes, _ = plan_attribute_changes(ref, wanted)
    if not changes:
        return changes
    for att in ref.GetAttributes():
        tag = str(att.TagString).upper()
        if tag in changes:
            att.TextString = changes[tag][1]
    return changes


def read_block(ref: Any, *, with_attributes: bool = True) -> dict[str, Any]:
    row = {
        "handle": str(ref.Handle),
        "block": block_name(ref),
        "layer": str(safe_get(ref, "Layer", default="")),
        "position": from_com_point(ref.InsertionPoint),
        "rotation_deg": rad_to_deg(safe_get(ref, "Rotation", default=0.0)),
        "scale": [round(float(safe_get(ref, a, default=1.0)), 6) for a in ("XScaleFactor", "YScaleFactor", "ZScaleFactor")],
    }
    if with_attributes:
        row["attributes"] = attributes_of(ref)
    return row


def normalize_scale(scale: float | list[float] | tuple[float, ...]) -> tuple[float, float, float]:
    vals = [float(scale)] * 3 if isinstance(scale, (int, float)) else [float(v) for v in scale]
    if len(vals) == 1:
        vals *= 3
    if len(vals) != 3 or any(v == 0 for v in vals) or any(v != v or abs(v) == float("inf") for v in vals):
        raise InvalidParameterError("scale deve ser um número ≠ 0 ou [sx, sy, sz] com valores ≠ 0.")
    return vals[0], vals[1], vals[2]


def insert_block_ref(
    s: Session,
    name: str,
    point: Any,
    *,
    scale: Any = 1.0,
    rotation_deg: float = 0.0,
    layer: str | None = None,
    attributes: dict[str, str] | None = None,
) -> tuple[Any, dict[str, tuple[str, str]], list[str]]:
    """Insere (dentro de undo_mark do chamador) e preenche atributos. Retorna (ref, mudanças, tags desconhecidas)."""
    p = normalize_point(point, name="point")
    sx, sy, sz = normalize_scale(scale)
    ref = s.model_space.InsertBlock(to_variant_point(p), name, sx, sy, sz, deg_to_rad(rotation_deg))
    if layer:
        ref.Layer = layer
    changes: dict[str, tuple[str, str]] = {}
    unknown: list[str] = []
    if attributes:
        _, unknown = plan_attribute_changes(ref, attributes)
        changes = apply_attributes(ref, attributes)
    return ref, changes, unknown
