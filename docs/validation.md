# Validation record

## Version 0.3.0 — 2026-10-05

Environment: Windows (x64), Python 3.14.3, pywin32 312, MCP SDK 1.30.0, ezdxf 1.4.4, matplotlib 3.11.2, **AutoCAD Plant 3D 2021** (acad.exe 24.0.47.0), a disposable drawing named `MCP_TEST.dwg`.

| Check | Result |
|---|---|
| `pytest -m "not autocad"` on Windows / Python 3.14 | **184 passed**, 7 deselected |
| `pytest -m "not autocad"` on Linux / Python 3.11 (offline DXF engine, protocol, simulated COM) | **184 passed**, 7 deselected |
| `pytest -m autocad` against the live Plant 3D 2021 | **7 passed** (status, layer/line round trip with confirm, block definitions, 100-block Excel import undone by **one** `_.U`, native dimensions, plot to PDF, XRecord round trip) |
| Real stdio subprocess: JSON-RPC only on stdout, 50 tools listed, DXF create/edit/dimension/PDF export, path outside the workspace refused | passed |

Live tests are manual and opt-in; CI does not run them. The 7 live tests ran once on one machine and one AutoCAD build after the fixes below. They do **not** certify other AutoCAD or Plant 3D versions, native Plant 3D piping objects, rotated UCS, or production drawings.

### Defects found by the live run and fixed in 0.3.0

1. **Phantom undo step.** Creating/deleting a SelectionSet (used by every query tool) registers an empty undo step in AutoCAD: after a query the user's first Ctrl+Z appeared to do nothing. Measured: add+select+delete needs 2 undos, direct ModelSpace iteration needs 1. Drawings up to `limits.scan_threshold` (3000) entities are now scanned directly; larger ones keep the SelectionSet path and return a warning. The unit test only proves that the small-drawing path creates no SelectionSet; the undo behaviour itself is a live-measured fact.
2. **XRecord read.** `GetXRecordData` with `VARIANT(VT_BYREF)` arguments returns empty through pywin32 late binding; calling it with no arguments returns `(types, data)`.
3. **Concurrency in the DXF tools.** Concurrent calls on the same file raced; local tools are now serialized and DXF saves are atomic (temp file + replace).
4. The read-only launch test patched the wrong COM entry point and could have attached to a running AutoCAD.

### Known limits

- `dxf_export` is an ezdxf/matplotlib rendering, not the AutoCAD plotter (`plot_to_pdf` uses the real plotter). Text uses a substitute font and hatch/lineweight fidelity is approximate.
- Dimension text and arrows default to 2.5 drawing units; in large drawings pass `dimscale` (an angular dimension drawn without it was not visible in a test render).
- `dxf_*` tools read DXF, not DWG. Save a DXF copy from AutoCAD first.
- One unexplained `AttributeError` on an attribute proxy was seen once in an earlier live run and was not reproduced.
- The `scan_threshold` path iterates entities over COM; very large drawings are slower or take the SelectionSet path.

## Version 0.2.0 / 0.1.0 (historical)

0.2.0 added the support register QA tools (162 non-live tests at the time). 0.1.0 reported 134 non-live tests. Those runs used simulated AutoCAD only.

## CI

`.github/workflows/tests.yml` runs the non-live suite on Windows (Python 3.11–3.14) and Linux (3.12) and builds the package. It has **not been executed remotely yet**; a badge is not evidence until the first run completes.

## Live validation procedure

Create `MCP_TEST.dwg` with layers and a block `SUP-TEST` with attributes TAG/TIPO/LINHA (see the README in [Português](../README.pt-BR.md) or [Español](../README.es.md)), open it as the only drawing, and run `python -m pytest -m autocad -v`. Record the AutoCAD build, Python environment and counts. Do not touch AutoCAD while the tests run. Tests refuse any drawing whose name does not start with `MCP_TEST`.
