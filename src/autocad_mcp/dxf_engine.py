"""Motor DXF offline (ezdxf): lê, cria e edita desenhos SEM AutoCAD aberto.

Independente da camada COM. Funções puras sobre arquivos; a restrição de pastas e o modo somente
leitura são aplicados pelas ferramentas (`tools/dxf.py`). Nenhum código de terceiros foi copiado.
"""

from __future__ import annotations

import math
import os
import re
import sqlite3
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

import ezdxf
from ezdxf import units as ezunits
from ezdxf.document import Drawing
from ezdxf.entities import DXFGraphic

from autocad_mcp.errors import EntityNotFoundError, InvalidParameterError

VERSIONS = {"R2000", "R2004", "R2007", "R2010", "R2013", "R2018"}
UNITS = {"mm": ezunits.MM, "cm": ezunits.CM, "m": ezunits.M, "in": ezunits.IN, "ft": ezunits.FT, "unitless": 0}
UNIT_NAMES = {v: k for k, v in UNITS.items()}
MAX_ENTITIES_PER_CALL = 5000
PAPERS_MM = {"A4": (297, 210), "A3": (420, 297), "A2": (594, 420), "A1": (841, 594), "A0": (1189, 841)}
ENTITY_TYPES = {"line", "circle", "arc", "polyline", "text", "mtext", "point", "insert", "hatch", "ellipse"}


# --------------------------------------------------------------------------- abrir / salvar

def open_doc(path: Path) -> Drawing:
    try:
        return ezdxf.readfile(str(path))
    except (ezdxf.DXFError, OSError, UnicodeDecodeError) as exc:
        try:  # arquivo com erros estruturais leves
            from ezdxf import recover

            doc, _auditor = recover.readfile(str(path))
            return doc
        except Exception:  # noqa: BLE001
            raise InvalidParameterError(f"Não consegui abrir o DXF '{path.name}': {exc}") from exc


def save_doc(doc: Drawing, path: Path) -> None:
    tmp = path.with_name(path.name + ".tmp")
    try:
        doc.saveas(str(tmp))
        os.replace(tmp, path)  # gravação atômica: nunca deixa um DXF pela metade
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        raise InvalidParameterError(f"Não consegui salvar '{path.name}': {exc}") from exc


def create_doc(version: str = "R2018", units: str = "mm") -> Drawing:
    version = version.upper()
    if version not in VERSIONS:
        raise InvalidParameterError(f"version deve ser uma de {sorted(VERSIONS)}.")
    if units not in UNITS:
        raise InvalidParameterError(f"units deve ser uma de {sorted(UNITS)}.")
    return ezdxf.new(version, setup=True, units=UNITS[units])


# --------------------------------------------------------------------------- helpers

def _pt(value: Any, name: str, *, dims: int = 3) -> tuple[float, ...]:
    if not isinstance(value, (list, tuple)) or len(value) not in (2, 3):
        raise InvalidParameterError(f"'{name}' deve ser [x, y] ou [x, y, z].")
    try:
        nums = tuple(float(v) for v in value)
    except (TypeError, ValueError) as exc:
        raise InvalidParameterError(f"'{name}' contém valor não numérico.") from exc
    if not all(math.isfinite(n) for n in nums):
        raise InvalidParameterError(f"'{name}' contém valor não finito.")
    return nums + (0.0,) * (dims - len(nums)) if dims == 3 else nums[:2]


def _num(spec: dict, key: str, *, positive: bool = False, default: float | None = None) -> float:
    if key not in spec:
        if default is not None:
            return default
        raise InvalidParameterError(f"Campo obrigatório ausente: '{key}'.")
    try:
        v = float(spec[key])
    except (TypeError, ValueError) as exc:
        raise InvalidParameterError(f"'{key}' deve ser numérico.") from exc
    if not math.isfinite(v) or (positive and v <= 0):
        raise InvalidParameterError(f"'{key}' deve ser {'positivo e ' if positive else ''}finito.")
    return v


def ensure_layer(doc: Drawing, name: str, color: int | None = None, linetype: str | None = None) -> None:
    if name not in doc.layers:
        attrs: dict[str, Any] = {}
        if color is not None:
            attrs["color"] = int(color)
        if linetype:
            if linetype not in doc.linetypes:
                raise InvalidParameterError(f"Tipo de linha '{linetype}' não existe no desenho.")
            attrs["linetype"] = linetype
        doc.layers.add(name, **attrs)


def _common(spec: dict, doc: Drawing) -> dict[str, Any]:
    attrs: dict[str, Any] = {}
    layer = spec.get("layer")
    if layer:
        ensure_layer(doc, str(layer))
        attrs["layer"] = str(layer)
    if spec.get("color") is not None:
        c = int(spec["color"])
        if not 0 <= c <= 256:
            raise InvalidParameterError("color deve estar entre 0 e 256 (ACI).")
        attrs["color"] = c
    return attrs


def add_entity(doc: Drawing, space, spec: dict[str, Any]) -> Any:
    """Cria UMA entidade a partir de um dict; devolve a entidade ezdxf."""
    if not isinstance(spec, dict) or "type" not in spec:
        raise InvalidParameterError("Cada entidade precisa ser um objeto com o campo 'type'.")
    t = str(spec["type"]).lower()
    if t not in ENTITY_TYPES:
        raise InvalidParameterError(f"type '{t}' não suportado; use um de {sorted(ENTITY_TYPES)}.")
    attrs = _common(spec, doc)
    if t == "line":
        return space.add_line(_pt(spec.get("start"), "start"), _pt(spec.get("end"), "end"), dxfattribs=attrs)
    if t == "circle":
        return space.add_circle(_pt(spec.get("center"), "center"), _num(spec, "radius", positive=True), dxfattribs=attrs)
    if t == "arc":
        return space.add_arc(_pt(spec.get("center"), "center"), _num(spec, "radius", positive=True),
                             _num(spec, "start_angle"), _num(spec, "end_angle"), dxfattribs=attrs)
    if t == "polyline":
        pts = spec.get("points")
        if not isinstance(pts, list) or len(pts) < 2:
            raise InvalidParameterError("polyline exige 'points' com ao menos 2 pontos.")
        return space.add_lwpolyline([_pt(p, "points[]", dims=2) for p in pts], close=bool(spec.get("closed", False)),
                                    dxfattribs=attrs)
    if t == "text":
        text = space.add_text(str(spec.get("text", "")), height=_num(spec, "height", positive=True, default=2.5),
                              dxfattribs=attrs | {"rotation": _num(spec, "rotation", default=0.0)})
        text.set_placement(_pt(spec.get("insert"), "insert"))
        return text
    if t == "mtext":
        return space.add_mtext(str(spec.get("text", "")), dxfattribs=attrs | {
            "insert": _pt(spec.get("insert"), "insert"), "char_height": _num(spec, "height", positive=True, default=2.5)})
    if t == "point":
        return space.add_point(_pt(spec.get("location"), "location"), dxfattribs=attrs)
    if t == "ellipse":
        return space.add_ellipse(_pt(spec.get("center"), "center"), major_axis=_pt(spec.get("major_axis"), "major_axis"),
                                 ratio=_num(spec, "ratio", positive=True), dxfattribs=attrs)
    if t == "hatch":
        pts = spec.get("points")
        if not isinstance(pts, list) or len(pts) < 3:
            raise InvalidParameterError("hatch exige 'points' (contorno fechado, ao menos 3 pontos).")
        h = space.add_hatch(color=int(spec.get("color", 7)), dxfattribs={k: v for k, v in attrs.items() if k != "color"})
        pattern = spec.get("pattern")
        if pattern:
            h.set_pattern_fill(str(pattern), scale=_num(spec, "scale", positive=True, default=1.0))
        h.paths.add_polyline_path([_pt(p, "points[]", dims=2) for p in pts], is_closed=True)
        return h
    # insert
    name = str(spec.get("block", ""))
    if name not in doc.blocks:
        raise InvalidParameterError(f"Bloco '{name}' não existe no desenho (defina-o antes).")
    ref = space.add_blockref(name, _pt(spec.get("insert"), "insert"), dxfattribs=attrs | {
        "xscale": _num(spec, "xscale", default=1.0), "yscale": _num(spec, "yscale", default=1.0),
        "zscale": _num(spec, "zscale", default=1.0), "rotation": _num(spec, "rotation", default=0.0)})
    if isinstance(spec.get("attributes"), dict):
        ref.add_auto_attribs({str(k).upper(): str(v) for k, v in spec["attributes"].items()})
    return ref


def define_block(doc: Drawing, name: str, entities: list[dict], attributes: list[str] | None = None,
                 base_point: tuple[float, float] = (0.0, 0.0)) -> None:
    if not name or name in doc.blocks:
        raise InvalidParameterError(f"Nome de bloco vazio ou já existente: '{name}'.")
    blk = doc.blocks.new(name=name, base_point=base_point)
    for spec in entities:
        add_entity(doc, blk, spec)
    for i, tag in enumerate(attributes or []):
        blk.add_attdef(str(tag).upper(), (0, -2.5 * (i + 1)), str(tag), dxfattribs={"height": 2.0})


# --------------------------------------------------------------------------- consulta

def _space(doc: Drawing, layout: str | None):
    if not layout or layout.lower() in {"model", "modelspace"}:
        return doc.modelspace()
    try:
        return doc.layouts.get(layout)
    except KeyError as exc:
        raise InvalidParameterError(f"Layout '{layout}' não existe; use dxf_info para listar.") from exc


def entity_summary(e: Any, *, detail: bool = False) -> dict[str, Any]:
    d = e.dxf
    t = e.dxftype()
    row: dict[str, Any] = {"handle": d.handle, "type": t, "layer": d.get("layer", "0"), "color": d.get("color", 256)}
    try:
        if t == "LINE":
            s, en = d.start, d.end
            row["geometry"] = {"start": list(s.xyz), "end": list(en.xyz), "length": round(s.distance(en), 6)}
        elif t == "CIRCLE":
            row["geometry"] = {"center": list(d.center.xyz), "radius": d.radius}
        elif t == "ARC":
            row["geometry"] = {"center": list(d.center.xyz), "radius": d.radius,
                               "start_angle": d.start_angle, "end_angle": d.end_angle}
        elif t == "LWPOLYLINE":
            pts = [list(p[:2]) for p in e.get_points()]
            row["geometry"] = {"points": pts if detail or len(pts) <= 20 else pts[:20], "n_points": len(pts),
                               "closed": bool(e.closed)}
        elif t in ("TEXT", "MTEXT"):
            row["geometry"] = {"text": e.dxf.text if t == "TEXT" else e.text, "insert": list(d.insert.xyz)}
        elif t == "INSERT":
            attrs = {a.dxf.tag: a.dxf.text for a in e.attribs}
            row["geometry"] = {"block": d.name, "insert": list(d.insert.xyz), "rotation": d.get("rotation", 0.0)}
            row["attributes"] = attrs
        elif t == "POINT":
            row["geometry"] = {"location": list(d.location.xyz)}
        elif t == "DIMENSION":
            row["geometry"] = {"measurement": round(float(e.get_measurement()), 6) if hasattr(e, "get_measurement") else None,
                               "dimstyle": d.get("dimstyle", "")}
    except Exception:  # noqa: BLE001 - resumo é best-effort; nunca derruba a consulta
        row.setdefault("geometry", None)
    return row


def info(doc: Drawing) -> dict[str, Any]:
    msp = doc.modelspace()
    counts: dict[str, int] = {}
    for e in msp:
        counts[e.dxftype()] = counts.get(e.dxftype(), 0) + 1
    extents = None
    try:
        from ezdxf import bbox

        box = bbox.extents(msp, fast=True)
        if box.has_data:
            extents = {"min": list(box.extmin.xyz), "max": list(box.extmax.xyz)}
    except Exception:  # noqa: BLE001
        pass
    unit_code = int(doc.header.get("$INSUNITS", 0))
    return {"version": doc.dxfversion, "units": UNIT_NAMES.get(unit_code, f"code:{unit_code}"),
            "layers": [{"name": layer.dxf.name, "color": layer.dxf.color, "on": layer.is_on(),
                        "frozen": layer.is_frozen(), "locked": layer.is_locked()} for layer in doc.layers],
            "layouts": [lay.name for lay in doc.layouts],
            "blocks": sorted(b.name for b in doc.blocks if not b.name.startswith("*")),
            "dimstyles": [d.dxf.name for d in doc.dimstyles],
            "modelspace_counts": counts, "modelspace_total": sum(counts.values()), "extents": extents}


def query(doc: Drawing, *, type: str | None = None, layer: str | None = None, block: str | None = None,
          layout: str | None = None, limit: int = 50, offset: int = 0) -> dict[str, Any]:
    space = _space(doc, layout)
    wanted = type.upper() if type else None
    if wanted == "POLYLINE":
        wanted = "LWPOLYLINE"
    rows: list[Any] = []
    for e in space:
        if wanted and e.dxftype() != wanted:
            continue
        if layer and not fnmatchcase(e.dxf.get("layer", "0").upper(), layer.upper()):
            continue
        if block and (e.dxftype() != "INSERT" or not fnmatchcase(e.dxf.name.upper(), block.upper())):
            continue
        rows.append(e)
    total = len(rows)
    page = rows[offset: offset + limit]
    return {"entities": [entity_summary(e) for e in page],
            "page": {"total": total, "offset": offset, "limit": limit, "has_more": offset + limit < total}}


def get_entity(doc: Drawing, handle: str) -> Any:
    e = doc.entitydb.get(str(handle).upper())
    if e is None or not isinstance(e, DXFGraphic) or e.dxf.owner is None:
        raise EntityNotFoundError(f"Handle '{handle}' não encontrado no DXF.")
    return e


def read_attributes(doc: Drawing, block_filter: str | None = None, layer_filter: str | None = None,
                    limit: int = 2000) -> list[dict[str, Any]]:
    out = []
    for e in doc.modelspace().query("INSERT"):
        if block_filter and not fnmatchcase(e.dxf.name.upper(), block_filter.upper()):
            continue
        if layer_filter and not fnmatchcase(e.dxf.layer.upper(), layer_filter.upper()):
            continue
        out.append({"handle": e.dxf.handle, "block": e.dxf.name, "layer": e.dxf.layer,
                    "insert": list(e.dxf.insert.xyz), "attributes": {a.dxf.tag: a.dxf.text for a in e.attribs}})
        if len(out) >= limit:
            raise InvalidParameterError(f"Mais de {limit} blocos; restrinja block_filter/layer_filter.")
    return out


# --------------------------------------------------------------------------- edição

def modify(doc: Drawing, handles: list[str], *, layer: str | None = None, color: int | None = None,
           translate: list[float] | None = None, rotate_deg: float | None = None,
           rotate_center: list[float] | None = None, scale: float | None = None,
           attributes: dict[str, str] | None = None) -> dict[str, Any]:
    from ezdxf.math import Matrix44

    if not handles:
        raise InvalidParameterError("Informe ao menos um handle.")
    if layer:
        ensure_layer(doc, layer)
    m = Matrix44()
    if scale is not None:
        if scale <= 0:
            raise InvalidParameterError("scale deve ser positivo.")
        m = m @ Matrix44.scale(scale, scale, scale)
    if rotate_deg is not None:
        cx, cy, _cz = _pt(rotate_center or [0, 0, 0], "rotate_center")
        m = m @ Matrix44.translate(-cx, -cy, 0) @ Matrix44.z_rotate(math.radians(rotate_deg)) @ Matrix44.translate(cx, cy, 0)
    if translate:
        tx, ty, tz = _pt(translate, "translate")
        m = m @ Matrix44.translate(tx, ty, tz)
    transform = scale is not None or rotate_deg is not None or bool(translate)
    changed = 0
    for h in handles:
        e = get_entity(doc, h)
        if layer:
            e.dxf.layer = layer
        if color is not None:
            e.dxf.color = int(color)
        if transform:
            e.transform(m)
        if attributes and e.dxftype() == "INSERT":
            by_tag = {a.dxf.tag.upper(): a for a in e.attribs}
            for k, v in attributes.items():
                if k.upper() not in by_tag:
                    raise InvalidParameterError(f"Atributo '{k}' não existe no bloco {e.dxf.name} (handle {h}).")
                by_tag[k.upper()].dxf.text = str(v)
        changed += 1
    return {"modified": changed}


def delete_entities(doc: Drawing, handles: list[str]) -> int:
    n = 0
    for h in handles:
        e = get_entity(doc, h)
        layout = e.get_layout()
        if layout is not None:
            layout.delete_entity(e)
        else:
            e.destroy()
        n += 1
    return n


# --------------------------------------------------------------------------- cotas

_DIM_KINDS = {"linear", "aligned", "radius", "diameter", "angular"}


def add_dimension(doc: Drawing, space, spec: dict[str, Any]) -> Any:
    kind = str(spec.get("kind", "")).lower()
    if kind not in _DIM_KINDS:
        raise InvalidParameterError(f"kind deve ser um de {sorted(_DIM_KINDS)}.")
    style = str(spec.get("dimstyle", "EZDXF"))
    if style not in doc.dimstyles:
        raise InvalidParameterError(f"Estilo de cota '{style}' não existe; use dxf_info para listar dimstyles.")
    override: dict[str, Any] = {"dimtxt": 2.5, "dimasz": 2.5, "dimexe": 1.25, "dimexo": 0.625, "dimgap": 0.625,
                                "dimdec": 0, "dimlfac": 1.0}
    if spec.get("lfac") is not None:  # fator linear: o texto da cota mostra distância * lfac (ex.: 25 num desenho em 1:25)
        override["dimlfac"] = _num(spec, "lfac", positive=True)
    if spec.get("dimscale") is not None:
        override["dimscale"] = _num(spec, "dimscale", positive=True)
    if spec.get("text_height") is not None:
        override["dimtxt"] = _num(spec, "text_height", positive=True)
    if spec.get("arrow_size") is not None:
        override["dimasz"] = _num(spec, "arrow_size", positive=True)
    if spec.get("decimals") is not None:
        override["dimdec"] = int(spec["decimals"])
    if spec.get("text") is not None:
        text = str(spec["text"])
    else:
        text = None
    attrs = _common(spec, doc)
    layer_attr = {"layer": attrs["layer"]} if "layer" in attrs else None
    kw: dict[str, Any] = {"dimstyle": style, "override": override or None, "text": text if text else "<>"}
    if layer_attr:
        kw["dxfattribs"] = layer_attr
    if kind == "linear":
        dim = space.add_linear_dim(base=_pt(spec.get("base"), "base", dims=2), p1=_pt(spec.get("p1"), "p1", dims=2),
                                   p2=_pt(spec.get("p2"), "p2", dims=2), angle=_num(spec, "angle", default=0.0), **kw)
    elif kind == "aligned":
        dim = space.add_aligned_dim(p1=_pt(spec.get("p1"), "p1", dims=2), p2=_pt(spec.get("p2"), "p2", dims=2),
                                    distance=_num(spec, "offset", default=5.0), **kw)
    elif kind == "radius":
        dim = space.add_radius_dim(center=_pt(spec.get("center"), "center", dims=2), radius=_num(spec, "radius", positive=True),
                                   angle=_num(spec, "angle", default=45.0), **kw)
    elif kind == "diameter":
        dim = space.add_diameter_dim(center=_pt(spec.get("center"), "center", dims=2), radius=_num(spec, "radius", positive=True),
                                     angle=_num(spec, "angle", default=45.0), **kw)
    else:  # angular: duas retas [[p1,p2],[p3,p4]] + ponto de base do arco
        l1, l2 = spec.get("line1"), spec.get("line2")
        if not (isinstance(l1, list) and len(l1) == 2 and isinstance(l2, list) and len(l2) == 2):
            raise InvalidParameterError("angular exige line1=[[x,y],[x,y]] e line2=[[x,y],[x,y]] e base=[x,y].")
        dim = space.add_angular_dim_2l(base=_pt(spec.get("base"), "base", dims=2),
                                       line1=(_pt(l1[0], "line1", dims=2), _pt(l1[1], "line1", dims=2)),
                                       line2=(_pt(l2[0], "line2", dims=2), _pt(l2[1], "line2", dims=2)), **kw)
    dim.render()
    return dim.dimension


# --------------------------------------------------------------------------- layouts / exportação

def create_layout(doc: Drawing, name: str, paper: str = "A3", landscape: bool = True, margins_mm: float = 10.0,
                  viewports: list[dict] | None = None) -> dict[str, Any]:
    if not name or name.lower() in {"model", "modelspace"} or name in [layout.name for layout in doc.layouts]:
        raise InvalidParameterError(f"Nome de layout inválido ou já existente: '{name}'.")
    paper = paper.upper()
    if paper not in PAPERS_MM:
        raise InvalidParameterError(f"paper deve ser um de {sorted(PAPERS_MM)}.")
    w, h = PAPERS_MM[paper]
    if not landscape:
        w, h = h, w
    lay = doc.layouts.new(name)
    lay.page_setup(size=(w, h), margins=(margins_mm,) * 4, units="mm")
    made = []
    for n, v in enumerate(viewports or []):
        cx, cy = _pt(v.get("center"), "viewport.center", dims=2)
        vw, vh = _num(v, "width", positive=True), _num(v, "height", positive=True)
        view_center = _pt(v.get("view_center"), "viewport.view_center", dims=2)
        scale = _num(v, "scale", positive=True, default=1.0)  # papel/modelo: 0.01 = 1:100
        vp = lay.add_viewport(center=(cx, cy), size=(vw, vh), view_center_point=view_center, view_height=vh / scale)
        vp.dxf.status = n + 2  # status 1 = viewport "ativa" do papel: o renderizador a ignora; use >= 2
        if v.get("frame", True):
            ensure_layer(doc, "VIEWPORT_FRAME", 8)
            lay.add_lwpolyline([(cx - vw / 2, cy - vh / 2), (cx + vw / 2, cy - vh / 2), (cx + vw / 2, cy + vh / 2),
                                (cx - vw / 2, cy + vh / 2)], close=True, dxfattribs={"layer": "VIEWPORT_FRAME"})
        made.append({"handle": vp.dxf.handle, "scale": scale})
    return {"layout": name, "paper": paper, "size_mm": [w, h], "viewports": made}


def export_render(doc: Drawing, out: Path, *, layout: str | None = None, fmt: str | None = None,
                  dpi: int = 150, background: str = "white",
                  size_in: tuple[float, float] | None = None) -> dict[str, Any]:
    """Renderiza modelspace/layout para PDF, PNG ou SVG com o backend matplotlib do ezdxf (sem AutoCAD)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.config import BackgroundPolicy, ColorPolicy, Configuration
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

    fmt = (fmt or out.suffix.lstrip(".")).lower()
    if fmt not in {"pdf", "png", "svg"}:
        raise InvalidParameterError("Formato de saída deve ser pdf, png ou svg.")
    if not 30 <= dpi <= 600:
        raise InvalidParameterError("dpi deve estar entre 30 e 600.")
    space = _space(doc, layout)
    page_in = (11.69, 8.27)
    if size_in is not None:
        page_in = (float(size_in[0]), float(size_in[1]))
    elif layout and layout.lower() not in {"model", "modelspace"}:
        w_mm, h_mm = space.dxf.paper_width, space.dxf.paper_height
        if w_mm and h_mm:
            page_in = (float(w_mm) / 25.4, float(h_mm) / 25.4)
    fig = plt.figure(figsize=page_in, dpi=dpi)
    try:
        ax = fig.add_axes([0, 0, 1, 1])
        cfg = Configuration(background_policy=BackgroundPolicy.WHITE if background == "white" else BackgroundPolicy.DEFAULT,
                            color_policy=ColorPolicy.BLACK if background == "white" else ColorPolicy.COLOR)
        Frontend(RenderContext(doc), MatplotlibBackend(ax), config=cfg).draw_layout(space, finalize=True)
        fig.set_size_inches(*page_in)  # o backend do ezdxf pode redimensionar a figura ao finalizar
        fig.savefig(str(out), dpi=dpi, format=fmt, facecolor="white" if background == "white" else None)
    finally:
        plt.close(fig)
    return {"path": str(out), "format": fmt, "layout": layout or "Model", "bytes": out.stat().st_size,
            "page_inches": [round(page_in[0], 2), round(page_in[1], 2)]}


# --------------------------------------------------------------------------- SQL somente leitura

_FORBIDDEN_SQL = re.compile(r"\b(attach|detach|pragma|insert|update|delete|drop|create|alter|replace|vacuum)\b", re.I)


def build_index(doc: Drawing) -> sqlite3.Connection:
    """Índice SQLite em memória: tabelas entities(handle,type,layer,color,block,x,y,z,text,length,radius)
    e attributes(handle,block,tag,value)."""
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE entities(handle TEXT PRIMARY KEY, type TEXT, layer TEXT, color INT, block TEXT,"
               " x REAL, y REAL, z REAL, text TEXT, length REAL, radius REAL)")
    db.execute("CREATE TABLE attributes(handle TEXT, block TEXT, tag TEXT, value TEXT)")
    for e in doc.modelspace():
        row = entity_summary(e, detail=True)
        g = row.get("geometry") or {}
        loc = g.get("insert") or g.get("center") or g.get("start") or g.get("location") or [None, None, None]
        loc = list(loc) + [None] * (3 - len(loc))
        db.execute("INSERT INTO entities VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                   (row["handle"], row["type"], row["layer"], row["color"], g.get("block"), loc[0], loc[1], loc[2],
                    g.get("text"), g.get("length"), g.get("radius")))
        for tag, val in (row.get("attributes") or {}).items():
            db.execute("INSERT INTO attributes VALUES (?,?,?,?)", (row["handle"], g.get("block"), tag, val))
    db.commit()
    return db


def sql_query(doc: Drawing, sql: str, limit: int = 200) -> dict[str, Any]:
    stmt = sql.strip().rstrip(";")
    if not stmt.lower().startswith("select") or ";" in stmt or _FORBIDDEN_SQL.search(stmt):
        raise InvalidParameterError("Apenas uma instrução SELECT é permitida (tabelas: entities, attributes).")
    db = build_index(doc)
    db.set_authorizer(lambda action, a, b, c, d: sqlite3.SQLITE_OK if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION) else sqlite3.SQLITE_DENY)
    try:
        cur = db.execute(f"SELECT * FROM ({stmt}) LIMIT {int(limit) + 1}")
        cols = [c[0] for c in cur.description]
        rows = cur.fetchall()
    except sqlite3.Error as exc:
        raise InvalidParameterError(f"SQL inválido: {exc}") from exc
    finally:
        db.close()
    truncated = len(rows) > limit
    return {"columns": cols, "rows": [list(r) for r in rows[:limit]], "truncated": truncated}


# --------------------------------------------------------------------------- símbolos de suporte (pictogramas)

_R = 50.0  # raio do tubo no símbolo base (unidades do desenho; escale na inserção)
SUPPORT_SYMBOLS: dict[str, list[dict[str, Any]]] = {
    "GUIA": [{"type": "circle", "center": [0, 0], "radius": _R},
             {"type": "line", "start": [-1.6 * _R, -_R], "end": [-1.6 * _R, _R]},
             {"type": "line", "start": [1.6 * _R, -_R], "end": [1.6 * _R, _R]}],
    "ANCORA": [{"type": "circle", "center": [0, 0], "radius": _R},
               {"type": "polyline", "points": [[-1.5 * _R, -2 * _R], [1.5 * _R, -2 * _R], [0, -_R]], "closed": True},
               {"type": "line", "start": [-1.5 * _R, -2 * _R], "end": [1.5 * _R, -1 * _R]},
               {"type": "line", "start": [1.5 * _R, -2 * _R], "end": [-1.5 * _R, -1 * _R]}],
    "APOIO": [{"type": "circle", "center": [0, 0], "radius": _R},
              {"type": "line", "start": [-1.5 * _R, -_R], "end": [1.5 * _R, -_R]},
              {"type": "line", "start": [-1.5 * _R, -_R], "end": [-1.2 * _R, -1.4 * _R]},
              {"type": "line", "start": [0, -_R], "end": [0.3 * _R, -1.4 * _R]},
              {"type": "line", "start": [1.5 * _R, -_R], "end": [1.8 * _R, -1.4 * _R]}],
    "MOLA": [{"type": "circle", "center": [0, 0], "radius": _R},
             {"type": "polyline", "points": [[0, -_R], [0.6 * _R, -1.25 * _R], [-0.6 * _R, -1.75 * _R],
                                              [0.6 * _R, -2.25 * _R], [0, -2.5 * _R]]}],
}


def insert_support_symbol(doc: Drawing, kind: str, insert: tuple[float, ...], tag: str | None = None,
                          line: str | None = None, size: float = 100.0, layer: str | None = None) -> dict[str, Any]:
    """Insere um pictograma de suporte (bloco SUP-<TIPO> com atributos TAG/TIPO/LINHA), definindo-o se faltar.

    Os desenhos são pictogramas simplificados para o cadastro; não representam uma norma de suportes.
    """
    kind = kind.upper()
    if kind not in SUPPORT_SYMBOLS:
        raise InvalidParameterError(f"kind deve ser um de {sorted(SUPPORT_SYMBOLS)}.")
    if not size > 0:
        raise InvalidParameterError("size deve ser positivo.")
    name = f"SUP-{kind}"
    if name not in doc.blocks:
        define_block(doc, name, SUPPORT_SYMBOLS[kind], ["TAG", "TIPO", "LINHA"])
    k = size / (2 * _R)
    spec = {"type": "insert", "block": name, "insert": list(insert), "xscale": k, "yscale": k, "zscale": k,
            "attributes": {"TAG": tag or "", "TIPO": kind, "LINHA": line or ""}}
    if layer:
        spec["layer"] = layer
    ref = add_entity(doc, doc.modelspace(), spec)
    return {"handle": ref.dxf.handle, "block": name}
