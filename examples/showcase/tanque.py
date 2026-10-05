"""Exemplo 2 - Tanque TK-101 (50 m³): elevação 1:30, planta 1:30, detalhes 1:5, tabela de bocais, dados de projeto e lista de materiais."""
import math
import sys
from pathlib import Path

from common import *  # noqa

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "../../docs/images")
doc = new_doc()
d = D(doc, doc.modelspace())
x0, y0, x1, y1 = frame(d, "A1")
d.text("TANQUE TK-101  -  ARRANJO GERAL, BOCAIS E BASE", (x0 + 6, y1 - 12), 6, "CARIMBO_TXT")
d.line((x0 + 6, y1 - 15), (x0 + 330, y1 - 15), "CARIMBO")
d.text("Tanque atmosférico vertical de teto cônico, 50 m³ (Ø4000 x 4000), sobre anel de concreto - dimensões em mm", (x0 + 6, y1 - 20.5), 2.8, "TEXTO_NOTA")


class V:
    """Vista em escala: converte coordenadas reais (mm) em milímetros de papel."""
    def __init__(self, ox, oy, scale):
        self.ox, self.oy, self.k = ox, oy, 1.0 / scale
        self.scale = scale

    def p(self, x, y):
        return (self.ox + x * self.k, self.oy + y * self.k)

    def line(self, a, b, layer="EQUIP", **kw):
        return d.line(self.p(*a), self.p(*b), layer, **kw)

    def poly(self, pts, layer="EQUIP", close=False, **kw):
        return d.poly([self.p(*q) for q in pts], layer, close, **kw)

    def rect(self, xa, ya, xb, yb, layer="EQUIP", **kw):
        return self.poly([(xa, ya), (xb, ya), (xb, yb), (xa, yb)], layer, True, **kw)

    def circle(self, c, r, layer="EQUIP", **kw):
        return d.circle(self.p(*c), r * self.k, layer, **kw)

    def arc(self, c, r, a0, a1, layer="EQUIP", **kw):
        return d.arc(self.p(*c), r * self.k, a0, a1, layer, **kw)

    def hatch(self, pts, pattern="ANSI31", scale=1.0, color=8):
        return d.hatch_pat([self.p(*q) for q in pts], pattern, scale, color)

    def solid(self, pts, color=7):
        return d.hatch_solid([self.p(*q) for q in pts], color)

    def text(self, s, p, h=2.5, layer="TEXTO", **kw):
        return d.text(s, self.p(*p), h, layer, **kw)

    def dim_h(self, xa, xb, ya, yb, base_y, text=None, **kw):
        return d.dim("linear", p1=list(self.p(xa, ya)), p2=list(self.p(xb, yb)), base=[self.ox, self.p(0, base_y)[1]], lfac=self.scale, text=text, **kw)

    def dim_v(self, ya, yb, x, base_x, text=None, **kw):
        return d.dim("linear", p1=list(self.p(x, ya)), p2=list(self.p(x, yb)), base=[self.p(base_x, 0)[0], self.oy], angle=90, lfac=self.scale, text=text, **kw)

    def dim_al(self, a, b, offset, text=None, **kw):
        return d.dim("aligned", p1=list(self.p(*a)), p2=list(self.p(*b)), offset=offset, lfac=self.scale, text=text, **kw)

    def axis(self, a, b):
        return self.line(a, b, "EIXO")


# ================================================================== dados do tanque (mm)
R = 2000            # raio interno
H = 4000            # altura da casca
BOT = 300           # cota do fundo (topo do anel de concreto)
TOP = BOT + H       # junção casca/teto
RISE = 400          # flecha do teto (1:5)
APEX = TOP + RISE
NOZ = {  # marca: (DN, descrição, OD tubo, OD flange, esp. flange, projeção da face do flange ao casco, elevação do eixo acima do fundo, azimute, classe)
    "N1": ('6"', "Entrada de produto", 168.3, 279, 22, 350, 3400, 270, "150# RFWN"),
    "N2": ('8"', "Saída de produto", 219.1, 343, 25, 400, 350, 90, "150# RFWN"),
    "N5": ('2"', "Nível - tomada superior (LT-101)", 60.3, 152, 19, 250, 3650, 80, "150# RFWN"),
    "N6": ('2"', "Nível - tomada inferior (LT-101)", 60.3, 152, 19, 250, 650, 100, "150# RFWN"),
    "N7": ('4"', "Retorno de recirculação", 114.3, 229, 24, 300, 2900, 285, "150# RFWN"),
}

# ================================================================== ELEVAÇÃO (vista pelo sul) 1:25
E = V(150, 262, 30)
d.text("ELEVAÇÃO (VISTA SUL)", (E.p(-3000, 0)[0], E.p(0, 6400)[1]), 4.0, "CARIMBO_TXT"); d.text("ESCALA 1:30", (E.p(-3000, 0)[0], E.p(0, 6400)[1] - 5), 2.4, "TEXTO_NOTA")
# terreno, fundação e anel de concreto
E.line((-3200, 0), (3200, 0), "EQUIP_DET", lineweight=50)
for xg in range(-3200, 3201, 200):
    E.line((xg, 0), (xg - 120, -120), "HACHURA")
E.rect(-2600, -600, 2600, 0, "EQUIP_DET"); E.hatch([(-2600, -600), (2600, -600), (2600, 0), (-2600, 0)], "AR-CONC", 0.3, 8)
E.rect(-2300, 0, 2300, BOT, "EQUIP_DET"); E.hatch([(-2300, 0), (2300, 0), (2300, BOT), (-2300, BOT)], "ANSI31", 0.4, 8)
E.line((-1700, 0), (-1700, BOT), "OCULTA"); E.line((1700, 0), (1700, BOT), "OCULTA")
# chapa do fundo, casca e teto
E.line((-2060, BOT), (2060, BOT), "EQUIP", lineweight=70)
E.line((-R, BOT), (-R, TOP), "EQUIP", lineweight=60); E.line((R, BOT), (R, TOP), "EQUIP", lineweight=60)
E.line((-R, TOP), (0, APEX), "EQUIP", lineweight=60); E.line((R, TOP), (0, APEX), "EQUIP", lineweight=60)
E.line((-R - 80, TOP), (R + 80, TOP), "EQUIP_DET")                # cantoneira de topo
for k_ in range(1, 4):                                               # anéis de costura (virolas)
    E.line((-R, BOT + k_ * 1000), (R, BOT + k_ * 1000), "EQUIP_DET")
E.axis((0, -700), (0, APEX + 900))
# bocais de perfil (leste/oeste)
def side_nozzle(mark, sign):
    dn, desc, od, fod, fth, proj, el, az, cls = NOZ[mark]
    y = BOT + el
    xs = sign * R
    xf = sign * (R + proj)                           # face externa do flange
    E.rect(min(xs, xf - sign * fth), y - od / 2, max(xs, xf - sign * fth), y + od / 2, "EQUIP")
    E.rect(min(xf, xf - sign * fth), y - fod / 2, max(xf, xf - sign * fth), y + fod / 2, "EQUIP")
    E.axis((xs - sign * 150, y), (xf + sign * 250, y))
    E.circle((xf + sign * (330 if sign > 0 else 330), y + 0), 0.001, "TAG") if False else None
    bx = xf + sign * 420
    d.balloon(E.p(bx + sign * 60, y), mark, 3.6, "CHAMADA", 2.0); d.line(E.p(xf + sign * 40, y), E.p(bx + sign * 60 - sign * 150, y), "CHAMADA") if False else d.line(E.p(xf + sign * 250, y), E.p(bx + sign * 60 - sign * 3.6 / E.k, y), "CHAMADA")
for m_ in ("N2", "N5", "N6"): side_nozzle(m_, 1)
for m_ in ("N1", "N7"): side_nozzle(m_, -1)
# bocal de dreno N4 (face norte, oculto)
E.rect(-30, BOT + 120, 30, BOT + 180, "OCULTA")
# boca de visita N8 (face sul): vista frontal
mw_y = BOT + 900
E.circle((0, mw_y), 305, "EQUIP"); E.circle((0, mw_y), 406, "EQUIP"); E.circle((0, mw_y), 374.6, "EQUIP_DET")
for k_ in range(20):
    a_ = math.radians(k_ * 18); E.circle((374.6 * math.cos(a_), mw_y + 374.6 * math.sin(a_)), 18, "EQUIP_DET")
E.axis((-520, mw_y), (520, mw_y)); E.axis((0, mw_y - 520), (0, mw_y + 520))
d.balloon(E.p(0, mw_y - 650), "N8", 3.6, "CHAMADA", 2.0)
# escada marinheiro (az 135, x = +1414)
lx_, lw_ = 1414, 600
E.line((lx_ - lw_ / 2, BOT + 200), (lx_ - lw_ / 2, TOP + 1000), "ESTRUT"); E.line((lx_ + lw_ / 2, BOT + 200), (lx_ + lw_ / 2, TOP + 1000), "ESTRUT")
for yy in range(BOT + 500, TOP + 900, 300):
    E.line((lx_ - lw_ / 2, yy), (lx_ + lw_ / 2, yy), "ESTRUT")
for yy in range(BOT + 2400, TOP + 1000, 900):
    E.arc((lx_, yy), 450, 0, 360, "OCULTA")
# bocal de respiro N3 (topo) + boca de visita do teto N9
E.rect(-57, APEX, 57, APEX + 376, "EQUIP"); E.rect(-115, APEX + 376, 115, APEX + 400, "EQUIP"); E.axis((0, APEX - 100), (0, APEX + 700))
d.balloon(E.p(300, APEX + 330), "N3", 3.6, "CHAMADA", 2.0)
rx = -849; ry = TOP + (R - 1200) * RISE / R
E.rect(rx - 254, ry, rx + 254, ry + 300, "EQUIP"); E.rect(rx - 330, ry + 300, rx + 330, ry + 325, "EQUIP")
d.balloon(E.p(rx, ry + 520), "N9", 3.6, "CHAMADA", 2.0)
# níveis operacionais
for lab, yy in [("NÍVEL MÁX. (HH)  +3.700", BOT + 3700), ("NÍVEL NORMAL  +2.000", BOT + 2000), ("NÍVEL MÍN. (LL)  +300", BOT + 300 + 250)]:
    E.line((-R + 60, yy), (R - 60 - 600, yy), "OCULTA")
    E.text(lab, (-R + 120, yy + 40), 2.0, "TEXTO_NOTA")
# --- cotas da elevação
yN = {m: BOT + v[6] for m, v in NOZ.items()}
# corrente direita (elevações a partir do fundo)
cx_ = 3000
E.dim_v(BOT, yN["N2"], R + 100, cx_, "<>"); E.dim_v(yN["N2"], yN["N6"], R + 100, cx_); E.dim_v(yN["N6"], yN["N5"], R + 100, cx_); E.dim_v(yN["N5"], TOP, R + 100, cx_)
# corrente esquerda
lx2 = -3000
E.dim_v(BOT, mw_y, -R - 100, lx2); E.dim_v(mw_y, yN["N7"], -R - 100, lx2); E.dim_v(yN["N7"], yN["N1"], -R - 100, lx2); E.dim_v(yN["N1"], TOP, -R - 100, lx2)
# totais
E.dim_v(0, BOT, 2600, 3550) ; E.dim_v(BOT, TOP, 2600, 3550); E.dim_v(TOP, APEX, 2600, 3550)
E.dim_v(0, APEX + 400, 2600, 4100, "<>")
E.dim_v(-600, 0, 2600, 3550)
# horizontais
E.dim_h(-R, R, 0, 0, -1150)
E.dim_h(-2300, 2300, 0, 0, -1650)
E.dim_h(-2600, 2600, -600, -600, -2000)
E.dim_h(R, R + NOZ["N2"][5], yN["N2"], yN["N2"], yN["N2"] - 560)
E.dim_h(-R - NOZ["N1"][5], -R, yN["N1"], yN["N1"], yN["N1"] + 560)
E.dim_h(-115, 115, APEX + 400, APEX + 400, APEX + 1050, "<>")
d.leader(E.p(R, TOP - 40), E.p(R + 900, TOP + 1300), "Casca: chapa SA-283 C\ne = 6 mm (CA 1,5 mm)", 2.1)
d.leader(E.p(1300, TOP + 100), E.p(1500, TOP + 1900), "Teto cônico 1:5\nchapa e = 5 mm", 2.1)
d.leader(E.p(-1900, BOT - 0), E.p(-3600, BOT - 1000), "Chapa do fundo e = 6 mm\n(anel anular e = 8 mm)", 2.1)
d.leader(E.p(1500, BOT + 1300), E.p(2800, BOT + 2000), "Escada marinheiro com guarda-corpo\n(az. 135°)", 2.1)
d.leader(E.p(0, -300), E.p(-2500, -1000 - 100), "Anel de concreto C30 / fundação", 2.1) if False else None
# marcas de detalhe
d.circle(E.p(R + 150, BOT + 120), 3.0 / E.k * E.k, "CHAMADA") if False else None
d.circle(E.p(R + 40, BOT + 20), 6, "CHAMADA", lineweight=35); d.balloon(E.p(R + 900, BOT - 700), "A", 3.6, "CHAMADA", 2.6); d.line(E.p(R + 40 + 6 / E.k * 0.7, BOT + 20 - 6 / E.k * 0.7), E.p(R + 900 - 90, BOT - 700 + 90), "CHAMADA")
d.circle(E.p(R + 220, yN["N2"]), 10, "CHAMADA", lineweight=35); d.balloon(E.p(R + 1250, yN["N2"] + 650), "B", 3.6, "CHAMADA", 2.6); d.line(E.p(R + 220 + 10 / E.k * 0.7, yN["N2"] + 10 / E.k * 0.7), E.p(R + 1250 - 90, yN["N2"] + 650 - 90), "CHAMADA")

# ================================================================== PLANTA 1:30
Pv = V(440, 405, 30)
def pol(az, r):  # azimute (° a partir do norte, horário) e raio -> x leste, y norte
    a = math.radians(az)
    return (r * math.sin(a), r * math.cos(a))
d.text("PLANTA", (Pv.p(-3000, 0)[0], Pv.p(0, 3900)[1]), 4.0, "CARIMBO_TXT"); d.text("ESCALA 1:30", (Pv.p(-3000, 0)[0], Pv.p(0, 3900)[1] - 5), 2.4, "TEXTO_NOTA")
Pv.circle((0, 0), R, "EQUIP", lineweight=60); Pv.circle((0, 0), 2060, "OCULTA")
Pv.circle((0, 0), 2300, "EQUIP_DET"); Pv.circle((0, 0), 1700, "OCULTA"); Pv.circle((0, 0), 2600, "OCULTA")
Pv.axis((-3300, 0), (3300, 0)); Pv.axis((0, -3300), (0, 3300))
for k_ in range(8):                                                                   # chumbadores e cadeiras
    az = 22.5 + 45 * k_
    cxy = pol(az, 2150)
    Pv.circle(cxy, 40, "EQUIP"); Pv.rect(cxy[0] - 130, cxy[1] - 130, cxy[0] + 130, cxy[1] + 130, "EQUIP_DET")
for k_ in range(8):                                                                   # nervuras do teto
    az = 45 * k_ + 22.5
    Pv.line(pol(az, 300), pol(az, R), "OCULTA")
Pv.circle((0, 0), 115, "EQUIP"); Pv.circle((0, 0), 57, "EQUIP")                      # N3 vent
rm = pol(315, 1200); Pv.circle(rm, 254, "EQUIP"); Pv.circle(rm, 330, "EQUIP")        # N9
for m_, v_ in NOZ.items():
    dn, desc, od, fod, fth, proj, el, az, cls = v_
    a = math.radians(az); ux, uy = math.sin(a), math.cos(a); px_, py_ = -uy, ux
    pts = [pol(az, R)]
    def at(r_, w_): return (r_ * ux + w_ * px_, r_ * uy + w_ * py_)
    Pv.poly([at(R, -od / 2), at(R + proj - fth, -od / 2), at(R + proj - fth, od / 2), at(R, od / 2)], "EQUIP")
    Pv.poly([at(R + proj - fth, -fod / 2), at(R + proj, -fod / 2), at(R + proj, fod / 2), at(R + proj - fth, fod / 2)], "EQUIP", True)
    Pv.line(at(R - 200, 0), at(R + proj + 200, 0), "EIXO")
    bp = pol(az, R + proj + 560)
    d.balloon(Pv.p(*bp), m_, 3.6, "CHAMADA", 2.0)
    d.text(f"{az}°", Pv.p(*pol(az, R + proj + 1100)), 2.2, "TEXTO_NOTA", align="MIDDLE_CENTER")
# N4 dreno (norte) e N8 boca de visita (sul)
Pv.rect(-30, R, 30, R + 180, "EQUIP"); Pv.line((-150, R + 180), (150, R + 180), "EQUIP", lineweight=40); d.balloon(Pv.p(0, R + 640), "N4", 3.6, "CHAMADA", 2.0); d.text("0°", Pv.p(0, R + 1100), 2.2, "TEXTO_NOTA", align="MIDDLE_CENTER")
Pv.rect(-305, -R - 300, 305, -R, "EQUIP"); Pv.line((-406, -R - 300), (406, -R - 300), "EQUIP", lineweight=60)
d.balloon(Pv.p(0, -R - 860), "N8", 3.6, "CHAMADA", 2.0); d.text("180°", Pv.p(0, -R - 1400), 2.2, "TEXTO_NOTA", align="MIDDLE_CENTER")
d.balloon(Pv.p(*pol(315, 1200 + 700)), "N9", 3.6, "CHAMADA", 2.0); d.balloon(Pv.p(0, 270), "N3", 3.6, "CHAMADA", 2.0)
# escada e aterramento
ladd = pol(135, R + 150)
Pv.poly([(ladd[0] - 300, ladd[1] - 300 + 0), (ladd[0] + 300, ladd[1] + 300 + 0), (ladd[0] + 300 + 300, ladd[1] + 300 - 300), (ladd[0] - 300 + 300, ladd[1] - 300 - 300)], "ESTRUT", True)
Pv.text("ESCADA", Pv.p(*pol(135, R + 900))[0:2] and (pol(135, R + 900)[0] + 200, pol(135, R + 900)[1] - 300), 2.0, "TEXTO_NOTA") if False else d.text("ESCADA", Pv.p(*pol(135, R + 850)), 2.0, "TEXTO_NOTA", align="MIDDLE_CENTER")
ea = pol(225, R); Pv.rect(ea[0] - 60, ea[1] - 60, ea[0] + 60, ea[1] + 60, "EQUIP"); d.text("ATERRAMENTO", Pv.p(*pol(225, R + 600)), 2.0, "TEXTO_NOTA", align="MIDDLE_CENTER")
# cotas da planta
Pv.dim_h(-R, R, 0, 0, -3050) if False else None
d.dim("linear", p1=list(Pv.p(-R, 0)), p2=list(Pv.p(R, 0)), base=[Pv.ox, Pv.p(0, -3200)[1] - 0], lfac=30, text="Ø4000 (DI)")
d.dim("linear", p1=list(Pv.p(-2300, 0)), p2=list(Pv.p(2300, 0)), base=[Pv.ox, Pv.p(0, -3550)[1]], lfac=30, text="Ø4600 (ANEL)")
d.dim("linear", p1=list(Pv.p(-2600, 0)), p2=list(Pv.p(2600, 0)), base=[Pv.ox, Pv.p(0, -3900)[1]], lfac=30, text="Ø5200 (FUNDAÇÃO)")
d.dim("linear", p1=list(Pv.p(2150, 0)), p2=list(Pv.p(2150, 2150 * 0 + 0)), base=[Pv.ox, Pv.oy], lfac=30) if False else None
d.leader(Pv.p(*pol(22.5, 2150)), Pv.p(1900, 3500), "8 chumbadores M20 em Ø4300\n(az. 22,5° + k·45°)", 2.1)
d.leader(Pv.p(rm[0], rm[1]), Pv.p(-3300, 2000), "N9 DN500: R = 1200 mm @ 315°", 2.1)
d.leader(Pv.p(-60, -2200 + 0), Pv.p(-3300, -1500), "N8 DN600 (MH) @ 180°", 2.1) if False else None
# norte
nx, ny = Pv.p(-3300, 2900)
d.circle((nx, ny), 6, "NORTE"); d.poly([(nx, ny + 8), (nx - 2.6, ny - 3), (nx, ny - 0.5), (nx + 2.6, ny - 3)], "NORTE", True); d.hatch_solid([(nx, ny + 8), (nx - 2.6, ny - 3), (nx, ny - 0.5)], 7, "NORTE")
d.text("N", (nx, ny + 11), 3.2, "NORTE", align="MIDDLE_CENTER"); d.text("NORTE DE PROJETO", (nx, ny - 9), 1.8, "TEXTO_NOTA", align="MIDDLE_CENTER")

# ================================================================== DETALHE A - ancoragem 1:5
A = V(335, 205, 5)
d.text("DETALHE  A  -  ANCORAGEM", (A.p(1450, 0)[0], A.p(0, 960)[1]), 3.2, "CARIMBO_TXT"); d.text("ESCALA 1:5", (A.p(1450, 0)[0], A.p(0, 960)[1] - 4.5), 2.1, "TEXTO_NOTA")
# concreto (anel): x 1700..2300 ; topo y=300 ; mostrado de y=-100..300
A.rect(1650, -100, 2300, 300, "EQUIP_DET"); A.hatch([(1650, -100), (2300, -100), (2300, 300), (1650, 300)], "AR-CONC", 0.5, 8)
A.line((1650, -100), (1650, 300), "EQUIP_DET")
# argamassa 25 e chapa do fundo 6 (anular 8)
A.rect(1650, 300, 2090, 325, "EQUIP_DET"); A.hatch([(1650, 300), (2090, 300), (2090, 325), (1650, 325)], "ANSI37", 0.3, 8)
A.rect(1650, 325, 2090, 333, "EQUIP"); A.solid([(1650, 325), (2090, 325), (2090, 333), (1650, 333)], 7)
# casca (e=6) cota x=2000..2006
A.rect(2000, 333, 2006, 900, "EQUIP"); A.solid([(2000, 333), (2006, 333), (2006, 900), (2000, 900)], 7)
# cadeira de ancoragem: chapa superior e nervuras
A.rect(2006, 520, 2220, 536, "EQUIP"); A.solid([(2006, 520), (2220, 520), (2220, 536), (2006, 536)], 7)
A.line((2006, 333), (2150, 520), "EQUIP"); A.line((2006, 420), (2090, 520), "OCULTA")
A.rect(2006, 333, 2020, 520, "EQUIP_DET")
# chumbador M20
A.rect(2105, -80, 2125, 560, "EQUIP"); A.line((2115, -100), (2115, 600), "EIXO")
A.rect(2085, 536, 2145, 556, "EQUIP"); A.solid([(2085, 536), (2145, 536), (2145, 556), (2085, 556)], 2)    # arruela
A.rect(2092, 556, 2138, 586, "EQUIP"); A.line((2092, 570), (2138, 570), "EQUIP_DET")                       # porca
A.line((2105, -80), (2125, -110), "EQUIP"); A.line((2115, -60), (2115, -110), "OCULTA")
# cotas
A.dim_v(-80, 333, 2115, 2400, "<>"); A.dim_v(333, 520, 2115, 2400); A.dim_h(2000, 2115, 520, 520, 700, "<>")
A.dim_v(300, 333, 1650, 1400, "<>")
d.leader(A.p(2060, 329), A.p(1450, 650), "Chapa anular e = 8 mm", 2.0)
d.leader(A.p(1900, 312), A.p(1450, 560), "Argamassa grout 25 mm", 2.0)
d.leader(A.p(2115, 570), A.p(2300, 780), "Porca + arruela M20\nAISI 316", 2.0)
d.leader(A.p(2060, 528), A.p(2300, 690), "Cadeira de ancoragem\ne = 16 mm", 2.0)
d.leader(A.p(1950, 100), A.p(1450, 90), "Anel de concreto C30", 2.0)
d.leader(A.p(2003, 700), A.p(1450, 780), "Casca e = 6 mm", 2.0)

# ================================================================== DETALHE B - bocal N2 (8" 150# RFWN) 1:5
B = V(712, 475, 5)
d.text('DETALHE  B  -  BOCAL N2  8" 150# RFWN', (B.p(-420, 410)[0], B.p(0, 410)[1]), 3.2, "CARIMBO_TXT"); d.text("ESCALA 1:5", (B.p(-420, 330)[0], B.p(0, 330)[1]), 2.1, "TEXTO_NOTA")
# casca (e=6) vertical em x=0, abertura = OD do bocal; chapa de reforço 6 mm, OD 400
od, fod, fth, proj = 219.1, 343.0, 25.4, 400
tn = 8.18
for sgn in (1, -1):
    # casca segmentos fora da abertura/pad
    B.rect(-6, sgn * (od / 2 + 3), 0, sgn * 260, "EQUIP"); B.solid([(-6, sgn * (od / 2 + 3)), (0, sgn * (od / 2 + 3)), (0, sgn * 260), (-6, sgn * 260)], 7)
    # chapa de reforço (pad)
    B.rect(0, sgn * (od / 2 + 3), 6, sgn * 200, "EQUIP"); B.solid([(0, sgn * (od / 2 + 3)), (6, sgn * (od / 2 + 3)), (6, sgn * 200), (0, sgn * 200)], 7)
    # parede do bocal (tubo)
    y_out, y_in = sgn * od / 2, sgn * (od / 2 - tn)
    B.rect(6, min(y_out, y_in), proj - fth - 40, max(y_out, y_in), "EQUIP"); B.hatch([(6, y_out), (proj - fth - 40, y_out), (proj - fth - 40, y_in), (6, y_in)], "ANSI31", 0.25, 7)
    # cubo cônico e flange
    B.poly([(proj - fth - 40, y_out), (proj - fth, sgn * 140), (proj, sgn * 140), (proj, sgn * fod / 2)][0:0] or [(proj - fth - 40, y_out), (proj - fth, sgn * 128), (proj - fth, sgn * fod / 2), (proj, sgn * fod / 2), (proj, sgn * 118), (proj - fth - 40, y_in)], "EQUIP", True)
    B.hatch([(proj - fth - 40, y_out), (proj - fth, sgn * 128), (proj - fth, sgn * fod / 2), (proj, sgn * fod / 2), (proj, sgn * 118), (proj - fth - 40, y_in)], "ANSI31", 0.25, 7)
    B.line((proj, sgn * 111), (proj + 2, sgn * 111), "EQUIP")                       # face com ressalto (RF 2 mm)
B.axis((-60, 0), (proj + 80, 0))
B.line((proj, 111), (proj, -111), "EQUIP_DET")
# cotas
B.dim_h(0, proj, -fod / 2, -fod / 2, -300, "<>")
B.dim_v(-fod / 2, fod / 2, proj + 60, proj + 160, "<>")
B.dim_v(-od / 2, od / 2, 60, -170, "<>")
B.dim_v(-200, 200, 6, -300, "<>") if False else B.dim_v(-200, 200, 3, -290, "Ø400 PAD")
B.dim_h(proj - fth, proj, fod / 2, fod / 2, 240, "<>")
d.leader(B.p(proj - 12, fod / 2 - 8), B.p(proj + 300, 360), "Flange 8\" 150# RFWN\nASME B16.5 (A105)", 2.0) if False else d.leader(B.p(proj - 12, fod / 2 - 8), B.p(proj + 190, 330), 'Flange 8" 150# RFWN\nASME B16.5 (A105)', 2.0)
d.leader(B.p(3, 170), B.p(-440, 380), "Chapa de reforço\ne = 6 mm, OD 400", 2.0)
d.leader(B.p(-3, -240), B.p(-440, -300), "Casca e = 6 mm", 2.0)
d.leader(B.p(200, od / 2 - 4), B.p(210, 470), "Tubo 8\" SCH 40S\n(219,1 x 8,18)", 2.0)
d.text("8 furos Ø22 em Ø298,5 (BC)", (B.p(proj - 330, -fod / 2 - 90)[0], B.p(0, -fod / 2 - 90)[1] - 14), 1.9, "TEXTO_NOTA")

# ================================================================== tabelas
tx = x0 + 6; ty = y0 + 138
d.text("TABELA DE BOCAIS", (tx, ty + 4), 3, "CARIMBO_TXT")
cols = [0, 14, 22, 62, 112, 142, 166, 190, 214]
heads = ["MARCA", "QTD", "DN", "SERVIÇO", "CLASSE / FACE", "ELEV. (mm)", "AZIM.", "PROJ. (mm)"]
cols = [0, 14, 26, 46, 108, 140, 166, 188, 214]
rows = []
for m_, v_ in NOZ.items():
    rows.append((m_, "1", v_[0], v_[1], v_[8], str(v_[6]), f"{v_[7]}°", str(v_[5])))
rows.insert(2, ("N3", "1", '4"', "Respiro (PVRV-101 / quebra-chama)", "150# RFWN", "topo (+400)", "—", "—"))
rows.insert(3, ("N4", "1", '2"', "Dreno de fundo", "150# RFWN", "150", "0°", "300"))
rows.append(("N8", "1", '24"', "Boca de visita (MH)", "150# RFSO", "900", "180°", "300"))
rows.append(("N9", "1", '20"', "Boca de visita do teto", "150# RFSO", "teto, R=1200", "315°", "300"))
n = len(rows) + 1
rh = 5.4
d.rect(tx, ty - rh * n + 0, cols[-1], rh * n, "CARIMBO")
for c in cols[1:-1]:
    d.line((tx + c, ty - rh * n), (tx + c, ty), "CARIMBO")
for i in range(1, n):
    d.line((tx, ty - rh * i), (tx + cols[-1], ty - rh * i), "CARIMBO")
for c, h_ in zip(cols, heads):
    d.text(h_, (tx + c + 1.2, ty - rh + 1.7), 1.7, "TEXTO_NOTA")
for r_i, r in enumerate(rows):
    for c, t in zip(cols, r):
        d.text(t, (tx + c + 1.2, ty - rh * (r_i + 2) + 1.7), 1.9, "TEXTO")
d.text("Dados dos flanges conforme ASME B16.5 (valores típicos); verificar no projeto real.", (tx, ty - rh * n - 4), 1.7, "TEXTO_NOTA")

# dados de projeto
dx = tx + 224; dyt = ty
d.text("DADOS DE PROJETO", (dx, dyt + 4), 3, "CARIMBO_TXT")
data = [("Código de projeto", "API 650 (referência, dados fictícios)"), ("Capacidade nominal", "50 m³  (Ø4000 x 4000)"),
        ("Produto / massa específica", "Produto A / 900 kg/m³"), ("Pressão de projeto", "0,07 barg / vácuo 0,02 barg"),
        ("Temperatura de projeto", "80 °C"), ("Sobre-espessura de corrosão", "1,5 mm"),
        ("Material casca / fundo / teto", "SA-283 C"), ("Massa vazio (estim.)", "≈ 4,1 t"),
        ("Massa em teste hidrostático", "≈ 54 t"), ("Vento / sismo", "Conforme ASCE 7 - local (a definir)"),
        ("Pintura", "Jato Sa 2½ + epóxi + PU (esq. P-05)")]
dw = 128
d.rect(dx, dyt - rh * len(data), dw + 22, rh * len(data), "CARIMBO")
d.line((dx + 52, dyt - rh * len(data)), (dx + 52, dyt), "CARIMBO")
for i, (a, b) in enumerate(data):
    if i:
        d.line((dx, dyt - rh * i), (dx + dw + 22, dyt - rh * i), "CARIMBO")
    d.text(a, (dx + 1.2, dyt - rh * (i + 1) + 1.7), 1.9, "TEXTO_NOTA"); d.text(b, (dx + 53.2, dyt - rh * (i + 1) + 1.7), 1.9, "TEXTO")

# lista de materiais
mx = dx + 158 + 8
d.text("LISTA DE MATERIAIS", (mx, dyt + 4), 3, "CARIMBO_TXT")
mats = [("1", "Chapa do fundo", "SA-283 C", "e=6 / anular 8", "1 jg"), ("2", "Chapa da casca (4 virolas)", "SA-283 C", "e=6", "4"), ("3", "Chapa do teto cônico", "SA-283 C", "e=5", "1 jg"),
        ("4", "Cantoneira de topo", "A36", "L 75x75x8", "1 jg"), ("5", "Flange 8\" 150# RFWN", "A105", "B16.5", "1"), ("6", "Flange 6\" 150# RFWN", "A105", "B16.5", "1"),
        ("7", "Flange 4\" 150# RFWN", "A105", "B16.5", "2"), ("8", "Flange 2\" 150# RFWN", "A105", "B16.5", "3"), ("9", "Chumbador M20 x 600 c/ porca", "A307 / 316", "Ø4300", "8"),
        ("10", "Escada marinheiro c/ gaiola", "A36", "H=4,3 m", "1")]
mw = 150
cols_m = [0, 8, 62, 90, 116, mw]
d.rect(mx, dyt - rh * (len(mats) + 1), mw, rh * (len(mats) + 1), "CARIMBO")
for c in cols_m[1:-1]:
    d.line((mx + c, dyt - rh * (len(mats) + 1)), (mx + c, dyt), "CARIMBO")
for i in range(1, len(mats) + 1):
    d.line((mx, dyt - rh * i), (mx + mw, dyt - rh * i), "CARIMBO")
for c, h_ in zip(cols_m, ["Nº", "DESCRIÇÃO", "MATERIAL", "DIMENSÃO", "QTD"]):
    d.text(h_, (mx + c + 1.2, dyt - rh + 1.7), 1.7, "TEXTO_NOTA")
for i, r in enumerate(mats):
    for c, t in zip(cols_m, r):
        d.text(t, (mx + c + 1.2, dyt - rh * (i + 2) + 1.7), 1.9, "TEXTO")

# notas
notes_box(d, mx + mw + 10, dyt - 0, x1 - (mx + mw + 10) - 8, ["Dimensões em milímetros, exceto onde indicado.",
                                      "Azimutes medidos a partir do norte de projeto, no sentido horário.",
                                      "Elevações dos bocais referidas ao fundo do tanque (+300 do terreno).",
                                      "Solda de topo com penetração total nas juntas da casca (API 650).",
                                      "Dados fictícios, apenas para demonstração do MCP."], h=2.1)

# documentos de referência
rx0, ry0 = x0 + 6, y0 + 38
d.text("DOCUMENTOS DE REFERÊNCIA", (rx0, ry0 + 4), 3, "CARIMBO_TXT")
refs = [("EX-PID-100-001", "P&ID - Transferência e aquecimento", "0"), ("EX-FND-101-001", "Fundação do tanque TK-101 (anel de concreto)", "A"),
        ("EX-ESP-TK-101", "Folha de dados do tanque TK-101", "0"), ("EX-PIP-110-001", "Planta de tubulação - Área 110", "B")]
d.rect(rx0, ry0 - 5.4 * len(refs), 190, 5.4 * len(refs), "CARIMBO")
for i, (a, b, c) in enumerate(refs):
    if i:
        d.line((rx0, ry0 - 5.4 * i), (rx0 + 190, ry0 - 5.4 * i), "CARIMBO")
    d.text(a, (rx0 + 1.5, ry0 - 5.4 * (i + 1) + 1.7), 2.0, "TEXTO"); d.text(b, (rx0 + 40, ry0 - 5.4 * (i + 1) + 1.7), 2.0, "TEXTO"); d.text("REV " + c, (rx0 + 172, ry0 - 5.4 * (i + 1) + 1.7), 2.0, "TEXTO")
d.line((rx0 + 38, ry0), (rx0 + 38, ry0 - 5.4 * len(refs)), "CARIMBO"); d.line((rx0 + 170, ry0), (rx0 + 170, ry0 - 5.4 * len(refs)), "CARIMBO")
# carimbo
tbx, tby = title_block(d, x1, y0, "TANQUE TK-101 - ARRANJO E BOCAIS", "Elevação, planta, detalhes de ancoragem e do bocal N2", "EX-TK-101-001", "0", "1:30 / 1:5", "A1", "1/1")
revision_table(d, x1, tby, [("0", "05/10/26", "EMISSÃO PARA DEMONSTRAÇÃO DO MCP", "MCP", "—", "—")], 190)
save(doc, OUT, "06_tanque_bocais_base")
