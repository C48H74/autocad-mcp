"""Headless demo: builds a small support drawing with dimensions and a layout, then exports a PDF. No AutoCAD needed.

Run:  python examples/dxf_headless_demo.py [output_folder]
Uses the engine directly (the same code the dxf_* MCP tools call).
"""
import sys
from pathlib import Path

from autocad_mcp import dxf_engine as eng

out = Path(sys.argv[1] if len(sys.argv) > 1 else "demo_out")
out.mkdir(parents=True, exist_ok=True)

doc = eng.create_doc("R2018", "mm")
msp = doc.modelspace()
eng.ensure_layer(doc, "EIXOS", 1)
eng.ensure_layer(doc, "COTAS", 3)
eng.add_entity(doc, msp, {"type": "line", "start": [0, 0], "end": [6000, 0], "layer": "EIXOS"})
for i, (x, kind) in enumerate([(1000, "GUIA"), (3000, "ANCORA"), (5000, "APOIO")], start=1):
    eng.insert_support_symbol(doc, kind, (x, 0, 0), tag=f"S-{i:02d}", line="10-P-1001", size=300, layer="SUPORTES")
eng.add_dimension(doc, msp, {"kind": "linear", "p1": [1000, 0], "p2": [3000, 0], "base": [0, -600], "layer": "COTAS", "dimscale": 40})
eng.add_dimension(doc, msp, {"kind": "linear", "p1": [3000, 0], "p2": [5000, 0], "base": [0, -600], "layer": "COTAS", "dimscale": 40})
eng.create_layout(doc, "Folha1", "A3", viewports=[{"center": [210, 148], "width": 380, "height": 240,
                                                 "view_center": [3000, -200], "scale": 0.05}])
doc.saveas(str(out / "demo.dxf"))
print(eng.export_render(doc, out / "demo.pdf", layout="Folha1"))
print(eng.sql_query(doc, "SELECT tag, value FROM attributes WHERE tag = 'TIPO'")["rows"])
