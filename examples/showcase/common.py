"""Biblioteca comum dos exemplos: layers, estilos, folha/carimbo, cotas, chamadas, símbolos de P&ID.

Tudo em milímetros de papel (1 unidade = 1 mm impresso) salvo onde o exemplo usa viewport com escala.
Usa o motor `autocad_mcp.dxf_engine` (create_doc/ensure_layer/add_entity/define_block/add_dimension/create_layout/export_render)
e ezdxf diretamente para geometria auxiliar.
"""
from __future__ import annotations

import math
from pathlib import Path

from autocad_mcp import dxf_engine as eng

LAYERS = [  # nome, ACI, linetype, lineweight(1/100 mm)
    ("FORMATO", 8, None, 25), ("CARIMBO", 7, None, 25), ("CARIMBO_TXT", 7, None, 13),
    ("LINHA_PROC", 7, None, 50), ("LINHA_PROC_SEC", 7, None, 35), ("LINHA_UTIL", 3, "DASHED", 35),
    ("LINHA_INSTR", 5, "DASHED", 18), ("LINHA_SINAL", 5, "DASHDOT", 18), ("EQUIP", 4, None, 50), ("EQUIP_DET", 4, None, 25),
    ("VALV", 2, None, 35), ("INSTR", 3, None, 25), ("TAG", 2, None, 18), ("TEXTO", 7, None, 18), ("TEXTO_NOTA", 9, None, 13),
    ("COTAS", 3, None, 18), ("EIXO", 1, "DASHDOT", 18), ("OCULTA", 8, "DASHED", 13), ("HACHURA", 8, None, 9),
    ("CHAMADA", 7, None, 13), ("LEGENDA", 6, None, 18), ("PISTA", 30, None, 35), ("EDIF", 6, None, 35),
    ("CERCA", 8, "DASHED", 25), ("TUBOVIA", 4, None, 35), ("AREA", 5, "DASHDOT", 25), ("ESTRUT", 2, None, 35),
    ("VEGETACAO", 3, None, 13), ("NORTE", 7, None, 35),
]
SIZES = {"A3": (420, 297), "A1": (841, 594), "A2": (594, 420)}


def new_doc(units="mm"):
    doc = eng.create_doc("R2018", units)
    for name, aci, lt, lw in LAYERS:
        if lt and lt not in doc.linetypes:
            lt = None
        eng.ensure_layer(doc, name, aci, lt)
        doc.layers.get(name).dxf.lineweight = lw
    if "MCP" not in doc.styles:
        doc.styles.add("MCP", font="arial.ttf")
    ds = doc.dimstyles.new("MCP", dxfattribs={"dimtxsty": "MCP"})
    ds.dxf.dimtxt = 2.5; ds.dxf.dimasz = 2.5; ds.dxf.dimexe = 1.0; ds.dxf.dimexo = 0.8; ds.dxf.dimgap = 0.8
    ds.dxf.dimdec = 0; ds.dxf.dimlfac = 1.0; ds.dxf.dimtad = 1; ds.dxf.dimtih = 0; ds.dxf.dimtoh = 0
    ds.dxf.dimclrd = 3; ds.dxf.dimclre = 3; ds.dxf.dimclrt = 3
    return doc


class D:
    """Atalhos de desenho sobre um espaço (modelspace ou layout)."""

    def __init__(self, doc, space):
        self.doc, self.sp = doc, space

    def line(self, a, b, layer="LINHA_PROC", **kw):
        return self.sp.add_line(a, b, dxfattribs={"layer": layer, **kw})

    def poly(self, pts, layer="LINHA_PROC", close=False, **kw):
        return self.sp.add_lwpolyline(pts, close=close, dxfattribs={"layer": layer, **kw})

    def rect(self, x, y, w, h, layer="EQUIP", **kw):
        return self.poly([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], layer, True, **kw)

    def circle(self, c, r, layer="EQUIP", **kw):
        return self.sp.add_circle(c, r, dxfattribs={"layer": layer, **kw})

    def arc(self, c, r, a0, a1, layer="EQUIP", **kw):
        return self.sp.add_arc(c, r, a0, a1, dxfattribs={"layer": layer, **kw})

    def text(self, s, p, h=2.5, layer="TEXTO", rot=0, align="LEFT", **kw):
        t = self.sp.add_text(str(s), height=h, rotation=rot, dxfattribs={"layer": layer, "style": "MCP", **kw})
        t.set_placement(p, align=getattr(__import__("ezdxf.enums", fromlist=["TextEntityAlignment"]).TextEntityAlignment, align))
        return t

    def mtext(self, s, p, h=2.5, w=0, layer="TEXTO", attach=1, **kw):
        m = self.sp.add_mtext(s, dxfattribs={"layer": layer, "style": "MCP", "char_height": h, "attachment_point": attach, **kw})
        m.set_location(p)
        if w:
            m.dxf.width = w
        return m

    def hatch_solid(self, pts, color=7, layer="HACHURA"):
        h = self.sp.add_hatch(color=color, dxfattribs={"layer": layer})
        h.paths.add_polyline_path(pts, is_closed=True)
        return h

    def hatch_pat(self, pts, pattern="ANSI31", scale=1.0, color=8, layer="HACHURA"):
        h = self.sp.add_hatch(color=color, dxfattribs={"layer": layer})
        h.set_pattern_fill(pattern, scale=scale)
        h.paths.add_polyline_path(pts, is_closed=True)
        return h

    def arrow(self, tip, ang, size=2.5, layer="LINHA_PROC"):
        a = math.radians(ang)
        b1 = (tip[0] - size * math.cos(a - 0.22), tip[1] - size * math.sin(a - 0.22))
        b2 = (tip[0] - size * math.cos(a + 0.22), tip[1] - size * math.sin(a + 0.22))
        self.hatch_solid([tip, b1, b2], color=7, layer=layer)

    def dim(self, kind, **spec):
        spec["kind"] = kind
        spec.setdefault("layer", "COTAS")
        spec.setdefault("dimstyle", "MCP")
        return eng.add_dimension(self.doc, self.sp, spec)

    def leader(self, tip, p_text, text, h=2.2, layer="CHAMADA", side=None, arrow=True):
        """Chamada: ponta -> cotovelo -> linha de texto com sublinhado; `text` pode ter \\n (linhas sobre a linha)."""
        side = side or (1 if p_text[0] >= tip[0] else -1)
        lines = str(text).split("\n")
        tw = max(len(l) for l in lines) * h * 0.62 + 2
        self.line(tip, p_text, layer)
        self.line(p_text, (p_text[0] + side * tw, p_text[1]), layer)
        if arrow:
            ang = math.degrees(math.atan2(tip[1] - p_text[1], tip[0] - p_text[0]))
            self.arrow(tip, ang, 2.0, layer)
        for i, l in enumerate(reversed(lines)):
            x = p_text[0] + (1 if side > 0 else -tw + 1)
            self.text(l, (x, p_text[1] + 0.8 + i * (h + 0.8)), h, "TEXTO")

    def balloon(self, c, label, r=4, layer="CHAMADA", h=2.5):
        self.circle(c, r, layer)
        self.text(label, c, h, layer, align="MIDDLE_CENTER")


def frame(d: D, size="A1", margin_l=20, margin=7):
    """Moldura: borda de papel + moldura interna (margem esquerda maior p/ furação)."""
    w, h = SIZES[size]
    d.rect(0, 0, w, h, "FORMATO")
    x0, y0, x1, y1 = margin_l, margin, w - margin, h - margin
    d.rect(x0, y0, x1 - x0, y1 - y0, "CARIMBO", lineweight=70)
    # marcas de centro e zonas (A-F / 1-8)
    nx, ny = (8, 6) if size == "A1" else (6, 4)
    for i in range(1, nx):
        x = x0 + (x1 - x0) * i / nx
        d.line((x, y1), (x, y1 + 4), "FORMATO"); d.line((x, y0), (x, y0 - 4), "FORMATO")
    for i in range(nx):
        x = x0 + (x1 - x0) * (i + 0.5) / nx
        d.text(str(i + 1), (x, y1 + 2), 2.5, "FORMATO", align="MIDDLE_CENTER")
    for j in range(1, ny):
        y = y0 + (y1 - y0) * j / ny
        d.line((x0, y), (x0 - 4, y), "FORMATO"); d.line((x1, y), (x1 + 4, y), "FORMATO")
    for j in range(ny):
        y = y0 + (y1 - y0) * (j + 0.5) / ny
        d.text(chr(ord("A") + ny - 1 - j), (x0 - 2, y), 2.5, "FORMATO", align="MIDDLE_CENTER")
    return x0, y0, x1, y1


def title_block(d: D, x1, y0, title, subtitle, doc_no, rev="0", scale="S/ESCALA", size="A1", sheet="1/1", author="MCP"):
    """Carimbo no canto inferior direito: cliente/logo, título, 4 responsáveis, escala/folha/formato/data, nº do documento e revisão."""
    W = 190 if size == "A1" else 175
    H = 56
    x = x1 - W
    d.rect(x, y0, W, H, "CARIMBO", lineweight=50)
    for yy in (14, 26, 38):
        d.line((x, y0 + yy), (x1, y0 + yy), "CARIMBO")
    # logotipo fictício + cliente
    d.circle((x + 10, y0 + 47), 6.5, "LEGENDA", lineweight=35)
    d.poly([(x + 5.5, y0 + 44), (x + 10, y0 + 51), (x + 14.5, y0 + 44)], "LEGENDA")
    d.line((x + 6.5, y0 + 46.5), (x + 13.5, y0 + 46.5), "LEGENDA")
    d.text("CLIENTE EXEMPLO S.A.", (x + 20, y0 + 49), 4.0, "CARIMBO_TXT")
    d.text("Unidade de Demonstração - Projeto Básico (dados fictícios)", (x + 20, y0 + 42.2), 2.4, "TEXTO_NOTA")
    d.text("TÍTULO / DOCUMENTO", (x + 2, y0 + 35.4), 1.6, "TEXTO_NOTA")
    d.text(title, (x + 2, y0 + 30.6), 3.4, "CARIMBO_TXT")
    d.text(subtitle, (x + 2, y0 + 27.4), 1.9, "TEXTO")
    for lab, val, px in [("PROJETO", author, 0), ("DESENHO", author, 1), ("VERIFICAÇÃO", "—", 2), ("APROVAÇÃO", "—", 3)]:
        cx = x + W / 4 * px
        if px:
            d.line((cx, y0 + 14), (cx, y0 + 26), "CARIMBO")
        d.text(lab, (cx + 2, y0 + 22.6), 1.6, "TEXTO_NOTA"); d.text(val, (cx + 2, y0 + 17.2), 2.8, "CARIMBO_TXT")
    cells = [("ESCALA", scale, 0, 28), ("FOLHA", sheet, 28, 50), ("FORMATO", size, 50, 72), ("DATA", "05/10/2026", 72, 102),
             ("Nº DO DOCUMENTO", doc_no, 102, 168), ("REV.", rev, 168, W)]
    for lab, val, a, b in cells:
        if a:
            d.line((x + a, y0), (x + a, y0 + 14), "CARIMBO")
        d.text(lab, (x + a + 2, y0 + 10.8), 1.6, "TEXTO_NOTA")
        d.text(val, (x + a + 2, y0 + 3.8), 5.5 if lab == "REV." else 2.9, "CARIMBO_TXT")
    return x, y0 + H


def revision_table(d: D, x_right, y_bottom, rows=None, w=190):
    """Tabela de revisões acima do carimbo."""
    rows = rows or [("0", "05/10/26", "EMISSÃO INICIAL", "MCP", "—", "—")]
    h = 5.2
    x = x_right - w
    n = len(rows) + 1
    d.rect(x, y_bottom, w, h * n, "CARIMBO")
    cols = [0, 12, 34, 128, 150, 170, w]
    for c in cols[1:-1]:
        d.line((x + c, y_bottom), (x + c, y_bottom + h * n), "CARIMBO")
    for i in range(1, n):
        d.line((x, y_bottom + h * i), (x + w, y_bottom + h * i), "CARIMBO")
    hdr = ["REV.", "DATA", "DESCRIÇÃO", "POR", "VERIF.", "APROV."]
    for c, t in zip(cols, hdr):
        d.text(t, (x + c + 1.5, y_bottom + h * (n - 1) + 1.5), 1.8, "TEXTO_NOTA")
    for r, row in enumerate(rows):
        for c, t in zip(cols, row):
            d.text(t, (x + c + 1.5, y_bottom + h * (n - 2 - r) + 1.4), 2.2, "TEXTO")
    return y_bottom + h * n


def notes_box(d: D, x, y_top, w, notes, title="NOTAS GERAIS", h=2.4):
    lines = []
    for i, n in enumerate(notes, 1):
        lines.append(f"{i}. {n}")
    d.text(title, (x, y_top), h + 0.6, "CARIMBO_TXT")
    d.line((x, y_top - 1.2), (x + w, y_top - 1.2), "CARIMBO")
    y = y_top - 5.2
    for l in lines:
        d.text(l, (x, y), h, "TEXTO")
        y -= h + 1.6
    return y


# ----------------------------------------------------------------------------------- símbolos de P&ID (origem no centro do símbolo)
def valve_gate(d, c, rot=0, layer="VALV"):
    s = 2.6
    x, y = c
    pts = [[(x - s, y - s * .75), (x - s, y + s * .75), (x, y), (x - s, y - s * .75)], [(x + s, y - s * .75), (x + s, y + s * .75), (x, y), (x + s, y - s * .75)]]
    for p in pts:
        d.poly(_rot(p, c, rot), layer, True)


def valve_globe(d, c, rot=0, layer="VALV"):
    valve_gate(d, c, rot, layer)
    d.circle(c, 0.8, layer)
    d.sp.add_circle(c, 0.8, dxfattribs={"layer": layer})


def valve_check(d, c, rot=0, layer="VALV"):
    valve_gate(d, c, rot, layer)
    x, y = c
    d.poly(_rot([(x - 1.6, y + 1.9), (x - 1.6, y - 1.9), (x + 1.6, y)], c, rot), layer, True)


def valve_ball(d, c, rot=0, layer="VALV"):
    valve_gate(d, c, rot, layer)
    d.circle(c, 1.5, layer)


def valve_control(d, c, rot=0, layer="VALV", fail="FC"):
    """Válvula de controle: corpo globo + atuador diafragma (semicírculo) com haste."""
    valve_globe(d, c, rot, layer)
    x, y = c
    d.line(_pt(c, rot, 0, 0), _pt(c, rot, 0, 5.5), layer)
    d.arc(_pt(c, rot, 0, 5.5), 3.2, 0 + rot, 180 + rot, layer)
    d.text(fail, _pt(c, rot, 0, 8.6), 1.8, "TAG", align="MIDDLE_CENTER")


def valve_psv(d, c, rot=0, layer="VALV"):
    """PSV (ângulo): corpo ângulo + mola."""
    x, y = c
    d.poly(_rot([(x - 2.4, y - 2.0), (x + 2.4, y - 2.0), (x, y + 1.0), (x - 2.4, y - 2.0)], c, rot), layer, True)
    d.poly(_rot([(x - 2.4, y + 4.0), (x + 2.4, y + 4.0), (x, y + 1.0), (x - 2.4, y + 4.0)], c, rot), layer, True)
    d.poly(_rot([(x - 1.5, y + 4.0), (x + 1.5, y + 4.4), (x - 1.5, y + 5.0), (x + 1.5, y + 5.6), (x - 1.5, y + 6.2), (x + 1.5, y + 6.8)], c, rot), layer)


def reducer(d, c, rot=0, layer="LINHA_PROC"):
    x, y = c
    d.poly(_rot([(x - 2, y - 2.2), (x + 2, y - 1.2), (x + 2, y + 1.2), (x - 2, y + 2.2)], c, rot), layer, True)


def flange(d, c, rot=0, layer="VALV"):
    x, y = c
    d.line(*_rot([(x, y - 2.2), (x, y + 2.2)], c, rot), layer)


def blind(d, c, rot=0, layer="VALV"):
    x, y = c
    d.poly(_rot([(x - 1.0, y - 2.2), (x + 1.0, y - 2.2), (x + 1.0, y + 2.2), (x - 1.0, y + 2.2)], c, rot), layer, True)
    d.hatch_solid(_rot([(x - 1.0, y - 2.2), (x + 1.0, y - 2.2), (x + 1.0, y + 2.2), (x - 1.0, y + 2.2)], c, rot), 2)


def strainer(d, c, rot=0, layer="VALV"):
    x, y = c
    d.poly(_rot([(x - 3, y - 2), (x + 3, y - 2), (x + 3, y + 2), (x - 3, y + 2)], c, rot), layer, True)
    d.line(*_rot([(x - 3, y - 2), (x + 3, y + 2)], c, rot), layer)


def instrument(d, c, tag, num, kind="field", r=4.6, layer="INSTR", h=None):
    """Balão ISA 5.1: kind field (sem linha), panel (linha cheia, sala de controle), dcs (linha + círculo duplo/quadrado)."""
    x, y = c
    if kind == "dcs":
        d.rect(x - r, y - r, 2 * r, 2 * r, layer)
        d.circle(c, r, layer)
        d.line((x - r, y), (x + r, y), layer)
    else:
        d.circle(c, r, layer)
        if kind == "panel":
            d.line((x - r, y), (x + r, y), layer)
        elif kind == "local_panel":
            d.line((x - r, y), (x + r, y), layer, linetype="DASHED")
    h = h or (2.4 if r >= 4.2 else 1.9)
    d.text(tag, (x, y + r * 0.42), h, "TAG", align="MIDDLE_CENTER")
    d.text(num, (x, y - r * 0.45), h, "TAG", align="MIDDLE_CENTER")


def _rot(pts, c, rot):
    if not rot:
        return pts
    a = math.radians(rot)
    ca, sa = math.cos(a), math.sin(a)
    return [(c[0] + (px - c[0]) * ca - (py - c[1]) * sa, c[1] + (px - c[0]) * sa + (py - c[1]) * ca) for px, py in pts]


def _pt(c, rot, dx, dy):
    return _rot([(c[0] + dx, c[1] + dy)], c, rot)[0]


def line_tag(d, p, text, w=36, layer="TAG"):
    """Etiqueta de linha (flag): retângulo com ID da linha no estilo diâmetro-serviço-nº-classe-isolamento."""
    x, y = p
    d.rect(x, y, w, 5.4, layer)
    d.text(text, (x + w / 2, y + 2.7), 2.2, layer, align="MIDDLE_CENTER")


def save(doc, out: Path, name, layout=None, dpi=None, background="black", size_in=(16.5, 11.7)):
    import os
    dpi = dpi or int(os.environ.get("SHOWCASE_DPI", "200"))
    out.mkdir(parents=True, exist_ok=True)
    doc.saveas(str(out / f"{name}.dxf"))
    r = eng.export_render(doc, out / f"{name}.png", layout=layout, dpi=dpi, background=background, size_in=size_in)
    print(name, r["bytes"], "bytes", r["page_inches"])
    return r
