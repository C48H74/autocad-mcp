"""Galeria de exemplos: desenha 4 folhas com o mesmo motor que as ferramentas dxf_* usam e exporta PNG + DXF.

Uso:  python examples/gallery.py [pasta_saida]     (não precisa de AutoCAD)
"""
import math
import sys
from pathlib import Path

from autocad_mcp import dxf_engine as eng

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/images")
OUT.mkdir(parents=True, exist_ok=True)


def new(units="mm"):
    doc = eng.create_doc("R2018", units)
    for name, color, lt in [("TUBO", 4, None), ("EIXO", 1, "DASHDOT"), ("COTAS", 3, None), ("SUPORTES", 30, None),
                            ("TEXTO", 7, None), ("EQUIP", 6, None), ("VALV", 2, None)]:
        eng.ensure_layer(doc, name, color, lt)
    return doc, doc.modelspace()


def ent(doc, msp, **spec):
    return eng.add_entity(doc, msp, spec)


def dim(doc, msp, **spec):
    spec.setdefault("layer", "COTAS")
    return eng.add_dimension(doc, msp, spec)


def pipe(doc, msp, pts, od, layer="TUBO"):
    """Tubo em vista de planta como duas paralelas (OD) + eixo."""
    h = od / 2
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        dx, dy = x2 - x1, y2 - y1
        L = math.hypot(dx, dy)
        nx, ny = -dy / L * h, dx / L * h
        for s in (1, -1):
            ent(doc, msp, type="line", start=[x1 + s * nx, y1 + s * ny], end=[x2 + s * nx, y2 + s * ny], layer=layer)
        ent(doc, msp, type="line", start=[x1, y1], end=[x2, y2], layer="EIXO")


def save(doc, name, layout=None, dpi=170, background="black"):
    doc.saveas(str(OUT / f"{name}.dxf"))
    r = eng.export_render(doc, OUT / f"{name}.png", layout=layout, dpi=dpi, background=background)
    print(name, r["bytes"], "bytes")


# 1 ---------------------------------------------------------------- suportes em planta
doc, msp = new()
pipe(doc, msp, [(0, 0), (9000, 0)], 273)
kinds = [(1000, "ANCORA"), (3000, "GUIA"), (5000, "APOIO"), (7000, "GUIA"), (9000, "MOLA")]
kinds = [(x, k) for x, k in kinds if k in eng.SUPPORT_SYMBOLS] or [(1000, "GUIA")]
for i, (x, k) in enumerate(kinds, 1):
    eng.insert_support_symbol(doc, k, (x, -450, 0), tag=f"S-{i:02d}", line="10-P-1001", size=500, layer="SUPORTES")
for (xa, _), (xb, _) in zip(kinds, kinds[1:]):
    dim(doc, msp, kind="linear", p1=[xa, -450], p2=[xb, -450], base=[0, -1500], dimscale=60, text_height=2.5)
ent(doc, msp, type="text", text="LINHA 10\"-P-1001-CS300 | PLANTA DE SUPORTES", insert=[0, 900], height=180, layer="TEXTO")
save(doc, "01_suportes_planta")

# 2 ---------------------------------------------------------------- planta de tubulação com equipamento, curvas e válvula
doc, msp = new()
ent(doc, msp, type="circle", center=[0, 0], radius=1400, layer="EQUIP")
ent(doc, msp, type="circle", center=[0, 0], radius=1250, layer="EQUIP")
ent(doc, msp, type="text", text="V-101", insert=[-330, -60], height=260, layer="TEXTO")
route = [(1400, 0), (5500, 0), (5500, 4500), (10500, 4500)]
pipe(doc, msp, route, 324)
ent(doc, msp, type="polyline", points=[[3300, -330], [3300, 330], [3800, 0]], closed=True, layer="VALV")
ent(doc, msp, type="polyline", points=[[4300, -330], [4300, 330], [3800, 0]], closed=True, layer="VALV")
ent(doc, msp, type="text", text="XV-101", insert=[3250, 480], height=170, layer="TEXTO")
for x in (1650, 7800):
    y = 0 if x < 5000 else 4500
    ent(doc, msp, type="line", start=[x, y - 330], end=[x, y + 330], layer="TUBO")
ent(doc, msp, type="polyline", points=[[10500, 4150], [11100, 4150], [11100, 4850], [10500, 4850]],
    closed=True, layer="EQUIP")
ent(doc, msp, type="text", text="P-201", insert=[10620, 4430], height=170, layer="TEXTO")
dim(doc, msp, kind="linear", p1=[1400, 0], p2=[5500, 0], base=[0, -1800], dimscale=120)
dim(doc, msp, kind="linear", p1=[5500, 4500], p2=[10500, 4500], base=[0, 5800], dimscale=120)
dim(doc, msp, kind="linear", p1=[5500, 0], p2=[5500, 4500], base=[7000, 0], angle=90, dimscale=120)
dim(doc, msp, kind="diameter", center=[0, 0], radius=1400, angle=225, dimscale=120)
ent(doc, msp, type="text", text="12\"-HC-2204-CS300  (PLANTA)", insert=[1700, 2300], height=230, layer="TEXTO")
save(doc, "02_planta_tubulacao")

# 3 ---------------------------------------------------------------- isométrico 2D (30°) com cotas alinhadas
doc, msp = new()
c, s = math.cos(math.radians(30)), math.sin(math.radians(30))
def iso(x, y, z):  # x -> direita/cima, y -> esquerda/cima, z -> vertical
    return (round((x - y) * c, 1), round((x + y) * s + z, 1))
route3 = [(0, 0, 0), (0, 0, 3000), (4000, 0, 3000), (4000, 3000, 3000), (4000, 3000, 800)]
pts = [iso(*p) for p in route3]
for a, b in zip(pts, pts[1:]):
    ent(doc, msp, type="line", start=list(a), end=list(b), layer="TUBO", lineweight=50)
for a, b, off in [(pts[0], pts[1], 450), (pts[1], pts[2], 450), (pts[2], pts[3], -450), (pts[3], pts[4], -450)]:
    dim(doc, msp, kind="aligned", p1=list(a), p2=list(b), offset=off, dimscale=60)
mid = ((pts[1][0] + pts[2][0]) / 2, (pts[1][1] + pts[2][1]) / 2)
ent(doc, msp, type="text", text="EL +103.000", insert=[pts[1][0] - 2300, pts[1][1] - 100], height=180, layer="TEXTO")
ent(doc, msp, type="text", text="ISO 10\"-P-1001-CS300-01  |  FL 1/1", insert=[pts[0][0] - 1200, pts[0][1] - 900],
    height=200, layer="TEXTO")
for p in (pts[0], pts[-1]):
    ent(doc, msp, type="circle", center=list(p), radius=120, layer="VALV")
save(doc, "03_isometrico_2d")

# 4 ---------------------------------------------------------------- folha A3 com carimbo, viewport 1:50 e tabela de suportes
doc, msp = new()
pipe(doc, msp, [(0, 0), (9000, 0), (9000, 4500)], 273)
for i, (x, y) in enumerate([(1500, -450), (4500, -450), (7500, -450)], 1):
    eng.insert_support_symbol(doc, "GUIA", (x, y, 0), tag=f"S-{i:02d}", line="10-P-1001", size=500, layer="SUPORTES")
dim(doc, msp, kind="linear", p1=[0, 0], p2=[9000, 0], base=[0, -1700], dimscale=100)
eng.create_layout(doc, "A3", "A3", margins_mm=5.0,
                  viewports=[{"center": [210, 168], "width": 390, "height": 215, "view_center": [4500, 1900], "scale": 0.025}])
lay = doc.layouts.get("A3")
ensure = eng.ensure_layer
ensure(doc, "FOLHA", 7)
lay.add_lwpolyline([(5, 5), (415, 5), (415, 292), (5, 292)], close=True, dxfattribs={"layer": "FOLHA"})
lay.add_lwpolyline([(215, 5), (415, 5), (415, 38), (215, 38)], close=True, dxfattribs={"layer": "FOLHA"})
for y in (16, 27):
    lay.add_line((215, y), (415, y), dxfattribs={"layer": "FOLHA"})
lay.add_line((315, 5), (315, 38), dxfattribs={"layer": "FOLHA"})
for txt, p in [("PLANTA DE SUPORTES 10\"-P-1001", (218, 30)), ("DES.: MCP", (218, 19)),
               ("ESCALA 1:40", (318, 19)), ("DOC: DES-SUP-001  REV. A", (218, 8)), ("FOLHA 1/1  A3", (318, 8))]:
    lay.add_text(txt, height=2.8, dxfattribs={"layer": "FOLHA", "insert": p})
save(doc, "04_folha_a3_carimbo", layout="A3", dpi=130, background="white")
print("pronto:", sorted(p.name for p in OUT.glob("*.png")))
