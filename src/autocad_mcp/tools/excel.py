"""Integração com Excel (domínio de tubulação): tabela de suportes ⇄ blocos com atributos."""

from __future__ import annotations

import datetime as dt
from typing import Any

from autocad_mcp._com import com_error
from autocad_mcp.blocks_core import (
    apply_attributes,
    definition_names,
    insert_block_ref,
    plan_attribute_changes,
    read_block,
    resolve_definition,
)
from autocad_mcp.entity_info import attributes_of, block_name
from autocad_mcp.errors import EntityNotFoundError, ExcelIntegrationError, InvalidParameterError
from autocad_mcp.excel_io import (
    FIXED_HEADERS,
    build_rows,
    check_path,
    read_table,
    resolve_mapping,
    write_table,
)
from autocad_mcp.geometry import format_cell
from autocad_mcp.selection import selection
from autocad_mcp.session import Session
from autocad_mcp.tools._base import com_tool

_MAX_EXPORT = 20000


def _key(v: str) -> str:
    return v.strip().casefold()


def _cap(items: list[Any], s: Session) -> tuple[list[Any], bool]:
    return items[: s.cfg.max_limit], len(items) > s.cfg.max_limit


@com_tool(coords=True)
def export_blocks_to_excel(
    s: Session,
    block_name: str,
    path: str,
    layer: str | None = None,
    sheet_name: str = "Blocos",
    confirm: bool = False,
) -> dict[str, Any]:
    """Exporta blocos para .xlsx: HANDLE, BLOCO, CAMADA, X, Y, Z, ROTACAO, ESCALA_X/Y/Z + uma coluna por TAG.

    QUANDO USAR: gerar a lista/tabela de suportes do desenho, ou obter uma planilha-modelo para depois
    editar e reimportar (o arquivo gerado é aceito por import_blocks_from_excel e sync_attributes_from_excel).
    Só lê o desenho. Se o arquivo já existir, sobrescrever exige confirm=true (a planilha tem aba INFO com a unidade).
    Parâmetros: block_name (curinga * e ?), path (.xlsx, caminho na máquina do usuário), layer (opcional),
    sheet_name, confirm. Coordenadas na unidade do desenho.
    Exemplo: export_blocks_to_excel("SUP-*", "C:\\\\proj\\\\suportes.xlsx", layer="SUPORTES").
    """
    p = check_path(path, s.cfg, write=True)
    if p.exists():
        s.require_confirm(confirm, "sobrescrever uma planilha existente", {"file": str(p)})
    tags: list[str] = []
    data: list[dict[str, Any]] = []
    with selection(s, types="INSERT", block=block_name, layer=layer) as sel:
        for ref in sel.iter_all():
            data.append(read_block(ref))
            if len(data) > _MAX_EXPORT:
                raise InvalidParameterError(f"Mais de {_MAX_EXPORT} blocos; restrinja block_name/layer.")
    for row in data:
        for t in row["attributes"]:
            if t not in tags:
                tags.append(t)
    fixed = set(FIXED_HEADERS)
    headers = FIXED_HEADERS + [("ATTR:" + t) if t in fixed else t for t in tags]  # evita colisão TAG "X" × coluna X
    rows = [
        [r["handle"], r["block"], r["layer"], *r["position"], r["rotation_deg"], *r["scale"]]
        + [r["attributes"].get(t, "") for t in tags]
        for r in data
    ]
    if len(rows) > 5000:
        s.warn("Exportação grande: leitura via COM é lenta; considere filtrar por bloco/camada.")
    info = {
        "desenho": str(s.doc.Name), "unidade": s.units_name, "filtro_bloco": block_name,
        "filtro_camada": layer or "", "linhas": len(rows), "gerado_em": dt.datetime.now().isoformat(timespec="seconds"),
    }
    write_table(p, sheet_name, headers, rows, info)
    if not rows:
        s.warn("Nenhum bloco encontrado: a planilha foi criada só com o cabeçalho.")
    return {"file": str(p), "sheet": sheet_name, "rows": len(rows), "columns": headers}


def _build_key_index(s: Session, key_tag: str, block_filter: str | None) -> dict[str, list[Any]]:
    index: dict[str, list[Any]] = {}
    with selection(s, types="INSERT", block=block_filter) as sel:
        for ref in sel.iter_all():
            v = attributes_of(ref).get(key_tag)
            if v is not None and v.strip():
                index.setdefault(_key(v), []).append(ref)
    return index


@com_tool(coords=True)
def import_blocks_from_excel(
    s: Session,
    path: str,
    sheet: str | None = None,
    mapping: dict[str, str] | None = None,
    dry_run: bool = False,
    confirm: bool = False,
    block_name: str | None = None,
    key_tag: str | None = None,
    layer: str | None = None,
    update_position: bool = False,
    create_missing_layer: bool = False,
    header_row: int = 1,
) -> dict[str, Any]:
    """Insere ou atualiza blocos, linha a linha, a partir de uma planilha .xlsx. Um único Ctrl+Z desfaz tudo.

    QUANDO USAR: carregar a tabela de suportes (TAG, TIPO, X, Y, Z, LINHA...) no desenho. FLUXO SEGURO:
    dry_run=true primeiro (relata inserir/atualizar/erro por linha sem tocar no desenho), depois execute.
    Inserções não pedem confirmação; se alguma linha ATUALIZA um bloco existente, exige confirm=true.
    Parâmetros: path/sheet/header_row; mapping ({coluna_excel: alvo}, alvo ∈ x,y,z,rotation(graus),scale,
    scale_x/y/z,layer,block,handle,ignore ou "attr:TAG"; sem mapping, detecta X/Y/Z/BLOCO/CAMADA/ROTACAO/
    ESCALA/HANDLE por nome e trata as demais colunas como atributos de mesmo nome); block_name (bloco padrão
    das linhas sem coluna de bloco); key_tag (atributo-chave, ex. "TAG": linha cujo valor já existe no desenho
    ATUALIZA o bloco em vez de inserir duplicado); layer (camada padrão); update_position (também move blocos
    existentes; padrão false); create_missing_layer. Célula em branco = ignorar (não apaga o atributo).
    Erros por linha não abortam o lote. Exemplo:
    import_blocks_from_excel("C:\\\\proj\\\\suportes.xlsx", block_name="SUP-GUIDE", key_tag="TAG", layer="SUPORTES", dry_run=true).
    """
    p = check_path(path, s.cfg, write=False)
    table = read_table(p, sheet, header_row, s.cfg.max_batch_rows)
    for w in table.warnings:
        s.warn(w)
    specs, results = build_rows(table, resolve_mapping(table.headers, mapping), block_name)
    key = key_tag.strip().upper() if key_tag else None

    known_blocks = definition_names(s)
    default_layer = s.ensure_layer(layer, create=create_missing_layer) if layer and not create_missing_layer else layer
    existing_layers = {n.casefold() for n in s.layer_names()}
    index = _build_key_index(s, key, block_name) if key else {}
    seen_keys: set[str] = set()
    plan: list[dict[str, Any]] = []
    layers_to_create: set[str] = set()

    for spec in specs:
        entry: dict[str, Any] = {"row": spec.row}
        try:
            target = None
            if spec.handle:
                target = s.find_entity(spec.handle)
                if not hasattr(target, "GetAttributes"):
                    raise InvalidParameterError(f"O handle {spec.handle} não é um bloco.")
            elif key:
                kv = spec.attributes.get(key)
                if not kv:
                    raise InvalidParameterError(f"Linha sem valor para a chave '{key}'.")
                if _key(kv) in seen_keys:
                    raise InvalidParameterError(f"Chave '{kv}' repetida na planilha.")
                seen_keys.add(_key(kv))
                found = index.get(_key(kv), [])
                if len(found) > 1:
                    raise InvalidParameterError(
                        f"Chave '{kv}' ambígua no desenho: {len(found)} blocos ({[str(f.Handle) for f in found[:5]]})."
                    )
                target = found[0] if found else None
            if target is not None:
                changes, unknown = plan_attribute_changes(target, spec.attributes)
                for t in unknown:
                    s.warn(f"Tag '{t}' não existe no bloco '{block_name_of(target)}' (ignorada).")
                pos_change = False
                if spec.has_position:
                    cur = read_block(target, with_attributes=False)["position"]
                    pos_change = any(abs(a - b) > 1e-6 for a, b in zip(cur, spec.point))
                    if pos_change and not update_position:
                        entry["warning"] = f"posição diverge do desenho {cur} → {list(spec.point)} (use update_position=true para mover)"
                entry.update(handle=str(target.Handle), block=block_name_of(target), changes={t: {"from": o, "to": n} for t, (o, n) in changes.items()})
                entry["action"] = "update" if (changes or (pos_change and update_position)) else "unchanged"
                entry["_target"], entry["_pos"] = target, (spec.point if pos_change and update_position else None)
            else:
                name = resolve_definition(s, spec.block or "", known_blocks) if spec.block else None
                if not name:
                    raise InvalidParameterError("Linha sem bloco: informe a coluna de bloco ou block_name.")
                if not spec.has_position:
                    raise InvalidParameterError("Linha sem coordenadas X e Y.")
                lay = spec.layer or default_layer or layer
                if lay and lay.casefold() not in existing_layers:
                    if not create_missing_layer:
                        raise InvalidParameterError(f"Camada '{lay}' não existe (use create_missing_layer=true).")
                    layers_to_create.add(lay)
                entry.update(action="insert", block=name, layer=lay, position=list(spec.point), attributes=spec.attributes)
                entry["_spec"] = spec
        except (InvalidParameterError, EntityNotFoundError, com_error) as exc:
            entry = {"row": spec.row, "action": "error", "message": str(exc).splitlines()[0]}
        plan.append(entry)

    plan = sorted(plan + results, key=lambda e: e["row"])
    counts = {a: sum(1 for e in plan if e["action"] == a) for a in ("insert", "update", "unchanged", "error")}

    def public(e: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in e.items() if not k.startswith("_")}

    def report(applied: bool) -> dict[str, Any]:
        shown, truncated = _cap([public(e) for e in plan], s)
        errs = [public(e) for e in plan if e["action"] == "error"][: s.cfg.max_limit]
        return {
            "file": str(p), "sheet": table.sheet, "dry_run": dry_run, "applied": applied,
            "rows_read": len(table.rows), "to_insert" if not applied else "inserted": counts["insert"],
            "to_update" if not applied else "updated": counts["update"],
            "unchanged": counts["unchanged"], "errors": counts["error"], "error_rows": errs,
            "results": shown, "results_truncated": truncated,
        }

    if dry_run or (counts["insert"] == 0 and counts["update"] == 0):
        return report(False)
    if counts["update"] > 0:
        s.require_confirm(confirm, f"atualizar {counts['update']} bloco(s) já existentes", {k: v for k, v in report(False).items() if k != "results"})

    with s.undo_mark():
        for lay in sorted(layers_to_create):
            s.ensure_layer(lay, create=True)
        for e in plan:
            if e["action"] == "insert":
                sp: Any = e["_spec"]
                try:
                    ref, _ch, unknown = insert_block_ref(
                        s, e["block"], sp.point, scale=sp.scale, rotation_deg=sp.rotation, layer=e.get("layer"), attributes=sp.attributes
                    )
                    e["handle"] = str(ref.Handle)
                    if unknown:
                        e["warning"] = f"tags inexistentes ignoradas: {unknown}"
                except (InvalidParameterError, com_error) as exc:
                    e.update(action="error", message=str(exc).splitlines()[0])
            elif e["action"] == "update":
                try:
                    apply_attributes(e["_target"], {t: c["to"] for t, c in e["changes"].items()})
                    if e["_pos"] is not None:
                        from autocad_mcp.geometry import to_variant_point

                        e["_target"].InsertionPoint = to_variant_point(e["_pos"])
                except (InvalidParameterError, com_error) as exc:
                    e.update(action="error", message=str(exc).splitlines()[0])
    counts.update({a: sum(1 for e in plan if e["action"] == a) for a in counts})
    out = report(True)
    out["undo"] = "Ctrl+Z desfaz todo o lote desta chamada."
    return out


def block_name_of(ref: Any) -> str:
    return block_name(ref)


@com_tool(coords=False)
def sync_attributes_from_excel(
    s: Session,
    path: str,
    key_tag: str,
    dry_run: bool = False,
    confirm: bool = False,
    sheet: str | None = None,
    block_name: str | None = None,
    mapping: dict[str, str] | None = None,
    header_row: int = 1,
) -> dict[str, Any]:
    """Atualiza ATRIBUTOS de blocos já existentes casando pela TAG-chave (não insere nem move nada).

    QUANDO USAR: a planilha é a fonte da verdade dos dados (TIPO, LINHA, PESO...) e o desenho deve refletí-la.
    FLUXO SEGURO: dry_run=true (mostra antes→depois, não encontrados e ambíguos); depois confirm=true.
    Como altera valores em massa, qualquer mudança real exige confirm=true. Um Ctrl+Z desfaz tudo.
    Parâmetros: path/sheet/header_row, key_tag (atributo-chave, ex. "TAG"; a planilha precisa de coluna
    com esse nome), block_name (restringe o universo; curinga), mapping ({coluna_excel: "TAG_DO_ATRIBUTO"};
    sem mapping, cada cabeçalho é o nome da tag). Célula em branco = mantém o valor do desenho.
    Exemplo: sync_attributes_from_excel("C:\\\\proj\\\\suportes.xlsx", key_tag="TAG", dry_run=true).
    """
    key = key_tag.strip().upper()
    if not key:
        raise InvalidParameterError("key_tag vazio.")
    p = check_path(path, s.cfg, write=False)
    table = read_table(p, sheet, header_row, s.cfg.max_batch_rows)
    col_tag: dict[str, str] = {}
    if mapping:
        for col, tag in mapping.items():
            hit = next((h for h in table.headers if h.casefold() == col.strip().casefold()), None)
            if hit is None:
                raise InvalidParameterError(f"Coluna '{col}' não existe na planilha. Colunas: {table.headers}")
            col_tag[hit] = str(tag).strip().upper()
    else:
        col_tag = {h: (h[5:] if h.casefold().startswith("attr:") else h).strip().upper() for h in table.headers}
        for fixed in ("HANDLE", "BLOCO", "CAMADA", "X", "Y", "Z", "ROTACAO", "ESCALA_X", "ESCALA_Y", "ESCALA_Z"):
            if fixed != key:
                col_tag = {h: t for h, t in col_tag.items() if t != fixed}
    key_col = next((h for h, t in col_tag.items() if t == key), None)
    if key_col is None:
        raise ExcelIntegrationError(f"Nenhuma coluna da planilha corresponde à chave '{key}'. Colunas: {table.headers}")

    index = _build_key_index(s, key, block_name)
    rows_out: list[dict[str, Any]] = []
    plan: list[tuple[Any, dict[str, str]]] = []
    seen: set[str] = set()
    matched_keys: set[str] = set()
    unknown_tags: set[str] = set()
    for rnum, rec in table.rows:
        kv = format_cell(rec.get(key_col))
        if not kv:
            rows_out.append({"row": rnum, "status": "error", "message": "chave vazia"})
            continue
        if _key(kv) in seen:
            rows_out.append({"row": rnum, "status": "error", "key": kv, "message": "chave repetida na planilha"})
            continue
        seen.add(_key(kv))
        found = index.get(_key(kv), [])
        if not found:
            rows_out.append({"row": rnum, "status": "not_found", "key": kv})
            continue
        if len(found) > 1:
            rows_out.append({"row": rnum, "status": "ambiguous", "key": kv, "handles": [str(f.Handle) for f in found[:10]]})
            continue
        matched_keys.add(_key(kv))
        ref = found[0]
        wanted = {t: format_cell(rec.get(h)) for h, t in col_tag.items() if t != key and format_cell(rec.get(h)) != ""}
        changes, unknown = plan_attribute_changes(ref, wanted)
        unknown_tags.update(unknown)
        status = "changed" if changes else "unchanged"
        rows_out.append({"row": rnum, "status": status, "key": kv, "handle": str(ref.Handle),
                         "changes": {t: {"from": o, "to": n} for t, (o, n) in changes.items()}})
        if changes:
            plan.append((ref, {t: n for t, (_o, n) in changes.items()}))
    if unknown_tags:
        s.warn(f"Colunas sem atributo correspondente em alguns blocos (ignoradas nesses casos): {sorted(unknown_tags)}")
    tally = {k: sum(1 for r in rows_out if r["status"] == k) for k in ("changed", "unchanged", "not_found", "ambiguous", "error")}
    only_in_drawing = sorted(k for k in index if k not in seen)
    shown, truncated = _cap(rows_out, s)
    result = {
        "file": str(p), "sheet": table.sheet, "key_tag": key, "dry_run": dry_run, "rows_read": len(table.rows), **tally,
        "in_drawing_not_in_sheet": len(only_in_drawing), "in_drawing_not_in_sheet_sample": only_in_drawing[:20],
        "results": shown, "results_truncated": truncated, "applied": False,
    }
    if dry_run or not plan:
        return result
    s.require_confirm(confirm, f"atualizar atributos de {len(plan)} bloco(s) a partir da planilha", {k: v for k, v in result.items() if k != "results"} | {"results": shown[:50]})
    with s.undo_mark():
        for ref, ch in plan:
            apply_attributes(ref, ch)
    result["applied"] = True
    result["undo"] = "Ctrl+Z desfaz todo o lote desta chamada."
    return result


TOOLS = [export_blocks_to_excel, import_blocks_from_excel, sync_attributes_from_excel]
