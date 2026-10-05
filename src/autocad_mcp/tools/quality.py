"""Support QA and explicit server capabilities. Independently implemented; no third-party code copied."""
from __future__ import annotations

from typing import Any

from autocad_mcp import __version__
from autocad_mcp._com import HAS_PYWIN32
from autocad_mcp.blocks_core import read_block
from autocad_mcp.context import get_context
from autocad_mcp.errors import InvalidParameterError
from autocad_mcp.selection import selection
from autocad_mcp.session import Session
from autocad_mcp.support_quality import Fields, SupportSnapshot, audit, compare, digest
from autocad_mcp.tools._base import com_tool, local_read_tool


@local_read_tool
def system_capabilities() -> dict[str, Any]:
    """Informa capacidades e restrições sem conectar ou iniciar AutoCAD.

    QUANDO USAR: antes de escolher ferramentas; distingue configuração de conexão real.
    Parâmetros: nenhum. Exemplo: system_capabilities() informa read_only e limitações Plant 3D.
    """
    cfg = get_context().cfg
    return {"version": __version__, "backend": "windows-com", "pywin32_available": HAS_PYWIN32,
            "connection_verified": False, "connection_probe": "status", "read_only": cfg.read_only,
            "drawing_writes_enabled": not cfg.read_only, "excel_writes_enabled": not cfg.read_only,
            "lisp_enabled": cfg.enable_lisp and not cfg.read_only, "auto_launch_enabled": cfg.allow_launch and not cfg.read_only,
            "support_qa": True, "offline_snapshot_comparison": True, "headless_dxf_engine": True, "dxf_engine": "ezdxf", "tool_profile": cfg.profile,
            "audit_log_enabled": cfg.audit_log, "file_io_restricted": not cfg.allow_any_path or bool(cfg.excel_allowed_dirs),
            "native_plant3d_database": False, "automatic_rollback": False,
            "max_snapshot_rows": min(cfg.max_batch_rows, 2000),
            "read_only_note": "Blocks mutating tools including dry_run, save, Excel export, LISP and view/session changes; logs and temporary COM selection sets remain."}


@com_tool(mutates=False)
def snapshot_support_register(s: Session, block_filter: str | None = None, layer_filter: str | None = None,
                              key_tag: str = "TAG", type_tag: str = "TIPO", line_tag: str = "LINHA") -> dict[str, Any]:
    """Captura cadastro completo e limitado de suportes, sem alterar entidades ou salvar arquivos.

    QUANDO USAR: antes de revisar atributos ou comparar revisões. Exige filtro explícito de bloco/camada.
    Parâmetros: block_filter, layer_filter, key_tag/type_tag/line_tag; nomes de atributos configuráveis.
    Exemplo: snapshot_support_register(block_filter="SUP-*", type_tag="TYPE", line_tag="LINE").
    Retorna data.snapshot para audit_support_register/compare_support_register; recusa exceder o limite.
    """
    block_filter = block_filter.strip() if block_filter else None
    layer_filter = layer_filter.strip() if layer_filter else None
    if not (block_filter or layer_filter):
        raise InvalidParameterError("Informe block_filter ou layer_filter explicitamente.")
    fields = Fields(key=key_tag, kind=type_tag, line=line_tag)
    maximum = min(s.cfg.max_batch_rows, 2000)
    rows = []
    with selection(s, types="INSERT", block=block_filter, layer=layer_filter) as sel:
        for ref in sel.iter_all():
            if len(rows) >= maximum:
                raise InvalidParameterError(f"Escopo excede {maximum} blocos; restrinja os filtros. Snapshot parcial não é emitido.")
            rows.append(read_block(ref))
    snapshot = SupportSnapshot(document=str(s.doc.Name), units_code=s.units_code, fields=fields,
                               block_filter=block_filter, layer_filter=layer_filter, rows=rows)
    return {"snapshot": snapshot.model_dump(mode="json"), "sha256": digest(snapshot), "count": len(rows),
            "note": "Editable block attributes only; generic COM, not native Plant 3D supports or engineering certification."}


@local_read_tool
def audit_support_register(snapshot: SupportSnapshot, allowed_types: list[str] | None = None,
                           expected_tags: list[str] | None = None, limit: int = 200) -> dict[str, Any]:
    """Audita TAGs duplicadas, campos vazios e cadastro esperado; totais por linha/tipo sem inferências.

    QUANDO USAR: QA de cadastro antes da entrega ou importação Excel; não dimensiona suportes.
    Parâmetros: snapshot completo, allowed_types/expected_tags fornecidos pelo projeto, limit=1..500.
    Exemplo: audit_support_register(snapshot, allowed_types=["GUIA", "ANCORA"]). Funciona sem AutoCAD.
    """
    return audit(snapshot, allowed_types, expected_tags, limit)


@local_read_tool
def compare_support_register(before: SupportSnapshot, after: SupportSnapshot, position_tolerance: float = 0.01,
                             allow_document_change: bool = False, limit: int = 200) -> dict[str, Any]:
    """Compara revisões por TAG; mostra inseridos/removidos, deslocamentos e atributos alterados.

    QUANDO USAR: revisão de cadastros de suportes com unidades/filtros idênticos; funciona sem AutoCAD.
    Parâmetros: before/after completos; position_tolerance na unidade do desenho (não tolerância normativa).
    Exemplo: compare_support_register(before, after, position_tolerance=1.0). TAGs ambíguas não são casadas.
    """
    return compare(before, after, position_tolerance, allow_document_change, limit)


TOOLS = [system_capabilities, snapshot_support_register, audit_support_register, compare_support_register]
