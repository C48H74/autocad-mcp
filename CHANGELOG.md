# Changelog

## [0.3.1] - 2026-10-05

- Docs: README architecture flowchart now shows both engines (COM and ezdxf), guards, support QA and the PDF/PNG/SVG/Excel paths.
- Corrigido: `ensure_layer` ignorava cor e tipo de linha da layer (`doc.layers.add(..., dxfattribs=)` não aplica); teste de regressão.
- Novo: cotas aceitam `lfac` (fator linear) para desenhos em escala; `export_render` aceita `size_in` (render grande) e corrige o redimensionamento da figura pelo backend.
- Novo: `examples/showcase/` (P&ID, tanque com bocais/base, arranjo geral) + testes de fumaça; galeria no README.

## 0.3.0 — Headless DXF engine, dimensions, layouts/PDF

- **50 tools** (20 new). New headless DXF engine on ezdxf, no AutoCAD needed: `dxf_info`, `dxf_query`, `dxf_get_entity`,
  `dxf_read_attributes`, `dxf_sql_query` (read-only SQL over an in-memory index), `dxf_audit`, `dxf_create`, `dxf_create_layer`,
  `dxf_add_entities`, `dxf_define_block`, `dxf_modify_entities`, `dxf_delete_entities`, `dxf_add_dimensions`, `dxf_create_layout`,
  `dxf_export` (PDF/PNG/SVG), `dxf_insert_support_symbol` (GUIA/ANCORA/APOIO/MOLA pictograms with TAG/TIPO/LINHA).
- New COM tools: `add_dimension` (native DIMENSION), `plot_to_pdf` (real "DWG To PDF.pc3" plotter), `project_data_set`/`project_data_get` (XRecord inside the DWG).
- **Security:** all file I/O (DXF, PDF, PNG, Excel) is restricted to `[paths].allowed_dirs`; with no configuration only `~/autocad-mcp-workspace` is accepted (`allow_any = true` to opt out). DXF writes are atomic and serialized; edit tools accept `output_path` to keep the original.
- Tool profiles (`server.profile` = lean/core/full) and an opt-in JSONL audit trail (`server.audit_log`, no parameters recorded).
- **Fix (found in live Plant 3D 2021 tests):** query tools created and deleted a SelectionSet, which registers an empty undo step, so the user's first Ctrl+Z after a query did nothing visible. Drawings up to `limits.scan_threshold` (3000) entities are now scanned directly; larger ones keep the SelectionSet path and warn.
- Fix: `_com` stub and read-only launch test patched the wrong COM entry point.
- Independently implemented; see NOTICE. Dependencies added: ezdxf, matplotlib.

## 0.2.0 — Support register quality and revision review

- Four additional tools: `system_capabilities`, `snapshot_support_register`, `audit_support_register`, `compare_support_register` (30 total).
- Project-configurable key/type/line attributes; duplicate and missing TAG checks, expected-register reconciliation and grouping by line/type.
- Revision matching by business key, not handle or guessed proximity. Ambiguous records remain unresolved; mismatched units/scope are refused.
- Operator-enforced read-only configuration and environment override; conservative MCP tool annotations; invalid configuration fails closed.
- Independently implemented following a source review of U-C4N/Autocad-MCP. No third-party source copied; see the comparison document.

## 0.1.0 — Initial publication

- 26 local MCP tools for AutoCAD drawing access through Windows COM.
- Session, layer, entity, drawing, block-attribute and Excel workflows; optional AutoLISP.
- Documentation in English, Portuguese and Spanish.
- Simulated CAD tests and a real stdio protocol test; separate opt-in live integration tests.
- Windows CI, contributor guidance, security documentation and issue templates.
- Limit MCP SDK to 1.x to preserve the FastMCP API used by the implementation.

Live AutoCAD/Plant 3D interoperability is not yet certified. See [validation notes](docs/validation.md).
