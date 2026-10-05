"""Exemplo 3 - Arranjo geral (plot plan) 1:250: vias, tanques com dique, bombas, tubovia, trocador, prédios, incêndio, cotas e quadros."""
import math
import sys
from pathlib import Path

from common import *  # noqa

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "../../docs/images")
doc = new_doc()
doc.layers.get("PISTA").dxf.color = 2
doc.layers.get("TUBOVIA").dxf.color = 140
for nm, col in [("COORD", 8), ("HIDRANTE", 1), ("DRENO", 5), ("ILUM", 7)]:
    eng.ensure_layer(doc, nm, col, "DASHED" if nm == "DRENO" else None)
d = D(doc, doc.modelspace())
x0, y0, x1, y1 = frame(d, "A1")
d.text("ARRANJO GERAL (PLOT PLAN)  -  UNIDADE DE TRANSFERÊNCIA E AQUECIMENTO", (x0 + 6, y1 - 12), 6, "CARIMBO_TXT")
d.line((x0 + 6, y1 - 15), (x0 + 400, y1 - 15), "CARIMBO")
d.text("Áreas 100 (armazenamento), 110 (bombeamento), 120 (aquecimento), prédios, utilidades de incêndio e tubovia  -  ESCALA 1:250  -  cotas em metros",
       (x0 + 6, y1 - 20.5), 2.8, "TEXTO_NOTA")

K = 4.0            # 1 m = 4 mm de papel (1:250)
OX, OY = 38.0, 172.0
def P(x, y): return (OX + x * K, OY + y * K)
def line(a, b, layer="EDIF", **kw): return d.line(P(*a), P(*b), layer, **kw)
def rect(xa, ya, xb, yb, layer="EDIF", **kw): return d.poly([P(xa, ya), P(xb, ya), P(xb, yb), P(xa, yb)], layer, True, **kw)
def circ(c, r, layer="EQUIP", **kw): return d.circle(P(*c), r * K, layer, **kw)
def txt(s, p, h=2.2, layer="TEXTO", **kw): return d.text(s, P(*p), h, layer, **kw)
def hatch(xa, ya, xb, yb, pat="ANSI31", sc=2.0, col=8): return d.hatch_pat([P(xa, ya), P(xb, ya), P(xb, yb), P(xa, yb)], pat, sc, col)
def solid(xa, ya, xb, yb, col=8): return d.hatch_solid([P(xa, ya), P(xb, ya), P(xb, yb), P(xa, yb)], col)
def dim(a, b, base, vertical=False, text=None, **kw):
    kw.setdefault("layer", "COTAS")
    if vertical:
        return d.dim("linear", p1=list(P(*a)), p2=list(P(*b)), base=[P(base, 0)[0], OY], angle=90, lfac=1 / K, decimals=1, text=text, **kw)
    return d.dim("linear", p1=list(P(*a)), p2=list(P(*b)), base=[OX, P(0, base)[1]], lfac=1 / K, decimals=1, text=text, **kw)

def rounded(xa, ya, xb, yb, r, layer, **kw):
    b = math.tan(math.pi / 8)
    pts = [(xa + r, ya, 0, 0, 0), (xb - r, ya, 0, 0, b), (xb, ya + r, 0, 0, 0), (xb, yb - r, 0, 0, b), (xb - r, yb, 0, 0, 0), (xa + r, yb, 0, 0, b), (xa, yb - r, 0, 0, 0), (xa, ya + r, 0, 0, b)]
    pts = [(P(x, y)[0], P(x, y)[1], s, e, bb) for x, y, s, e, bb in pts]
    return d.sp.add_lwpolyline(pts, close=True, dxfattribs={"layer": layer, **kw})

# ----------------------------------------------------------------- grade de coordenadas (a cada 20 m)
for gx in range(0, 131, 20):
    for gy in range(0, 96, 20):
        px, py = P(gx, gy)
        d.line((px - 3, py), (px + 3, py), "COORD"); d.line((px, py - 3), (px, py + 3), "COORD")
for gx in range(0, 131, 20):
    d.text(f"E {1000 + gx:.0f}", P(gx, -3.2), 1.9, "COORD", align="MIDDLE_CENTER")
for gy in range(0, 96, 20):
    d.text(f"N {5000 + gy:.0f}", (P(-1.6, gy)[0], P(0, gy)[1]), 1.9, "COORD", rot=90, align="MIDDLE_CENTER")

# ----------------------------------------------------------------- cerca, portão, vias
fence = lambda a, b: (line(a, b, "CERCA"))
fence((0, 0), (4, 0)); fence((12, 0), (130, 0)); fence((130, 0), (130, 95)); fence((130, 95), (0, 95)); fence((0, 95), (0, 0))
for i in range(0, 131, 5):
    if not 4 < i < 12:
        d.line(P(i, 0), P(i, 0.9), "CERCA")
rounded(6.5, 6.5, 123.5, 88.5, 7, "PISTA"); rounded(13.5, 13.5, 116.5, 81.5, 2, "PISTA")
line((4, 0), (4, 6.5), "PISTA"); line((12, 0), (12, 6.5), "PISTA")
for yy in (44.5, 51.5):
    line((13.5, yy), (56.5, yy), "PISTA"); line((63.5, yy), (116.5, yy), "PISTA")
for xx in (56.5, 63.5):
    line((xx, 13.5), (xx, 44.5), "PISTA"); line((xx, 51.5), (xx, 81.5), "PISTA")
line((10, 13.5), (10, 13.5), "PISTA")
for (cx, cy, sx, sy) in [(56.5, 44.5, -1, -1), (63.5, 44.5, 1, -1), (56.5, 51.5, -1, 1), (63.5, 51.5, 1, 1)]:   # raios de curva nos cruzamentos
    pass
line((8, 0), (8, 6.5), "EIXO"); line((9, 9), (9, 9), "EIXO")
txt("PORTÃO DE ACESSO", (8, -4.8), 2.0, "TEXTO", align="MIDDLE_CENTER")
dim((4, 0), (12, 0), -8.6, text="<>")
# eixo das vias e setas de sentido
for a, b in [((10, 10), (120, 10)), ((120, 10), (120, 85)), ((120, 85), (10, 85)), ((10, 85), (10, 10)), ((60, 13.5), (60, 81.5)), ((13.5, 48), (116.5, 48))]:
    line(a, b, "EIXO")
txt("VIA INTERNA 7,0 m", (35, 48.0), 2.0, "TEXTO_NOTA", align="MIDDLE_CENTER"); txt("VIA INTERNA 7,0 m", (90, 48.0), 2.0, "TEXTO_NOTA", align="MIDDLE_CENTER")
dim((56.5, 40), (63.5, 40), 38.5)

# ----------------------------------------------------------------- ÁREA 100: tanques e dique
rect(16, 55, 45, 79, "EQUIP", lineweight=60); rect(16.6, 55.6, 44.4, 78.4, "EQUIP_DET")
for (a, b, c, e) in [(16, 55, 45, 55.6), (16, 78.4, 45, 79), (16, 55, 16.6, 79), (44.4, 55, 45, 79)]:
    solid(a, b, c, e, 8)
txt("DIQUE DE CONTENÇÃO D-100 (29 x 24 m, H = 1,2 m)", (30.5, 76.4), 2.0, "TEXTO_NOTA", align="MIDDLE_CENTER")
for tag_, cx_, fut in [("TK-101", 24, False), ("TK-102", 33, False), ("TK-103", 41.5, True)]:
    lay_ = "EQUIP" if not fut else "OCULTA"
    circ((cx_, 68), 2.0 if not fut else 1.5, lay_, lineweight=50); circ((cx_, 68), 1.65 if not fut else 1.2, "EQUIP_DET")
    d.line(P(cx_ - 2.6, 68), P(cx_ + 2.6, 68), "EIXO"); d.line(P(cx_, 65.4), P(cx_, 70.6), "EIXO")
    txt(tag_, (cx_, 64.2), 2.8, "TAG", align="MIDDLE_CENTER")
    txt("(FUTURO)" if fut else "50 m³", (cx_, 62.3), 1.9, "TEXTO_NOTA", align="MIDDLE_CENTER")
d.dim("aligned", p1=list(P(24, 68)), p2=list(P(33, 68)), offset=-27.0 * 0 + 12.5, lfac=1 / K, decimals=1, layer="COTAS", dimstyle="MCP")
dim((16, 55), (45, 55), 52.6, text="<>"); dim((45, 55), (45, 79), 47.5, vertical=True, text="<>")
d.leader(P(25.8, 69.4), P(18, 85.5), "Escada helicoidal /\nplataforma de topo", 2.0)
# bacia / sump
rect(18.5, 56.6, 21.5, 59.6, "EQUIP_DET"); line((18.5, 56.6), (21.5, 59.6), "EQUIP_DET"); line((18.5, 59.6), (21.5, 56.6), "EQUIP_DET"); txt("SUMP-01", (20, 55.0), 1.7, "TEXTO_NOTA", align="MIDDLE_CENTER") if False else None

# ----------------------------------------------------------------- ÁREA 110: bombas
hatch(47, 54, 56, 66, "ANSI31", 1.2, 8); rect(47, 54, 56, 66, "EQUIP_DET")
for tag_, py in [("P-101A", 62.8), ("P-101B", 57.2)]:
    rect(49, py - 0.9, 52.2, py + 0.9, "EQUIP"); circ((50.1, py), 0.7, "EQUIP"); txt(tag_, (53.1, py - 0.4), 1.8, "TAG")
txt("ÁREA 110", (51.5, 67.2), 2.4, "LEGENDA", align="MIDDLE_CENTER"); txt("BOMBEAMENTO", (51.5, 65.9) if False else (51.5, 68.4 - 0.2), 1.8, "TEXTO_NOTA", align="MIDDLE_CENTER") if False else None
dim((47, 54), (47, 66), 44.7, vertical=True, text="<>"); dim((47, 54), (56, 54), 52.8, text="<>") if False else None
# linhas: sucção N2 -> bombas; descarga -> tubovia
pl = lambda pts, lay="LINHA_PROC": d.poly([P(*q) for q in pts], lay)
pl([(26, 66), (26, 60), (49, 60), (49, 62.8)]); pl([(49, 60), (49, 57.2)]); pl([(52.2, 62.8), (54.5, 62.8), (54.5, 54.1), (53.5, 54.1)]) if False else None
pl([(52.2, 62.8), (54.5, 62.8), (54.5, 57.2), (52.2, 57.2)]); pl([(54.5, 57.2), (54.5, 55.0), (55.0, 54.0), (54.8, 54.0)]) if False else None
pl([(54.5, 60), (54.5, 54.0)]) if False else pl([(54.5, 57.2), (54.5, 54.0)])
# ----------------------------------------------------------------- TUBOVIA (pipe rack)
colsx = [53, 55, 65, 71, 77, 83, 89]
rect(53, 53.3, 92, 55.7, "TUBOVIA", lineweight=35)
for i, cx_ in enumerate(colsx):
    rect(cx_ - 0.25, 53.05, cx_ + 0.25, 53.55, "TUBOVIA"); rect(cx_ - 0.25, 55.45, cx_ + 0.25, 55.95, "TUBOVIA")
    txt(f"PR-{i+1:02d}", (cx_, 56.4), 1.5, "TEXTO_NOTA", align="MIDDLE_CENTER")
pl([(54.5, 54.0), (73.5, 54.0), (73.5, 61.2)], "LINHA_PROC"); pl([(80.5, 61.2), (82, 61.2), (82, 54.0), (92, 54.0)], "LINHA_PROC")
pl([(92, 54.8), (77, 54.8), (77, 63.2)], "LINHA_UTIL"); pl([(78.2, 59.9), (78.2, 55.2), (92, 55.2)], "LINHA_UTIL")
txt('6"-P-1003-CS150-N', (56, 52.4), 1.7, "TAG"); txt('2"-LS-3001-CS150-H', (84.5, 56.4), 1.5, "TAG") if False else None
d.arrow(P(60, 54.0), 0, 2.0, "LINHA_PROC"); d.arrow(P(86, 54.8), 180, 2.0, "LINHA_UTIL"); d.arrow(P(90.5, 55.2), 0, 2.0, "LINHA_UTIL")
d.text("TUBOVIA TV-01", P(72, 50.4), 2.3, "TUBOVIA", align="MIDDLE_CENTER") if False else None
d.leader(P(70, 55.7), P(70, 47.0), "Tubovia TV-01\n3 linhas / bays de 6,0 m", 2.0)
dd = [(53, 55, 51.6), (55, 65, 51.6), (65, 71, 51.6), (71, 77, 51.6), (77, 83, 51.6), (83, 89, 51.6)]
for xa, xb, by in dd:
    d.dim("linear", p1=list(P(xa, 53.05)), p2=list(P(xb, 53.05)), base=[OX, P(0, by)[1]], lfac=1 / K, decimals=1, layer="COTAS", dimstyle="MCP")
# ----------------------------------------------------------------- ÁREA 120: E-101
hatch(70, 58, 84, 66, "ANSI31", 1.2, 8); rect(70, 58, 84, 66, "EQUIP_DET")
rect(74, 61.0, 80, 62.4, "EQUIP", lineweight=60); rect(73.2, 61.2, 74, 62.2, "EQUIP"); rect(80, 61.2, 80.8, 62.2, "EQUIP")
txt("E-101", (77, 64.2), 2.8, "TAG", align="MIDDLE_CENTER"); txt("TROCADOR CASCO-TUBO", (77, 66.6), 1.8, "TEXTO_NOTA", align="MIDDLE_CENTER")
dim((70, 58), (84, 58), 56.4 if False else 57.0, text="<>") if False else None
d.dim("linear", p1=list(P(70, 66)), p2=list(P(84, 66)), base=[OX, P(0, 68.4)[1]], lfac=1 / K, decimals=1, layer="COTAS", dimstyle="MCP")
d.dim("linear", p1=list(P(84, 58)), p2=list(P(84, 66)), base=[P(86.2, 0)[0], OY], angle=90, lfac=1 / K, decimals=1, layer="COTAS", dimstyle="MCP")
txt("ÁREA 120 - AQUECIMENTO", (77, 70.0), 2.3, "LEGENDA", align="MIDDLE_CENTER")
# U-200 existente e limite de bateria
hatch(93, 53, 114, 80, "ANSI31", 4.0, 8); rect(93, 53, 114, 80, "AREA", lineweight=50)
txt("UNIDADE 200", (103.5, 70), 3.2, "CARIMBO_TXT", align="MIDDLE_CENTER"); txt("(EXISTENTE - FORA DE ESCOPO)", (103.5, 67), 1.9, "TEXTO_NOTA", align="MIDDLE_CENTER")
d.line(P(92, 52), P(92, 81), "AREA", lineweight=60); txt("LIMITE DE BATERIA (LB)", (91.0, 81.8), 1.8, "LEGENDA", align="MIDDLE_RIGHT") if False else txt("LB", (92, 82.6), 2.2, "LEGENDA", align="MIDDLE_CENTER")

# ----------------------------------------------------------------- prédios SW
bld = [("SALA DE CONTROLE", "CR-01", 18, 33, 32, 41), ("SUBESTAÇÃO", "SE-01", 36, 33, 46, 39), ("OFICINA / ALMOXARIFADO", "OF-01", 18, 18, 33, 27)]
for nm, tg, xa, ya, xb, yb in bld:
    hatch(xa, ya, xb, yb, "ANSI31", 3.0, 8); rect(xa, ya, xb, yb, "EDIF", lineweight=60)
    txt(nm, ((xa + xb) / 2, (ya + yb) / 2 + 0.7), 1.9, "TEXTO", align="MIDDLE_CENTER"); txt(tg, ((xa + xb) / 2, (ya + yb) / 2 - 1.6), 2.4, "TAG", align="MIDDLE_CENTER")
dim((18, 33), (32, 33), 31.0, text="<>"); dim((18, 33), (18, 41), 15.8, vertical=True, text="<>")
rect(14, 1, 17.2, 4.2, "EDIF", lineweight=50); txt("GUARITA", (15.6, 5.6), 1.7, "TEXTO_NOTA", align="MIDDLE_CENTER")
# estacionamento
rect(37, 16, 53, 26, "EDIF")
for i in range(8):
    line((37 + 2.0 * (i + 1), 16), (37 + 2.0 * (i + 1), 21), "EDIF")
txt("ESTACIONAMENTO", (45, 23.6), 2.0, "TEXTO_NOTA", align="MIDDLE_CENTER")
# ----------------------------------------------------------------- SE: incêndio, carregamento, expansão
hatch(66, 33, 76, 39, "ANSI31", 3.0, 8); rect(66, 33, 76, 39, "EDIF", lineweight=60)
txt("CASA DE BOMBAS", (71, 37.0), 1.9, "TEXTO", align="MIDDLE_CENTER"); txt("DE INCÊNDIO  BI-01", (71, 35.4), 1.9, "TEXTO", align="MIDDLE_CENTER")
circ((88, 36), 6, "EQUIP", lineweight=50); circ((88, 36), 5.4, "EQUIP_DET"); d.line(P(80.5, 36), P(95.5, 36), "EIXO"); d.line(P(88, 29), P(88, 43), "EIXO")
txt("TQ-201", (88, 36.8), 2.6, "TAG", align="MIDDLE_CENTER"); txt("ÁGUA DE INCÊNDIO 280 m³", (88, 34.4), 1.7, "TEXTO_NOTA", align="MIDDLE_CENTER")
pl([(76, 36), (82, 36)], "LINHA_UTIL")
rect(68, 16, 90, 23, "EDIF"); line((68, 19.5), (90, 19.5), "EDIF", linetype="DASHED"); rect(70, 17, 78, 22, "EDIF"); rect(80, 17, 88, 22, "EDIF")
txt("BAIA DE CARREGAMENTO DE CAMINHÕES", (79, 24.6), 1.9, "TEXTO_NOTA", align="MIDDLE_CENTER")
rect(97, 16, 114, 42, "AREA"); hatch(97, 16, 114, 42, "ANSI31", 9.0, 8)
txt("ÁREA RESERVADA PARA", (105.5, 30.5), 2.2, "LEGENDA", align="MIDDLE_CENTER"); txt("EXPANSÃO FUTURA", (105.5, 28.3), 2.2, "LEGENDA", align="MIDDLE_CENTER")
# ----------------------------------------------------------------- hidrantes, iluminação, dreno
hyd = [(14.8, 14.8), (36, 14.8), (56, 14.8), (76, 14.8), (96, 14.8), (115, 14.8), (115, 46), (115, 62), (115, 80), (96, 80), (75, 80), (58, 80), (47, 80), (14.8, 80), (14.8, 60), (14.8, 40)]
for i, (hx, hy) in enumerate(hyd, 1):
    circ((hx, hy), 0.5, "HIDRANTE"); line((hx - 0.5, hy), (hx + 0.5, hy), "HIDRANTE"); line((hx, hy - 0.5), (hx, hy + 0.5), "HIDRANTE")
    if i in (1, 4, 7, 10, 13): txt(f"H-{i:02d}", (hx + 1.2, hy + 1.2), 1.4, "HIDRANTE")
for lp in [(6, 20), (6, 50), (6, 80), (125, 20), (125, 50), (125, 80), (30, 90.5), (60, 90.5), (90, 90.5), (30, 3.5), (60, 3.5), (90, 3.5)]:
    circ(lp, 0.6, "ILUM"); line((lp[0] - 1.0, lp[1]), (lp[0] + 1.0, lp[1]), "ILUM")
pl([(14, 14.4), (116, 14.4)], "DRENO") if False else None
d.poly([P(5.2, 88.9), P(124.8, 88.9)], "DRENO"); d.arrow(P(60, 88.9), 0, 2.0, "DRENO")
txt("VALETA DE DRENAGEM PLUVIAL", (92, 90.2), 1.7, "DRENO", align="MIDDLE_CENTER")
# ----------------------------------------------------------------- cotas gerais
dim((0, 0), (130, 0), -10.5, text="<>"); dim((0, 0), (0, 95), -8.2, vertical=True, text="<>")
d.text("SITE 130,0 x 95,0 m", (P(65, 97.5)[0], P(0, 97.5)[1]), 2.8, "TEXTO", align="MIDDLE_CENTER")
# distâncias de projeto (hachuradas)
def dist(a, b, tag_, off=2.0):
    d.line(P(*a), P(*b), "LEGENDA", linetype="DASHED"); L_ = math.hypot(a[0] - b[0], a[1] - b[1])
    mx_, my_ = P((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    d.text(f"{L_:.1f}", (mx_ + 1, my_ + 1), 2.2, "LEGENDA")
    return L_
D1 = dist((24, 66), (25, 41), "TK-101-CR-01"); D2 = dist((24, 66), (50, 60), "TK-101-P-101"); D3 = dist((50, 60), (71, 36), "P-101-BI-01") if False else None
# ----------------------------------------------------------------- norte, escala gráfica
nx, ny = 812.0, 566.0
d.circle((nx, ny), 7, "NORTE"); d.poly([(nx, ny + 9), (nx - 3.2, ny - 3.5), (nx, ny - 0.7), (nx + 3.2, ny - 3.5)], "NORTE", True); d.hatch_solid([(nx, ny + 9), (nx - 3.2, ny - 3.5), (nx, ny - 0.7)], 7, "NORTE")
d.text("N", (nx, ny + 12.5), 3.4, "NORTE", align="MIDDLE_CENTER"); d.text("NORTE DE PROJETO", (nx - 22, ny - 1), 1.8, "TEXTO_NOTA", align="MIDDLE_CENTER")
sx, sy = 578.0, 572.0
for i, lab in enumerate(["0", "10", "20", "30", "40", "50 m"]):
    xx = sx + i * 10 * K
    d.line((xx, sy), (xx, sy + 2), "TEXTO"); d.text(lab, (xx, sy - 3.5), 2.0, "TEXTO", align="MIDDLE_CENTER")
    if i < 5:
        d.rect(xx, sy, 10 * K, 2, "TEXTO")
        if i % 2 == 0: d.hatch_solid([(xx, sy), (xx + 10 * K, sy), (xx + 10 * K, sy + 2), (xx, sy + 2)], 7, "TEXTO")
d.text("ESCALA GRÁFICA  (1:250)", (sx, sy + 5.5), 2.2, "TEXTO")

# ================================================================= quadros (painel direito e faixa inferior)
def table(x, y_top, w, heads, rows, widths, title, rh=5.0, h=1.9):
    d.text(title, (x, y_top + 4), 3, "CARIMBO_TXT")
    n = len(rows) + 1
    d.rect(x, y_top - rh * n, w, rh * n, "CARIMBO")
    xs = [x]
    for wi in widths[:-1]:
        xs.append(xs[-1] + wi)
    for cx in xs[1:]:
        d.line((cx, y_top - rh * n), (cx, y_top), "CARIMBO")
    for i in range(1, n):
        d.line((x, y_top - rh * i), (x + w, y_top - rh * i), "CARIMBO")
    for cx, t in zip(xs, heads):
        d.text(t, (cx + 1.2, y_top - rh + 1.6), 1.7, "TEXTO_NOTA")
    for r_i, row in enumerate(rows):
        for cx, t in zip(xs, row):
            d.text(str(t), (cx + 1.2, y_top - rh * (r_i + 2) + 1.6), h, "TEXTO")
    return y_top - rh * n

px = 570.0
EQ = [("TK-101", "Tanque de armazenamento 50 m³", 1024.0, 5068.0, "+100,30"), ("TK-102", "Tanque de armazenamento 50 m³", 1033.0, 5068.0, "+100,30"),
      ("P-101A", "Bomba centrífuga (operação)", 1050.1, 5062.8, "+100,00"), ("P-101B", "Bomba centrífuga (reserva)", 1050.1, 5057.2, "+100,00"),
      ("E-101", "Trocador casco-tubo", 1077.0, 5061.7, "+100,60"), ("TV-01", "Tubovia - início (PR-01)", 1053.0, 5054.5, "+104,50"),
      ("CR-01", "Sala de controle", 1025.0, 5037.0, "+100,50"), ("SE-01", "Subestação elétrica", 1041.0, 5036.0, "+100,50"),
      ("OF-01", "Oficina / almoxarifado", 1025.5, 5022.5, "+100,40"), ("BI-01", "Casa de bombas de incêndio", 1071.0, 5036.0, "+100,40"),
      ("TQ-201", "Reservatório de água de incêndio", 1088.0, 5036.0, "+100,20"), ("U-200", "Unidade existente (LB)", 1103.5, 5066.5, "+100,00")]
yb = table(px, y1 - 48, 258, ["TAG", "DESCRIÇÃO", "E (m)", "N (m)", "COTA"], [(a, b, f"{c:.1f}", f"{e:.1f}", g) for a, b, c, e, g in EQ], [22, 118, 36, 42, 40],
           "LISTA DE EQUIPAMENTOS E COORDENADAS")
d.text("Coordenadas locais do sítio (E/N); cota do piso acabado em metros.", (px, yb - 4), 1.8, "TEXTO_NOTA")

# quadro de distâncias (calculado das posições do desenho)
def dd_(a, b): return math.hypot(a[0] - b[0], a[1] - b[1])
pos = {"TK-101": (24, 68), "P-101": (50.1, 60), "CR-01": (25, 41), "E-101": (77, 61.7), "BI-01": (71, 36), "FENCE": (24, 95)}
rows_d = [("TK-101 / TK-102 (entre centros)", f"{dd_((24,68),(33,68)):.1f}", "≥ 6,0", "OK"),
          ("TK-101 / bomba P-101A", f"{dd_(pos['TK-101'],pos['P-101']):.1f}", "≥ 15,0", "OK" if dd_(pos['TK-101'],pos['P-101']) >= 15 else "VERIFICAR"),
          ("TK-101 / sala de controle CR-01", f"{dd_(pos['TK-101'],pos['CR-01']):.1f}", "≥ 15,0", "OK" if dd_(pos['TK-101'],pos['CR-01']) >= 15 else "VERIFICAR"),
          ("TK-101 / cerca (norte)", f"{95-68-2:.1f}", "≥ 10,0", "OK"),
          ("TK-101 / reservatório TQ-201", f"{dd_(pos['TK-101'],(88,36)):.1f}", "≥ 15,0", "OK"),
          ("E-101 / sala de controle CR-01", f"{dd_(pos['E-101'],pos['CR-01']):.1f}", "≥ 15,0", "OK"),
          ("P-101A / casa de bombas BI-01", f"{dd_(pos['P-101'],pos['BI-01']):.1f}", "≥ 15,0", "OK")]
table(24, 112, 262, ["PAR", "DIST. (m)", "MÍN. (m)", "STATUS"], rows_d, [140, 40, 40, 42], "QUADRO DE DISTÂNCIAS (CRITÉRIO FICTÍCIO)", rh=4.8, h=1.9)
# legenda
lx0, lyt = 296, 112
d.text("LEGENDA", (lx0, lyt + 4), 3, "CARIMBO_TXT")
d.rect(lx0, lyt - 4.8 * 8, 178, 4.8 * 8, "CARIMBO")
leg = [("PISTA", "Via / acesso"), ("CERCA", "Cerca do sítio"), ("EQUIP", "Equipamento / tanque"), ("TUBOVIA", "Tubovia (pipe rack)"),
       ("LINHA_PROC", "Linha de processo"), ("LINHA_UTIL", "Utilidade (vapor/água)"), ("DRENO", "Drenagem pluvial"), ("AREA", "Limite de área")]
for i, (lay, lab) in enumerate(leg):
    cy = lyt - 4.8 * i - 3.2
    d.line((lx0 + 3, cy), (lx0 + 20, cy), lay, lineweight=50); d.text(lab, (lx0 + 23, cy - 1), 2.1, "TEXTO")
for i, (sym, lab) in enumerate([("hyd", "Hidrante (H-xx)"), ("lamp", "Poste de iluminação"), ("col", "Coluna da tubovia"), ("b", "Edificação")]):
    cy = lyt - 4.8 * i - 3.2; cx = lx0 + 100
    if sym == "hyd":
        d.circle((cx + 2, cy), 1.4, "HIDRANTE"); d.line((cx, cy), (cx + 4, cy), "HIDRANTE"); d.line((cx + 2, cy - 2), (cx + 2, cy + 2), "HIDRANTE")
    elif sym == "lamp":
        d.circle((cx + 2, cy), 1.2, "ILUM"); d.line((cx - 0.5, cy), (cx + 4.5, cy), "ILUM")
    elif sym == "col":
        d.rect(cx + 0.8, cy - 1, 2, 2, "TUBOVIA")
    else:
        d.rect(cx, cy - 1.4, 5, 2.8, "EDIF")
    d.text(lab, (cx + 9, cy - 1), 2.1, "TEXTO")
# notas
notes_box(d, 296 + 190, 112, 150, ["Cotas e coordenadas em metros; escala 1:250 (A1).",
                                    "Vias com 7,0 m de largura e raio interno 2,0 m.",
                                    "Dique D-100: capacidade ≥ 110 % do maior tanque.",
                                    "Tubovia a +4,50 m sobre o piso (bays de 6,0 m).",
                                    "Rede de incêndio em anel; hidrantes a cada 30 m.",
                                    "Dados e distâncias fictícios, para demonstração do MCP."], h=2.0)
areas = [("100", "Armazenamento", "TK-101/102/103 e dique D-100"), ("110", "Bombeamento", "P-101A/B sobre laje de concreto"), ("120", "Aquecimento", "E-101 e skid de utilidades"),
         ("200", "Unidade existente", "U-200 (fora de escopo, limite LB)"), ("300", "Edificações", "CR-01, SE-01, OF-01, guarita"), ("400", "Combate a incêndio", "BI-01, TQ-201, hidrantes H-01..16"),
         ("500", "Expansão futura", "Área reservada (97-114 E / 16-42 N)")]
table(570, 455, 258, ["ÁREA", "DESCRIÇÃO", "PRINCIPAIS ITENS"], areas, [18, 56, 184], "QUADRO DE ÁREAS")

# ----------------------------------------------------------------- seções típicas (1:50)
class S:
    def __init__(self, ox, oy, sc=50): self.ox, self.oy, self.k, self.sc = ox, oy, 1.0 / sc, sc
    def p(self, x, y): return (self.ox + x * self.k, self.oy + y * self.k)
    def line(self, a, b, layer="EQUIP", **kw): return d.line(self.p(*a), self.p(*b), layer, **kw)
    def rect(self, xa, ya, xb, yb, layer="EQUIP", **kw): return d.poly([self.p(xa, ya), self.p(xb, ya), self.p(xb, yb), self.p(xa, yb)], layer, True, **kw)
    def circ(self, c, r, layer="EQUIP", **kw): return d.circle(self.p(*c), r * self.k, layer, **kw)
    def hat(self, pts, pat, sc, col=8): return d.hatch_pat([self.p(*q) for q in pts], pat, sc, col)
    def dh(self, a, b, base, text=None): return d.dim("linear", p1=list(self.p(*a)), p2=list(self.p(*b)), base=[self.ox, self.p(0, base)[1]], lfac=self.sc, text=text, decimals=0, layer="COTAS", dimstyle="MCP")
    def dv(self, a, b, base, text=None): return d.dim("linear", p1=list(self.p(*a)), p2=list(self.p(*b)), base=[self.p(base, 0)[0], self.oy], angle=90, lfac=self.sc, text=text, decimals=0, layer="COTAS", dimstyle="MCP")
# A-A: tubovia
sa = S(640, 250)
d.text("SEÇÃO A-A  -  TUBOVIA TV-01", (572, 250 + 4600 * sa.k + 24), 3.0, "CARIMBO_TXT"); d.text("ESCALA 1:50  (cotas em mm)", (572, 250 + 4600 * sa.k + 19), 2.0, "TEXTO_NOTA")
sa.line((-2400, 0), (2400, 0), "EQUIP_DET", lineweight=50)
sa.rect(-1500, -500, 1500, 0, "EQUIP_DET"); sa.hat([(-1500, -500), (1500, -500), (1500, 0), (-1500, 0)], "AR-CONC", 0.25)
for sx_ in (-1200, 1200):
    sa.rect(sx_ - 150, 0, sx_ + 150, 4400, "TUBOVIA", lineweight=50); sa.hat([(sx_ - 150, 0), (sx_ + 150, 0), (sx_ + 150, 4400), (sx_ - 150, 4400)], "ANSI31", 0.25, 140)
sa.rect(-1500, 4400, 1500, 4600, "TUBOVIA", lineweight=50); sa.hat([(-1500, 4400), (1500, 4400), (1500, 4600), (-1500, 4600)], "ANSI31", 0.25, 140)
sa.line((-1200, 2400), (0, 4400), "TUBOVIA"); sa.line((1200, 2400), (0, 4400), "TUBOVIA")            # contraventos
for cx_, od, nm, lay in [(-800, 168, '6"', "LINHA_PROC"), (0, 60, '2"', "LINHA_UTIL"), (700, 48, '1.5"', "LINHA_UTIL")]:
    sa.circ((cx_, 4600 + od / 2 + 20), od / 2, lay, lineweight=50); sa.circ((cx_, 4600 + od / 2 + 20), od / 2 + 50, "OCULTA")
    sa.rect(cx_ - od / 2 - 20, 4600, cx_ + od / 2 + 20, 4640, "EQUIP_DET")
sa.dh((-1200, 0), (1200, 0), -900, "<>"); sa.dv((0, 0), (0, 4600), -2100, "<>"); sa.dv((0, 4600), (0, 4800), 1800) if False else None
d.leader(sa.p(-800, 4780), sa.p(2000, 5200), 'Linha 6"-P-1003-CS150-N', 2.0); d.leader(sa.p(0, 4720), sa.p(2000, 5900), 'Linha 2"-LS-3001-CS150-H', 2.0); d.leader(sa.p(700, 4690), sa.p(2000, 6600), 'Linha 1,5"-CD-3002-CS150-H', 2.0)
d.leader(sa.p(1200, 1500), sa.p(2100, 2600), "Coluna HEB 300 (PR-xx)", 2.0); d.leader(sa.p(-1100, -200), sa.p(-2300, -900 + 1500), "Sapata de concreto", 2.0) if False else d.leader(sa.p(1100, -300), sa.p(1700, -1100), "Sapata de concreto C30", 2.0)
sa.dh((-1200, 4600), (1200, 4600), 5250, "<>") if False else None
d.text("TOPO DE AÇO  EL +104,50", (sa.p(-2900, 0)[0], sa.p(0, 4700)[1] + 3), 2.0, "TEXTO_NOTA")
# B-B: via interna
sb = S(720, 140)
d.text("SEÇÃO B-B  -  VIA INTERNA", (650, 140 + 34), 3.0, "CARIMBO_TXT"); d.text("ESCALA 1:50  (cotas em mm)", (650, 140 + 29.5), 2.0, "TEXTO_NOTA")
sb.line((-4800, -450), (4800, -450), "EQUIP_DET")
top = [(-3500, 0), (0, 70), (3500, 0)]
d.poly([sb.p(*q) for q in top], "PISTA", lineweight=50)
sb.hat([(-3500, -50), (0, 20), (3500, -50), (3500, 0), (0, 70), (-3500, 0)], "ANSI31", 0.18, 252)
d.poly([sb.p(-3500, -50), sb.p(0, 20), sb.p(3500, -50)], "EQUIP_DET")
d.poly([sb.p(-3500, -200), sb.p(0, -130), sb.p(3500, -200)], "EQUIP_DET")
sb.hat([(-3500, -200), (0, -130), (3500, -200), (3500, -50), (0, 20), (-3500, -50)], "GRAVEL", 0.2, 8)
sb.rect(-3500, -450, 3500, -200, "EQUIP_DET"); sb.hat([(-3500, -450), (3500, -450), (3500, -200), (-3500, -200)], "EARTH", 0.2, 8)
for sgn in (-1, 1):                                                       # valetas
    d.poly([sb.p(sgn * 3500, 0), sb.p(sgn * 3900, -250), sb.p(sgn * 4300, -250), sb.p(sgn * 4700, 0)], "DRENO")
sb.dh((-3500, 0), (3500, 0), -900, "<>"); sb.dv((3500, -200), (3500, 0), 4300) if False else None
d.leader(sb.p(0, 40), sb.p(1500, 1200), "Capa asfáltica CBUQ e = 50 mm", 2.0); d.leader(sb.p(1000, -90), sb.p(1700, 600 + 300), "Base de brita graduada e = 150 mm", 2.0) if False else d.leader(sb.p(1500, -110), sb.p(2000, 700), "Base brita graduada e = 150 mm", 2.0)
d.leader(sb.p(-1500, -330), sb.p(-1800, -1500), "Sub-base / solo compactado e = 250 mm", 2.0)
d.text("Declividade transversal 2 %", (sb.p(-3500, 0)[0], sb.p(0, 600)[1]), 1.9, "TEXTO_NOTA")
d.text("Valeta pluvial", (sb.p(4000, 0)[0] - 8, sb.p(0, -700)[1]), 1.7, "DRENO")

# carimbo
tbx, tby = title_block(d, x1, y0, "ARRANJO GERAL (PLOT PLAN)", "Unidade de transferência e aquecimento - Áreas 100/110/120", "EX-ARR-000-001", "0", "1:250", "A1", "1/1")
revision_table(d, x1, tby, [("0", "05/10/26", "EMISSÃO PARA DEMONSTRAÇÃO DO MCP", "MCP", "—", "—")], 190)
save(doc, OUT, "07_layout_arranjo_geral")
