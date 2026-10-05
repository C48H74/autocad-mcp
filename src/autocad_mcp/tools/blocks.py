"""Blocos e atributos (prioridade máxima para tubulação/suportes)."""

from __future__ import annotations

from typing import Any

from autocad_mcp.blocks_core import (
    apply_attributes,
    attribute_definitions,
    clean_attributes,
    definition_names,
    insert_block_ref,
    plan_attribute_changes,
    read_block,
    resolve_definition,
)
from autocad_mcp.entity_info import attributes_of, block_name
from autocad_mcp.errors import InvalidParameterError
from autocad_mcp.selection import selection
from autocad_mcp.session import Session
from autocad_mcp.tools._base import com_tool

_PREVIEW_CAP = 200


@com_tool(mutates=False)
def list_block_definitions(
    s: Session,
    name_filter: str | None = None,
    include_xrefs: bool = False,
    count_instances: bool = False,
    limit: int = 0,
    offset: int = 0,
) -> dict[str, Any]:
    """Lista as definições de bloco do desenho e as TAGS de atributo de cada uma.

    QUANDO USAR: antes de insert_block (para saber nomes e tags válidos) ou de montar planilhas.
    Parâmetros: name_filter (curinga * e ?, ex. "SUP-*"), include_xrefs, count_instances (conta as
    referências no espaço modelo; mais lento), limit/offset (paginação; as tags só são lidas para a
    página pedida). Exemplo: list_block_definitions(name_filter="SUP-*", count_instances=true).
    """
    import fnmatch

    lim, off = s.page_args(limit, offset)
    names = sorted(definition_names(s, include_xrefs=include_xrefs).values(), key=str.casefold)
    if name_filter:
        pat = name_filter.casefold()
        names = [n for n in names if fnmatch.fnmatchcase(n.casefold(), pat)]
    page = names[off:off + lim]
    rows = []
    for n in page:
        row: dict[str, Any] = {"name": n, "attributes": attribute_definitions(s.doc.Blocks.Item(n))}
        if count_instances:
            with selection(s, block=n) as sel:
                row["instances"] = sel.page(0, 0)[1]
        rows.append(row)
    return {"blocks": rows, "page": s.page_info(len(names), off, lim, len(rows))}


@com_tool(coords=True)
def insert_block(
    s: Session,
    name: str,
    point: list[float],
    scale: float | list[float] = 1.0,
    rotation: float = 0.0,
    layer: str | None = None,
    attributes: dict[str, Any] | None = None,
    create_missing_layer: bool = False,
) -> dict[str, Any]:
    """Insere UMA referência de bloco (definição já existente) e preenche atributos por TAG.

    QUANDO USAR: para colocar um suporte/símbolo em coordenadas conhecidas. Para muitos blocos a partir
    de planilha, use import_blocks_from_excel. Desfazível com um Ctrl+Z.
    Parâmetros: name (bloco existente; ver list_block_definitions), point ([x, y] ou [x, y, z] na unidade do
    desenho), scale (número ou [sx, sy, sz]), rotation (GRAUS, anti-horário), layer (existente, ou crie com
    create_missing_layer=true), attributes ({TAG: valor}; tags não existentes geram aviso).
    Exemplo: insert_block("SUP-GUIDE", [1250.5, 830, 4200], rotation=90, layer="SUPORTES",
    attributes={"TAG": "PS-101", "LINHA": "10-P-1001"}).
    """
    canonical = resolve_definition(s, name)
    wanted = clean_attributes(attributes)
    lay = s.ensure_layer(layer, create=False) if not create_missing_layer else None
    with s.undo_mark():
        if create_missing_layer:
            lay = s.ensure_layer(layer, create=True)
        ref, _, unknown = insert_block_ref(
            s, canonical, point, scale=scale, rotation_deg=rotation, layer=lay, attributes=wanted
        )
    if unknown:
        s.warn(f"Tags inexistentes em '{canonical}' (ignoradas): {unknown}")
    if wanted and not bool(attributes_of(ref)):
        s.warn(f"O bloco '{canonical}' não tem atributos; attributes foi ignorado.")
    return {"block": read_block(ref)}


@com_tool(coords=True, mutates=False)
def read_block_attributes(
    s: Session, block_name: str | None = None, layer: str | None = None, limit: int = 0, offset: int = 0
) -> dict[str, Any]:
    """Lê referências de bloco: handle, posição, camada e dicionário TAG → valor de atributos.

    QUANDO USAR: para "ler a tabela de suportes do desenho", conferir TAGs, ou antes de atualizar valores.
    Parâmetros: block_name (curinga * e ?; vazio = todos os blocos), layer (curinga), limit/offset
    (paginação; 0 = padrão do servidor). Exemplo: read_block_attributes(block_name="SUP-*", layer="SUPORTES", limit=100).
    """
    lim, off = s.page_args(limit, offset)
    with selection(s, types="INSERT", block=block_name, layer=layer) as sel:
        items, total = sel.page(off, lim)
        rows = [read_block(r) for r in items]
    return {"blocks": rows, "page": s.page_info(total, off, lim, len(rows))}


def _targets(s: Session, handle: str | None, flt: dict[str, Any] | None) -> list[Any]:
    if bool(handle) == bool(flt):
        raise InvalidParameterError("Informe exatamente um entre `handle` e `filter`.")
    if handle:
        ent = s.find_entity(handle)
        if block_name(ent) == "" or not hasattr(ent, "GetAttributes"):
            raise InvalidParameterError(f"A entidade {handle} não é uma referência de bloco.")
        return [ent]
    unknown = set(flt) - {"block_name", "layer", "where"}  # type: ignore[arg-type]
    if unknown:
        raise InvalidParameterError(f"Chaves desconhecidas em filter: {sorted(unknown)}. Use block_name, layer, where.")
    where = clean_attributes((flt or {}).get("where"))
    out: list[Any] = []
    with selection(s, types="INSERT", block=flt.get("block_name"), layer=flt.get("layer")) as sel:  # type: ignore[union-attr]
        for ref in sel.iter_all():
            if where:
                cur = attributes_of(ref)
                if any(cur.get(t, None) is None or cur[t].strip().casefold() != v.strip().casefold() for t, v in where.items()):
                    continue
            out.append(ref)
            if len(out) > s.cfg.max_batch_rows:
                raise InvalidParameterError(
                    f"O filtro casa mais de {s.cfg.max_batch_rows} blocos; restrinja block_name/layer/where."
                )
    return out


@com_tool(coords=True)
def update_block_attributes(
    s: Session,
    attributes: dict[str, Any],
    handle: str | None = None,
    filter: dict[str, Any] | None = None,
    dry_run: bool = False,
    confirm: bool = False,
) -> dict[str, Any]:
    """Altera atributos de UM bloco (handle) ou de vários (filter). Sobrescrita exige confirm=true.

    QUANDO USAR: corrigir/preencher TAG, TIPO, LINHA etc. FLUXO SEGURO: 1) dry_run=true para ver o antes→depois;
    2) repetir com confirm=true. Sem confirm, se houver sobrescrita de valor existente ou mais de 1 bloco
    afetado, retorna ok=false com a prévia. Um único Ctrl+Z desfaz tudo.
    Parâmetros: attributes ({TAG: novo valor}; '' limpa), handle (string hex) OU filter
    ({"block_name": "SUP-*", "layer": "SUPORTES", "where": {"LINHA": "10-P-1001"}}), dry_run, confirm.
    Exemplo: update_block_attributes({"TIPO": "GUIA"}, filter={"block_name": "SUP-*", "where": {"TIPO": "SHOE"}}, dry_run=true).
    """
    wanted = clean_attributes(attributes)
    if not wanted:
        raise InvalidParameterError("`attributes` está vazio.")
    targets = _targets(s, handle, filter)

    plan, unknown_all, unchanged = [], set(), 0
    for ref in targets:
        changes, unknown = plan_attribute_changes(ref, wanted)
        unknown_all.update(unknown)
        if changes:
            plan.append((ref, changes))
        else:
            unchanged += 1
    overwrites = sum(1 for _, ch in plan for old, _new in ch.values() if old != "")
    preview = {
        "dry_run": dry_run,
        "matched": len(targets),
        "to_change": len(plan),
        "unchanged": unchanged,
        "overwrites_existing_values": overwrites,
        "changes": [
            {"handle": str(r.Handle), "block": block_name(r), "changes": {t: {"from": o, "to": n} for t, (o, n) in ch.items()}}
            for r, ch in plan[:_PREVIEW_CAP]
        ],
        "changes_truncated": len(plan) > _PREVIEW_CAP,
    }
    if unknown_all:
        s.warn(f"Tags não encontradas em alguns/todos os blocos (ignoradas nesses casos): {sorted(unknown_all)}")
    if dry_run or not plan:
        return {**preview, "applied": False}
    if overwrites > 0 or len(plan) > 1:
        s.require_confirm(confirm, f"alterar atributos de {len(plan)} bloco(s), {overwrites} valor(es) existente(s) sobrescrito(s)", preview)
    done = 0
    try:
        with s.undo_mark():
            for ref, _ in plan:
                apply_attributes(ref, wanted)
                done += 1
    except Exception as exc:
        raise type(exc)(f"{exc} — {done} bloco(s) já alterado(s); um único Ctrl+Z desfaz o lote.") from exc
    return {**preview, "applied": True, "undo": "Ctrl+Z desfaz todas as alterações desta chamada."}


TOOLS = [list_block_definitions, insert_block, read_block_attributes, update_block_attributes]
