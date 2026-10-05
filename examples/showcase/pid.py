"""Exemplo 1 - P&ID: tanque TK-101, bombas P-101A/B, medição/controle de vazão, trocador E-101 com controle de temperatura."""
import math
import sys
from pathlib import Path

from common import *  # noqa

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "../../docs/images")
doc = new_doc()
d = D(doc, doc.modelspace())
x0, y0, x1, y1 = frame(d, "A1")
P = lambda pts, layer="LINHA_PROC": d.poly(pts, layer)
tag = lambda t, p, h=2.4, rot=0, align="LEFT": d.text(t, p, h, "TAG", rot, align)

n0 = len(doc.modelspace())

# ----------------------------------------------------------------- TK-101 (tanque atmosférico, teto cônico)
tx, ty0, tw, th = 100, 250, 60, 85     # centro x, base, largura, altura da casca
L, R = tx - tw / 2, tx + tw / 2
d.poly([(L, ty0), (L, ty0 + th), (tx, ty0 + th + 14), (R, ty0 + th), (R, ty0)], "EQUIP", close=False)
d.line((L - 4, ty0), (R + 4, ty0), "EQUIP")                      # anel de base
d.rect(L - 8, ty0 - 5, tw + 16, 5, "EQUIP_DET")                   # fundação
d.hatch_pat([(L - 8, ty0 - 5), (R + 8, ty0 - 5), (R + 8, ty0), (L - 8, ty0)], "ANSI31", 0.8)
d.line((L, ty0 + th), (R, ty0 + th), "EQUIP_DET")                 # junção casca/teto
for lvl, lab in [(ty0 + 8, "LL"), (ty0 + 22, "LAL"), (ty0 + 62, "LAH"), (ty0 + 76, "HH")]:
    d.line((L + 2, lvl), (R - 2, lvl), "OCULTA")
    d.text(lab, (R - 12, lvl + 1), 1.8, "TEXTO_NOTA")
d.text("TK-101", (tx, ty0 + 42), 5, "TAG", align="MIDDLE_CENTER")
d.text("TANQUE DE ARMAZENAMENTO", (tx, ty0 + 33), 2.2, "TEXTO", align="MIDDLE_CENTER")
# bocais
nz = {}
def nozzle(name, p, side, bal):
    x, y = p
    sx = -1 if side == "L" else 1
    d.line((x, y - 2.2), (x, y + 2.2), "VALV")                    # flange do bocal
    d.balloon((x + sx * 9, y + 7.5 if bal == "up" else y - 7.5), name, 3.4, "CHAMADA", 1.9)
nozzle("N1", (L, 290), "L", "up"); nozzle("N7", (L, 318), "L", "up"); nozzle("N2", (R, 262), "R", "dn")
nozzle("N5", (R, 328), "R", "up"); nozzle("N6", (R, 276), "R", "up")
# bocal de dreno N4 no fundo e respiro N3 no teto
P([(tx, ty0), (tx, ty0 - 14)]); valve_gate(d, (tx, ty0 - 22), 90)
P([(tx, ty0 - 24.6), (tx, ty0 - 36), (tx + 12, ty0 - 36)]); d.line((tx + 12, ty0 - 38.5), (tx + 12, ty0 - 33.5), "VALV"); tag("TAMPONADO", (tx + 15, ty0 - 37), 2)
d.balloon((tx - 9, ty0 - 12), "N4", 3.6, "CHAMADA", 2.0)
P([(tx, ty0 + th + 14), (tx, ty0 + th + 32)]); valve_psv(d, (tx, ty0 + th + 40))
d.rect(tx - 5, ty0 + th + 20, 10, 6, "VALV")                      # quebra-chama
tag("PVRV-101", (tx + 6, ty0 + th + 47), 2.2)
d.text("VENTE À ATM. (SEGURO)", (tx + 6, ty0 + th + 51), 1.8, "TEXTO_NOTA")
d.balloon((tx - 9, ty0 + th + 21), "N3", 3.6, "CHAMADA", 2.0)
d.rect(L - 6, ty0 + 12, 6, 12, "EQUIP"); d.line((L - 6, ty0 + 10), (L - 6, ty0 + 26), "VALV")  # boca de visita N8 (stub + flange)
d.balloon((L - 14, ty0 + 18), "N8", 3.4, "CHAMADA", 1.9); d.text("MH 24\"", (L - 24, ty0 + 8), 1.8, "TEXTO_NOTA")

# ----------------------------------------------------------------- entrada N1 e recirculação N7
P([(30, 290), (L, 290)]); d.arrow((L - 1, 290), 0)
valve_gate(d, (44, 290)); flange(d, (56, 290)); flange(d, (58, 290))
line_tag(d, (22, 294), '6"-P-1001-CS150-N', 33)
d.text("DE U-100", (30, 283), 2.4, "TEXTO"); d.text("(PROD. A 35 °C)", (30, 279), 1.9, "TEXTO_NOTA")
P([(L, 318), (40, 318), (40, 395), (330, 395), (330, 322)], "LINHA_PROC_SEC")
d.arrow((L - 1, 318), 0)
line_tag(d, (205, 386), '4"-P-1004-CS150-N', 33)
valve_globe(d, (60, 318)); valve_check(d, (225, 395), 180); valve_gate(d, (270, 395))
d.circle((150, 395), 0.0001, "TAG")
d.line((149, 392), (149, 398), "VALV"); d.line((151, 392), (151, 398), "VALV"); tag("RO-101", (140, 400), 2.2)  # placa de orifício de restrição
valve_gate(d, (330, 350), 90)
d.arrow((300, 395), 180)
d.arrow((90, 395), 180)

# ----------------------------------------------------------------- nível LT-101 / LIC-101
P([(R, 328), (160, 328), (160, 304.7)], "LINHA_INSTR"); P([(R, 276), (160, 276), (160, 295.3)], "LINHA_INSTR")
valve_gate(d, (R + 12, 328)); valve_gate(d, (R + 12, 276))
instrument(d, (160, 300), "LT", "101")
P([(160, 304.7), (160, 340), (176, 340)], "LINHA_SINAL")
instrument(d, (181, 340), "LIC", "101", "dcs", 4.6)
for k, (t, n, off) in enumerate([("LAH", "101", 15), ("LAL", "101", 28)]):
    instrument(d, (181 + off + 6, 340), t, n, "dcs", 3.8, h=1.7)
d.line((185.6, 340), (181 + 15 + 6 - 3.6, 340), "LINHA_SINAL")
d.line((181 + 15 + 6 + 3.6, 340), (181 + 28 + 6 - 3.6, 340), "LINHA_SINAL")

# ----------------------------------------------------------------- linha de sucção (N2 -> coletor) e bombas
SX, DX = 185, 330
P([(R, 262), (SX, 262)]); valve_gate(d, (150, 262)); flange(d, (140, 262)); tag("HV-101", (150, 254), 2.2)
line_tag(d, (R + 4, 266), '8"-P-1002-CS150-N', 34)
P([(SX, 230), (SX, 300)])
for (yy, nm) in [(300, "A"), (230, "B")]:
    P([(SX, yy), (258 - 9, yy)])
    valve_gate(d, (205, yy)); strainer(d, (224, yy)); tag("TSV-101" + nm if False else "", (224, yy + 5))
    reducer(d, (240, yy), 0)
    cx = 258
    d.circle((cx, yy), 9, "EQUIP", lineweight=60)
    d.poly([(cx - 4, yy + 5.5), (cx + 7, yy), (cx - 4, yy - 5.5)], "EQUIP_DET", False)    # rotor/seta
    d.line((cx, yy + 9), (cx, yy + 22), "LINHA_PROC")
    d.rect(cx - 12, yy - 14.6, 24, 3.6, "EQUIP_DET")                                   # base
    d.text(f"P-101{nm}", (cx, yy - 20), 3.4, "TAG", align="MIDDLE_CENTER")
    d.text("BOMBA CENTRÍFUGA" + (" (OPERAÇÃO)" if nm == "A" else " (RESERVA)"), (cx, yy - 25), 1.8, "TEXTO", align="MIDDLE_CENTER")
    P([(cx, yy + 22), (DX, yy + 22)]); valve_check(d, (285, yy + 22)); valve_gate(d, (306, yy + 22)); flange(d, (278, yy + 22))
    P([(DX, yy + 22), (DX, yy + 22)])
    d.line((cx + 4, yy + 22), (cx + 4, yy + 26), "LINHA_INSTR")                         # tomada PI
    instrument(d, (cx + 4, yy + 30.6), "PI", f"102{nm}", "field", 4.0)
    # dreno de carcaça e respiro
    P([(cx - 3, yy - 9), (cx - 3, yy - 11)], "LINHA_PROC_SEC")
    d.line((cx + 9 - 0.01, yy + 1), (cx + 14, yy + 1), "LINHA_PROC_SEC"); valve_gate(d, (cx + 17, yy + 1)) if False else None
P([(DX, 252), (DX, 322)])
d.text("P-101A/B EM PARALELO — UMA EM OPERAÇÃO, OUTRA EM RESERVA", (186, 196), 2.4, "TEXTO_NOTA")
line_tag(d, (SX + 3, 303.5), '8"-P-1002-CS150-N', 34) if False else None
line_tag(d, (290, 326.5), '6"-P-1003-CS150-N', 34) if False else None

# ----------------------------------------------------------------- linha principal: PT, FT/FCV, E-101, TT, limite de bateria
P([(DX, 287), (480, 287)])
valve_gate(d, (342, 287)); tag("HV-103", (338, 291), 2.2)
line_tag(d, (344, 270), '6"-P-1003-CS150-N', 34)
# PT-101 / PI-101
d.line((354, 287), (354, 316), "LINHA_INSTR"); valve_gate(d, (354, 300), 90); instrument(d, (354, 321), "PT", "101")
# orifício + FT-101
d.line((372, 283.5), (372, 290.5), "VALV", lineweight=60)
d.line((370.5, 290.5), (370.5, 318), "LINHA_INSTR"); d.line((373.5, 290.5), (373.5, 318), "LINHA_INSTR")
valve_gate(d, (370.5, 300), 90); valve_gate(d, (373.5, 308), 90)
instrument(d, (372, 322.6), "FT", "101")
# FCV-101 com bloqueios e bypass
valve_gate(d, (402, 287)); valve_control(d, (420, 287), 0, fail="FC"); valve_gate(d, (438, 287))
P([(394, 287), (394, 266), (446, 266), (446, 287)], "LINHA_PROC_SEC"); valve_globe(d, (420, 266))
tag("FCV-101", (428, 296), 2.4); tag("(BYPASS)", (428, 262), 1.9) if False else d.text("BYPASS - HV-104", (409, 259), 1.9, "TEXTO_NOTA")
instrument(d, (420, 352), "FIC", "101", "dcs")
P([(372, 327.2), (372, 352), (415.4, 352)], "LINHA_SINAL")
P([(420, 347.4), (420, 299)], "LINHA_SINAL")
d.text("FY: SINAL 4-20 mA / HART", (426, 346), 1.8, "TEXTO_NOTA")
# E-101 trocador casco-tubo horizontal
ex, ey = 525, 287
d.rect(ex - 30, ey - 12, 60, 24, "EQUIP", lineweight=60)
d.rect(ex - 40, ey - 9, 10, 18, "EQUIP"); d.rect(ex + 30, ey - 9, 10, 18, "EQUIP")
for k in (-1, 0, 1):
    d.line((ex - 30, ey + k * 4), (ex + 30, ey + k * 4), "EQUIP_DET")
d.line((ex - 18, ey - 12), (ex - 18, ey + 12), "EQUIP_DET"); d.line((ex + 6, ey - 12), (ex + 6, ey + 12), "EQUIP_DET")
d.text("E-101", (ex - 44, ey - 22), 3.6, "TAG")
d.text("TROCADOR CASCO-TUBO (AEL)", (ex - 44, ey - 27), 1.9, "TEXTO")
d.text("TUBOS: PRODUTO | CASCO: VAPOR LP", (ex - 44, ey - 31), 1.7, "TEXTO_NOTA")
P([(480, 287), (ex - 40, 287)]); flange(d, (484, 287)); P([(ex + 40, 287), (700, 287)]); flange(d, (ex + 44, 287))
# vapor (utilidade): entrada acima, TCV-101 (atuador à direita)
P([(ex, ey + 12), (ex, 372)], "LINHA_UTIL"); valve_gate(d, (ex, 316), 90); valve_control(d, (ex, 340), -90, fail="FC")
d.arrow((ex, 374), 270, 2.5, "LINHA_UTIL") if False else d.arrow((ex, ey + 14), 270, 2.5, "LINHA_UTIL")
d.text("VAPOR LP 3,5 BARG / 148 °C", (ex - 20, 376), 2.4, "TEXTO"); line_tag(d, (ex + 4, 355), '2"-LS-3001-CS150-H', 35)
instrument(d, (578, 352), "TIC", "101", "dcs")
P([(573.4, 352), (545, 352), (545, 340), (ex + 8.7, 340)], "LINHA_SINAL")
# condensado
P([(ex, ey - 12), (ex, 245)], "LINHA_UTIL"); valve_gate(d, (ex, 262), 90)
d.circle((ex, 232), 5.5, "VALV"); d.text("PT", (ex, 232), 2.2, "TAG", align="MIDDLE_CENTER")      # purgador
P([(ex, 226.5), (ex, 214), (560, 214)], "LINHA_UTIL"); valve_gate(d, (ex, 220), 90) if False else valve_gate(d, (545, 214))
d.arrow((560, 214), 0, 2.5, "LINHA_UTIL"); d.text("CONDENSADO A RECUPERAÇÃO", (562, 211.5), 2.4, "TEXTO")
line_tag(d, (ex - 36, 206), '1.5"-CD-3002-CS150-H', 38)
tag("ST-101", (ex + 8, 230), 2.2)
# TT-101 e segurança térmica
d.line((610, 287), (610, 316), "LINHA_INSTR"); d.circle((610, 291), 1.2, "INSTR")
instrument(d, (610, 321), "TT", "101"); P([(610, 325.6), (610, 336), (582.6, 352)], "LINHA_SINAL") if False else None
P([(610, 325.6), (610, 352), (582.6, 352)], "LINHA_SINAL")
# PSV-102 de alívio térmico
d.line((650, 287), (650, 300), "LINHA_PROC_SEC"); valve_psv(d, (650, 304)); d.line((650, 311.2), (650, 330), "LINHA_PROC_SEC")
tag("PSV-102", (655, 318), 2.4); d.text("ALÍVIO TÉRMICO  SET 12 BARG", (655, 313.5), 1.7, "TEXTO_NOTA"); d.text("P/ TANQUE DE ALÍVIO", (655, 332), 1.9, "TEXTO_NOTA")
valve_gate(d, (650, 294), 90)
# limite de bateria
P([(700, 287), (736, 287)]); d.arrow((738, 287), 0, 3)
valve_gate(d, (712, 287)); flange(d, (720, 287)); flange(d, (722, 287))
d.rect(736, 262, 76, 50, "AREA", lineweight=35)
d.text("LIMITE DE", (774, 303), 2.8, "TEXTO", align="MIDDLE_CENTER"); d.text("BATERIA", (774, 298), 2.8, "TEXTO", align="MIDDLE_CENTER")
d.text("PARA U-200", (774, 291), 3.2, "CARIMBO_TXT", align="MIDDLE_CENTER")
d.text("VER P&ID Nº  EX-PID-200-001", (774, 283), 2.0, "TEXTO_NOTA", align="MIDDLE_CENTER")
d.text("PRESS. 8 BARG / 85 °C", (774, 276), 2.0, "TEXTO_NOTA", align="MIDDLE_CENTER")
line_tag(d, (692, 291), '6"-P-1005-CS150-H', 34) if False else line_tag(d, (668, 291), '6"-P-1005-CS150-H', 34)

# ----------------------------------------------------------------- seta de sentido e blocos "HOLD / dados" ao lado dos equipamentos
d.balloon((L - 10, 345), "1", 3.6, "CHAMADA", 2.4); d.text("NOTA 1", (L - 15, 352), 1.8, "TEXTO_NOTA")
d.balloon((470, 300), "2", 3.6, "CHAMADA", 2.4)
d.balloon((600, 275), "3", 3.6, "CHAMADA", 2.4)

# ----------------------------------------------------------------- deslocamento do processo p/ centralizar na folha + áreas
for e_ in list(doc.modelspace())[n0:]:
    e_.translate(0, 112, 0)
D2 = 112
for (ax, aw, nm, sub) in [(24, 168, "ÁREA 100 - ARMAZENAMENTO", "TK-101"), (176, 190, "ÁREA 110 - BOMBEAMENTO E MEDIÇÃO", "P-101A/B | FT/FCV-101"),
                          (428, 148, "ÁREA 120 - AQUECIMENTO", "E-101"), (668, 154, "ÁREA 200", "Interface")]:
    pass
for (ax, aw, nm, sub) in [(26, 171, "ÁREA 100 - ARMAZENAMENTO", "TK-101"), (199, 207, "ÁREA 110 - BOMBEAMENTO E MEDIÇÃO", "P-101A/B | FT/FCV-101"),
                          (408, 272, "ÁREA 120 - AQUECIMENTO DE PRODUTO", "E-101 / TCV-101")]:
    d.rect(ax, 186 + D2, aw, 232, "AREA")
    d.text(nm, (ax + 3, 186 + D2 + 223), 3.0, "LEGENDA"); d.text(sub, (ax + 3, 186 + D2 + 218), 2.0, "TEXTO_NOTA")
d.text("P&ID  -  SISTEMA DE TRANSFERÊNCIA E AQUECIMENTO DE PRODUTO", (x0 + 6, y1 - 12), 6, "CARIMBO_TXT")
d.line((x0 + 6, y1 - 15), (x0 + 330, y1 - 15), "CARIMBO")
d.text("Tanque TK-101 / Bombas P-101A/B / Medição e controle de vazão / Trocador E-101 / Limite de bateria U-200",
       (x0 + 6, y1 - 20.5), 2.8, "TEXTO_NOTA")

# ----------------------------------------------------------------- tabela de correntes
sx0, sy0 = x0 + 6, y0 + 6 + 138 + 8
cols_ = [0, 44, 74, 104, 134, 164, 194, 224, 254]
heads_ = ["CORRENTE", "1 ENT. TK", "2 SUCÇÃO", "3 DESCARGA", "4 RECIRC.", "5 SAÍDA E-101", "V VAPOR LP", "C CONDENS."]
rows_ = [("Fase", "Líquido", "Líquido", "Líquido", "Líquido", "Líquido", "Vapor", "Líq. sat."),
         ("Vazão (m³/h)", "25,0", "25,0", "25,0", "3,0", "22,0", "0,29 t/h", "0,29 t/h"),
         ("Pressão (barg)", "0,10", "0,05", "6,80", "6,80", "6,40", "3,50", "3,20"),
         ("Temperatura (°C)", "35", "35", "35", "35", "70", "148", "136"),
         ("Massa específica (kg/m³)", "880", "880", "880", "880", "860", "—", "930"),
         ("Viscosidade (cP)", "4,2", "4,2", "4,2", "4,2", "2,1", "—", "—")]
tw_ = cols_[-1]
d.text("TABELA DE CORRENTES (CONDIÇÃO NORMAL DE OPERAÇÃO)", (sx0, sy0 + 6 * 5 + 11), 3, "CARIMBO_TXT")
d.rect(sx0, sy0, tw_, 5 * (len(rows_) + 1), "CARIMBO")
for k in range(1, len(rows_) + 1):
    d.line((sx0, sy0 + 5 * k), (sx0 + tw_, sy0 + 5 * k), "CARIMBO")
for cx in cols_[1:-1]:
    d.line((sx0 + cx, sy0), (sx0 + cx, sy0 + 5 * (len(rows_) + 1)), "CARIMBO")
for cx, h_ in zip(cols_, heads_):
    d.text(h_, (sx0 + cx + 1.5, sy0 + 5 * len(rows_) + 1.5), 1.9, "TEXTO_NOTA")
for i_, r_ in enumerate(rows_):
    for cx, t_ in zip(cols_, r_):
        d.text(t_, (sx0 + cx + 1.5, sy0 + 5 * (len(rows_) - 1 - i_) + 1.5), 2.0, "TEXTO")

# ----------------------------------------------------------------- legenda
lx, ly, lw, lh = x0 + 6, y0 + 6, 215, 138
d.rect(lx, ly, lw, lh, "CARIMBO"); d.text("LEGENDA", (lx + 3, ly + lh - 6), 3, "CARIMBO_TXT"); d.line((lx, ly + lh - 8), (lx + lw, ly + lh - 8), "CARIMBO")
def leg(row, col, fn, label, line=False):
    cx = lx + 8 + col * 106; cy = ly + lh - 18 - row * 11
    if line:
        fn(cx - 4, cy)
    else:
        d.line((cx - 7, cy), (cx + 7, cy), "LINHA_PROC_SEC")
        fn((cx, cy))
    d.text(label, (cx + 12, cy - 1.2), 2.1, "TEXTO")
leg(0, 0, lambda p: valve_gate(d, p), "Válvula de bloqueio (gaveta)")
leg(1, 0, lambda p: valve_globe(d, p), "Válvula globo")
leg(2, 0, lambda p: valve_check(d, p), "Válvula de retenção")
leg(3, 0, lambda p: valve_control(d, p, 0), "Válvula de controle (FC)")
leg(4, 0, lambda p: valve_psv(d, p), "Válvula de segurança/alívio")
leg(5, 0, lambda p: strainer(d, p), "Filtro tipo Y")
leg(6, 0, lambda p: flange(d, p), "Flange")
leg(7, 0, lambda p: instrument(d, p, "XX", "", "field", 4.2), "Instrumento de campo")
leg(8, 0, lambda p: instrument(d, p, "XX", "", "dcs", 4.2), "Instrumento no SDCD")
leg(9, 0, lambda p: d.arrow(p, 0), "Sentido de escoamento")
for i, (lay, lab) in enumerate([("LINHA_PROC", "Linha de processo principal"), ("LINHA_PROC_SEC", "Linha secundária / bypass"),
                                 ("LINHA_UTIL", "Utilidade (vapor/condensado)"), ("LINHA_INSTR", "Impulso de instrumento"),
                                 ("LINHA_SINAL", "Sinal elétrico/eletrônico")]):
    cy = ly + lh - 18 - i * 11
    d.line((lx + 106 + 1, cy), (lx + 106 + 16, cy), lay)
    d.text(lab, (lx + 106 + 20, cy - 1.2), 2.1, "TEXTO")
d.text("Código de linha:  DN - SERVIÇO - Nº - CLASSE - ISOLAMENTO", (lx + 106 + 1, ly + lh - 18 - 6 * 11), 1.9, "TEXTO_NOTA")
d.text("Ex.:  6\"-P-1003-CS150-N", (lx + 106 + 1, ly + lh - 18 - 6.8 * 11), 2.1, "TEXTO")
d.text("P=Processo  LS=Vapor LP  CD=Condensado  V=Vent", (lx + 106 + 1, ly + lh - 18 - 7.6 * 11), 1.7, "TEXTO_NOTA")
d.text("N=sem isolamento  H=conservação de calor", (lx + 106 + 1, ly + lh - 18 - 8.3 * 11), 1.7, "TEXTO_NOTA")
d.text("FC=falha fechada  LAH/LAL=alarme nível alto/baixo", (lx + 106 + 1, ly + lh - 18 - 9 * 11), 1.7, "TEXTO_NOTA")

# ----------------------------------------------------------------- notas
notes_box(d, lx + lw + 8, ly + lh - 2, 222, [
    "Dimensões de bocais e base do tanque: ver desenho EX-TK-101-001.",
    "TK-101 projetado para 0,07 barg / -0,02 barg e 80 °C (API 650 / 1 atm).",
    "Todas as linhas de produto em aço-carbono, classe CS150, exceto onde indicado.",
    "Isolamento 'H' em 50 mm de lã mineral com chapa de alumínio.",
    "Intertravamento LAL-101 desliga P-101A/B; LAH-101 fecha XV de U-100.",
    "Bomba em reserva parte automaticamente por baixa pressão (PAL-102).",
    "Placa de orifício FE-101 dimensionada para 25 m³/h (ASME MFC-3M).",
    "Dados de processo fictícios, apenas para demonstração do MCP.",
], title="NOTAS GERAIS", h=2.3)

# ----------------------------------------------------------------- lista de equipamentos e instrumentos
tx0, tyt, tw0 = lx + lw + 8 + 230, ly + lh - 2, x1 - 190 - 12 - (lx + lw + 8 + 230) + 190 - 6
tw0 = x1 - tx0 - 6
d.text("LISTA DE EQUIPAMENTOS", (tx0, tyt), 3, "CARIMBO_TXT"); d.line((tx0, tyt - 1.5), (tx0 + tw0, tyt - 1.5), "CARIMBO")
cols = [0, 20, 78, 112, 152]
heads = ["TAG", "DESCRIÇÃO", "CAPACIDADE", "PROJETO (P/T)", "MATERIAL"]
rows = [("TK-101", "Tanque de armazenamento", "50 m³", "0,07 barg / 80 °C", "SA-283 C"),
        ("P-101A/B", "Bomba centrífuga", "25 m³/h x 45 m", "10 barg / 80 °C", "ASTM A216 WCB"),
        ("E-101", "Trocador casco-tubo", "180 kW", "12 / 4 barg  / 160 °C", "SA-516 70"),
        ("FCV-101", "Válvula de controle", "Cv 28", "ANSI 150", "WCB / TRIM 316"),
        ("TCV-101", "Válvula de controle vapor", "Cv 6,3", "ANSI 150", "WCB / TRIM 316"),
        ("PSV-102", "Alívio térmico", "1\" x 1\"", "SET 12 barg", "WCB")]
y = tyt - 5
for c, h_ in zip(cols, heads):
    d.text(h_, (tx0 + c + 1, y - 3.4), 1.9, "TEXTO_NOTA")
d.rect(tx0, y - 5, tw0, 5 * (len(rows) + 1) + 0, "CARIMBO") if False else None
yy = y - 5.5
for r in rows:
    d.line((tx0, yy), (tx0 + tw0, yy), "CARIMBO")
    for c, t in zip(cols, r):
        d.text(t, (tx0 + c + 1, yy - 4), 2.1, "TEXTO")
    yy -= 5
d.line((tx0, yy), (tx0 + tw0, yy), "CARIMBO")

# ----------------------------------------------------------------- revisões e carimbo
tbx, tby = title_block(d, x1, y0, "P&ID - TRANSFERÊNCIA E AQUECIMENTO", "Tanque TK-101, bombas P-101A/B e trocador E-101", "EX-PID-100-001", "0", "S/ESCALA", "A1", "1/1")
revision_table(d, x1, tby, [("0", "05/10/26", "EMISSÃO PARA DEMONSTRAÇÃO DO MCP", "MCP", "—", "—"), ("A", "—", "—", "—", "—", "—")], 190)

save(doc, OUT, "05_pid_tanque_bombas_trocador")
