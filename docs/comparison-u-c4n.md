# Source comparison: U-C4N/Autocad-MCP

Review date: **2026-10-05**. Reference commit: [`cdb10638963898b3ea9b10cdd96a2c9bc495f184`](https://github.com/U-C4N/Autocad-MCP/tree/cdb10638963898b3ea9b10cdd96a2c9bc495f184). Baseline here: 0.1.0, 26 tools and 134 passing non-live tests.

## What is stronger in the reference

| Area | Evidence inspected | Assessment |
|---|---|---|
| CAD coverage | `server.py`, `backends/com_backend.py`, `backends/ezdxf_backend.py` | Much broader geometry, annotation, document and layout surface. |
| No-AutoCAD operation | ezdxf backend, backend contracts and capability declarations | A real DXF implementation, not merely simulated COM tests. DWG support has additional requirements. |
| Revision review | `engineering/understand/diff.py` | Compares entities and definitions using geometry/signatures, then conditional handle/proximity matching with declared tolerances. |
| Quality workflow | `engineering/preflight.py`, capabilities, critique/delivery modules | Explicit requirements, capability refusal and inspection are useful architectural patterns. |
| Engineering breadth | mechanical, architectural, P&ID and takeoff modules | Wider domain scope than this support/attribute-focused project. Native Plant 3D project integration is not established by these generic CAD features. |
| Evidence | README, tests, benchmark and smoke scripts | The author supplies considerably more evidence and claims live AutoCAD 2026 runs. Those live runs and the whole external test suite were not independently reproduced in this review. |

The reference README reports 247 registered tools for its release snapshot, while the repository description still says 122. Counts and self-scored benchmarks are not an independent ranking or a guarantee of correctness. Source breadth is a clear advantage; actual compatibility still depends on environment and task.

## What was adopted here

The useful concepts are explicit capabilities, pre-change quality checks and snapshot-based revision comparison. Version 0.2.0 implements them independently around a narrower workflow: **support registers keyed by the project's TAG**.

- `system_capabilities` reports configuration and unsupported features without implying a successful AutoCAD connection.
- `snapshot_support_register` captures a complete, bounded scope with configurable TAG/type/line field names.
- `audit_support_register` finds duplicate keys, missing fields, unexpected project types and missing/extra expected tags, with quantities by line/type.
- `compare_support_register` identifies moved/changed/added/removed support records. It refuses incompatible units or scope and reports ambiguous identity instead of guessing.
- Read-only mode blocks writes in the server, with MCP annotations for discovery.

This is a practical specialization, not a claim of a globally unique feature. The differentiator is a focused, testable review of support registers with Portuguese/Spanish/English documentation and explicit evidence boundaries.

## What version 0.3 adds from the review (independently implemented)

| Idea (source) | Here |
|---|---|
| Headless DXF backend, dimensions, layouts, PDF export (U-C4N, puran-water) | `dxf_*` tools on ezdxf: create/edit/query, native dimensions, paper layouts with scaled viewports, PDF/PNG/SVG export |
| SQL index over entities (easy-mcp-autocad, concept only) | `dxf_sql_query`: read-only SELECT over an in-memory SQLite index (entities, attributes) |
| Project data stored in the drawing (acad-cmd) | `project_data_set` / `project_data_get` (XRecord) |
| Audit trail (acad-cmd) | opt-in JSONL, no parameters recorded |
| Tool profiles (U-C4N) | `server.profile` lean/core/full |
| Plotting with the real plotter | `plot_to_pdf` ("DWG To PDF.pc3") |
| Symbol library (puran-water) | `dxf_insert_support_symbol`: GUIA/ANCORA/APOIO/MOLA pictograms with TAG/TIPO/LINHA |

Not adopted: the .NET plugin approach (DeepBIM), multi-CAD (ZWCAD/BricsCAD) backends, NLP command parsing, a dashboard, 3D solids and the very large tool surface of the reference. The DXF renderer is ezdxf/matplotlib, not the AutoCAD plotter, so output is approximate. DWG files cannot be read without AutoCAD; export DXF first.

## Licensing

The reference is MIT licensed. **No reference source code was copied.** Concepts were reimplemented; see [NOTICE](../NOTICE). Any future copied code must retain the upstream notice.
