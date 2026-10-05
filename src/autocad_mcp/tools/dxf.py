"""Ferramentas DXF offline: funcionam SEM AutoCAD aberto (ezdxf). Respeitam read_only e a lista de pastas."""

from __future__ import annotations

from typing import Any

from autocad_mcp import dxf_engine as eng
from autocad_mcp.context import get_context
from autocad_mcp.errors import ConfirmationRequiredError, InvalidParameterError
from autocad_mcp.paths import resolve_path
from autocad_mcp.tools._base import local_tool

_DXF = (".dxf",)


def _in(path: str):
    cfg = get_context().cfg
    p = resolve_path(path, cfg, write=False, suffixes=_DXF)
    return p, eng.open_doc(p)


def _out(path: str, output_path: str | None):
    """Destino do salvamento: output_path (copia, original intacto) ou o próprio arquivo."""
    if output_path:
        return resolve_path(output_path, get_context().cfg, write=True, suffixes=_DXF, must_exist=False)
    return resolve_path(path, get_context().cfg, write=True, suffixes=_DXF, must_exist=True)


def _check_batch(items: list, label: str) -> None:
    if not items:
        raise InvalidParameterError(f"'{label}' está vazio.")
    if len(items) > eng.MAX_ENTITIES_PER_CALL:
        raise InvalidParameterError(f"Máximo de {eng.MAX_ENTITIES_PER_CALL} itens por chamada; divida o lote.")


# ----------------------------------------------------------------------------- leitura

@local_tool(mutates=False)
def dxf_info(path: str) -> dict[str, Any]:
    """Resume um DXF sem abrir o AutoCAD: versão, unidades, camadas, layouts, blocos, estilos de cota, extensão.

    QUANDO USAR: primeiro passo antes de qualquer outra ferramenta dxf_*; confirma unidades e nomes de camada/layout.
    Parâmetros: path = caminho do .dxf dentro das pastas permitidas.
    Exemplo: dxf_info(path="C:/Users/eu/autocad-mcp-workspace/linha-L12.dxf")
    """
    _p, doc = _in(path)
    return eng.info(doc)


@local_tool(mutates=False)
def dxf_query(path: str, type: str | None = None, layer: str | None = None, block: str | None = None,
              layout: str | None = None, limit: int = 50, offset: int = 0) -> dict[str, Any]:
    """Lista entidades de um DXF com filtros e paginação (curingas * e ? em layer/block).

    QUANDO USAR: inspecionar ou contar entidades de um DXF sem AutoCAD; pagine com offset/limit (máx. 500).
    Parâmetros: path; type (LINE, CIRCLE, ARC, LWPOLYLINE, TEXT, MTEXT, INSERT, DIMENSION...); layer; block;
    layout (omita para o modelo); limit; offset.
    Exemplo: dxf_query(path="a.dxf", type="INSERT", block="SUP-*", layer="SUPORTES", limit=100)
    """
    _p, doc = _in(path)
    return eng.query(doc, type=type, layer=layer, block=block, layout=layout,
                     limit=max(1, min(int(limit), 500)), offset=max(0, int(offset)))


@local_tool(mutates=False)
def dxf_get_entity(path: str, handle: str) -> dict[str, Any]:
    """Devolve os detalhes completos de uma entidade do DXF pelo handle.

    QUANDO USAR: depois de dxf_query, para ver geometria/atributos de uma entidade específica.
    Parâmetros: path; handle (hexadecimal, ex. "2A3").
    Exemplo: dxf_get_entity(path="a.dxf", handle="2A3")
    """
    _p, doc = _in(path)
    return {"entity": eng.entity_summary(eng.get_entity(doc, handle), detail=True)}


@local_tool(mutates=False)
def dxf_read_attributes(path: str, block_filter: str | None = None, layer_filter: str | None = None) -> dict[str, Any]:
    """Lê os atributos de blocos (ex.: suportes TAG/TIPO/LINHA) direto do DXF, sem AutoCAD.

    QUANDO USAR: extrair o cadastro de suportes de um DXF exportado, ou preparar planilha/auditoria offline.
    Parâmetros: path; block_filter (ex. "SUP-*"); layer_filter. Recusa mais de 2000 blocos (restrinja o filtro).
    Exemplo: dxf_read_attributes(path="linha.dxf", block_filter="SUP-*")
    """
    _p, doc = _in(path)
    rows = eng.read_attributes(doc, block_filter, layer_filter)
    return {"count": len(rows), "blocks": rows}


@local_tool(mutates=False)
def dxf_sql_query(path: str, sql: str, limit: int = 200) -> dict[str, Any]:
    """Consulta o DXF com SQL SELECT sobre um índice em memória (tabelas entities e attributes).

    QUANDO USAR: perguntas agregadas (contagens por camada, blocos sem TAG, comprimento total por camada).
    Parâmetros: path; sql (somente SELECT; colunas entities: handle,type,layer,color,block,x,y,z,text,length,radius;
    attributes: handle,block,tag,value); limit (máx. 1000).
    Exemplo: dxf_sql_query(path="a.dxf", sql="SELECT layer, COUNT(*) n, SUM(length) L FROM entities GROUP BY layer")
    """
    _p, doc = _in(path)
    return eng.sql_query(doc, sql, limit=max(1, min(int(limit), 1000)))


@local_tool(mutates=False)
def dxf_audit(path: str) -> dict[str, Any]:
    """Audita a estrutura do DXF (erros que o AutoCAD acusaria ao abrir) sem alterar o arquivo.

    QUANDO USAR: antes de publicar/entregar um DXF gerado ou recebido; relata erros e itens corrigíveis.
    Parâmetros: path. Exemplo: dxf_audit(path="entrega.dxf")
    """
    _p, doc = _in(path)
    auditor = doc.audit()
    return {"errors": [str(e.message) for e in auditor.errors][:100], "error_count": len(auditor.errors),
            "fixes": [str(f.message) for f in auditor.fixes][:100], "fix_count": len(auditor.fixes),
            "clean": not auditor.has_errors}


# ----------------------------------------------------------------------------- escrita

@local_tool()
def dxf_create(path: str, units: str = "mm", version: str = "R2018", overwrite: bool = False) -> dict[str, Any]:
    """Cria um DXF novo e vazio (com estilos de cota e tipos de linha padrão) sem abrir o AutoCAD.

    QUANDO USAR: iniciar um desenho offline (esquema de suporte, folha de detalhe) para preencher com dxf_add_entities.
    Parâmetros: path (.dxf); units (mm, cm, m, in, ft); version (R2000..R2018); overwrite (padrão false).
    Exemplo: dxf_create(path="suporte-S12.dxf", units="mm")
    """
    p = resolve_path(path, get_context().cfg, write=True, suffixes=_DXF, must_exist=False)
    if p.exists() and not overwrite:
        raise InvalidParameterError(f"'{p.name}' já existe; use overwrite=true para substituir.")
    doc = eng.create_doc(version, units)
    eng.save_doc(doc, p)
    return {"path": str(p), "version": doc.dxfversion, "units": units}


@local_tool()
def dxf_create_layer(path: str, name: str, color: int = 7, linetype: str | None = None,
                     output_path: str | None = None) -> dict[str, Any]:
    """Cria (ou confirma) uma camada em um DXF.

    QUANDO USAR: preparar camadas (SUPORTES, COTAS, EIXOS) antes de desenhar.
    Parâmetros: path; name; color (ACI 1-255); linetype (ex. "DASHED"); output_path (salva cópia, preserva o original).
    Exemplo: dxf_create_layer(path="a.dxf", name="COTAS", color=3)
    """
    _p, doc = _in(path)
    existed = name in doc.layers
    eng.ensure_layer(doc, name, color, linetype)
    eng.save_doc(doc, _out(path, output_path))
    return {"layer": name, "created": not existed}


@local_tool()
def dxf_add_entities(path: str, entities: list[dict[str, Any]], layout: str | None = None,
                     output_path: str | None = None) -> dict[str, Any]:
    """Adiciona em lote entidades a um DXF: line, circle, arc, polyline, text, mtext, point, ellipse, hatch, insert.

    QUANDO USAR: desenhar offline. Valida tudo antes de salvar: se uma entidade falhar, nada é gravado.
    Parâmetros: path; entities (lista de objetos com "type"); layout (omita para o modelo); output_path.
    Campos: line{start,end} circle{center,radius} arc{center,radius,start_angle,end_angle} polyline{points,closed}
    text{insert,text,height,rotation} mtext{insert,text,height} hatch{points,pattern,scale} insert{block,insert,attributes}
    ellipse{center,major_axis,ratio}; todos aceitam layer e color (ACI).
    Exemplo: dxf_add_entities(path="a.dxf", entities=[{"type":"line","start":[0,0],"end":[100,0],"layer":"EIXOS"}])
    """
    _check_batch(entities, "entities")
    _p, doc = _in(path)
    space = eng._space(doc, layout)
    handles = []
    for i, spec in enumerate(entities):
        try:
            handles.append(eng.add_entity(doc, space, spec).dxf.handle)
        except InvalidParameterError as exc:
            raise InvalidParameterError(f"entities[{i}]: {exc} (nada foi gravado)") from exc
    eng.save_doc(doc, _out(path, output_path))
    return {"added": len(handles), "handles": handles[:200], "handles_truncated": len(handles) > 200}


@local_tool()
def dxf_define_block(path: str, name: str, entities: list[dict[str, Any]], attributes: list[str] | None = None,
                     output_path: str | None = None) -> dict[str, Any]:
    """Define um bloco (com atributos opcionais) em um DXF para depois inserir com dxf_add_entities type=insert.

    QUANDO USAR: criar o símbolo de suporte (ex. SUP-GUIA) com TAG/TIPO/LINHA offline.
    Parâmetros: path; name; entities (mesmo formato de dxf_add_entities, sem hatch/insert aninhado recomendado);
    attributes (lista de tags, ex. ["TAG","TIPO","LINHA"]); output_path.
    Exemplo: dxf_define_block(path="a.dxf", name="SUP-GUIA", entities=[{"type":"circle","center":[0,0],"radius":50}], attributes=["TAG","TIPO"])
    """
    _check_batch(entities, "entities")
    _p, doc = _in(path)
    eng.define_block(doc, name, entities, attributes)
    eng.save_doc(doc, _out(path, output_path))
    return {"block": name, "entities": len(entities), "attributes": attributes or []}


@local_tool()
def dxf_modify_entities(path: str, handles: list[str], layer: str | None = None, color: int | None = None,
                        translate: list[float] | None = None, rotate_deg: float | None = None,
                        rotate_center: list[float] | None = None, scale: float | None = None,
                        attributes: dict[str, str] | None = None, output_path: str | None = None) -> dict[str, Any]:
    """Altera entidades de um DXF: camada, cor, mover, girar, escalar e atributos de bloco.

    QUANDO USAR: ajustes em lote de um DXF (mudar camada de suportes, deslocar um trecho, corrigir TAG).
    Parâmetros: path; handles; layer; color; translate [dx,dy,dz]; rotate_deg (+ rotate_center); scale (>0);
    attributes {"TAG":"S-01"} (só blocos); output_path (recomendado: salva cópia).
    Exemplo: dxf_modify_entities(path="a.dxf", handles=["2A3"], attributes={"TIPO":"GUIA"}, output_path="a_rev1.dxf")
    """
    _check_batch(handles, "handles")
    _p, doc = _in(path)
    res = eng.modify(doc, handles, layer=layer, color=color, translate=translate, rotate_deg=rotate_deg,
                     rotate_center=rotate_center, scale=scale, attributes=attributes)
    eng.save_doc(doc, _out(path, output_path))
    return res


@local_tool()
def dxf_delete_entities(path: str, handles: list[str], confirm: bool = False, dry_run: bool = False,
                        output_path: str | None = None) -> dict[str, Any]:
    """Apaga entidades de um DXF (exige confirm=true; dry_run mostra a prévia sem gravar).

    QUANDO USAR: remover entidades erradas. Prefira output_path para manter o original.
    Parâmetros: path; handles; confirm; dry_run; output_path.
    Exemplo: dxf_delete_entities(path="a.dxf", handles=["2A3"], confirm=True, output_path="a_limpo.dxf")
    """
    _check_batch(handles, "handles")
    _p, doc = _in(path)
    preview = [eng.entity_summary(eng.get_entity(doc, h)) for h in handles[:20]]
    if dry_run:
        return {"would_delete": len(handles), "preview": preview}
    if not confirm:
        raise ConfirmationRequiredError(f"Apagaria {len(handles)} entidade(s). Repita com confirm=true.", details=preview)
    n = eng.delete_entities(doc, handles)
    eng.save_doc(doc, _out(path, output_path))
    return {"deleted": n}


@local_tool()
def dxf_add_dimensions(path: str, dimensions: list[dict[str, Any]], layout: str | None = None,
                       output_path: str | None = None) -> dict[str, Any]:
    """Cota um DXF (cotagem): linear, alinhada, raio, diâmetro e angular, com bloco de cota nativo.

    QUANDO USAR: cotar vãos, distâncias entre suportes, diâmetros de furo; gera cotas reais (entidade DIMENSION).
    Parâmetros: path; dimensions (lista); layout; output_path. Campos comuns: layer, color, dimstyle (padrão "EZDXF"),
    text_height, arrow_size, decimals, lfac (fator linear: texto = distância x lfac, p/ desenho em escala), text (substitui o valor; "<>" = medida).
    linear{base,p1,p2,angle} aligned{p1,p2,offset} radius{center,radius,angle} diameter{center,radius,angle}
    angular{line1:[[x,y],[x,y]],line2:[[x,y],[x,y]],base}.
    Exemplo: dxf_add_dimensions(path="a.dxf", dimensions=[{"kind":"linear","p1":[0,0],"p2":[1500,0],"base":[0,-200],"layer":"COTAS"}])
    """
    _check_batch(dimensions, "dimensions")
    _p, doc = _in(path)
    space = eng._space(doc, layout)
    out = []
    for i, spec in enumerate(dimensions):
        try:
            dim = eng.add_dimension(doc, space, spec)
        except InvalidParameterError as exc:
            raise InvalidParameterError(f"dimensions[{i}]: {exc} (nada foi gravado)") from exc
        out.append({"handle": dim.dxf.handle, "measurement": round(float(dim.get_measurement()), 6)
                    if hasattr(dim, "get_measurement") else None})
    eng.save_doc(doc, _out(path, output_path))
    return {"added": len(out), "dimensions": out}


@local_tool()
def dxf_create_layout(path: str, name: str, paper: str = "A3", landscape: bool = True, margins_mm: float = 10.0,
                      viewports: list[dict[str, Any]] | None = None, output_path: str | None = None) -> dict[str, Any]:
    """Cria um layout (folha) de papel num DXF, com viewports que enquadram o modelo em escala.

    QUANDO USAR: montar a folha de impressão antes de dxf_export (PDF).
    Parâmetros: path; name; paper (A4, A3, A2, A1, A0); landscape; margins_mm; output_path;
    viewports [{center:[x,y] no papel, width, height em mm, view_center:[x,y] no modelo, scale: papel/modelo (0.01 = 1:100)}].
    Exemplo: dxf_create_layout(path="a.dxf", name="Folha1", paper="A3", viewports=[{"center":[210,148],"width":380,"height":260,"view_center":[750,0],"scale":0.1}])
    """
    _p, doc = _in(path)
    res = eng.create_layout(doc, name, paper, landscape, margins_mm, viewports)
    eng.save_doc(doc, _out(path, output_path))
    return res


@local_tool()
def dxf_export(path: str, output: str, layout: str | None = None, dpi: int = 150,
               background: str = "white") -> dict[str, Any]:
    """Renderiza o modelo ou um layout do DXF para PDF, PNG ou SVG, sem AutoCAD (motor ezdxf + matplotlib).

    QUANDO USAR: gerar PDF de entrega ou imagem de pré-visualização; o formato vem da extensão de `output`.
    Parâmetros: path; output (.pdf, .png ou .svg); layout (omita para o modelo); dpi (30-600); background ("white" = traço preto sobre branco, "default").
    Exemplo: dxf_export(path="a.dxf", output="a.pdf", layout="Folha1")
    Observação: é uma renderização aproximada (não idêntica ao plotter do AutoCAD).
    """
    cfg = get_context().cfg
    _p, doc = _in(path)
    out = resolve_path(output, cfg, write=True, suffixes=(".pdf", ".png", ".svg"), must_exist=False)
    return eng.export_render(doc, out, layout=layout, dpi=dpi, background=background)


@local_tool()
def dxf_insert_support_symbol(path: str, kind: str, insert: list[float], tag: str | None = None,
                              line: str | None = None, size: float = 100.0, layer: str | None = None,
                              output_path: str | None = None) -> dict[str, Any]:
    """Insere um pictograma de suporte de tubulação (GUIA, ANCORA, APOIO, MOLA) com atributos TAG/TIPO/LINHA.

    QUANDO USAR: montar offline o desenho/cadastro de suportes; o bloco SUP-<TIPO> é criado se ainda não existir
    e depois pode ser lido com dxf_read_attributes. Os pictogramas são simplificados, não seguem uma norma.
    Parâmetros: path; kind (GUIA, ANCORA, APOIO, MOLA); insert [x, y]; tag; line (nº da linha); size (largura do símbolo,
    unidades do desenho; padrão 100); layer; output_path.
    Exemplo: dxf_insert_support_symbol(path="a.dxf", kind="GUIA", insert=[1200, 0], tag="S-014", line="L-12", layer="SUPORTES")
    """
    _p, doc = _in(path)
    res = eng.insert_support_symbol(doc, kind, tuple(float(v) for v in insert), tag, line, size, layer)
    eng.save_doc(doc, _out(path, output_path))
    return res


TOOLS = [dxf_info, dxf_query, dxf_get_entity, dxf_read_attributes, dxf_sql_query, dxf_audit, dxf_create,
         dxf_create_layer, dxf_add_entities, dxf_define_block, dxf_modify_entities, dxf_delete_entities,
         dxf_add_dimensions, dxf_create_layout, dxf_export, dxf_insert_support_symbol]
