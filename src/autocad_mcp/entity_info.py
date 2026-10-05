"""Descrição de entidades (resumo e detalhe) — usado por consulta, blocos e desenho."""

from __future__ import annotations

from typing import Any

from autocad_mcp._com import com_error
from autocad_mcp.geometry import from_com_point, rad_to_deg
from autocad_mcp.session import Session, safe_get

#: ObjectName (COM) → nome DXF (código de grupo 0 usado nos filtros de seleção)
DXF_NAMES: dict[str, str] = {
    "AcDbLine": "LINE", "AcDbCircle": "CIRCLE", "AcDbArc": "ARC", "AcDbEllipse": "ELLIPSE",
    "AcDbPolyline": "LWPOLYLINE", "AcDb2dPolyline": "POLYLINE", "AcDb3dPolyline": "POLYLINE",
    "AcDbSpline": "SPLINE", "AcDbText": "TEXT", "AcDbMText": "MTEXT", "AcDbPoint": "POINT",
    "AcDbBlockReference": "INSERT", "AcDbMInsertBlock": "INSERT", "AcDbAttributeDefinition": "ATTDEF",
    "AcDbHatch": "HATCH", "AcDbSolid": "SOLID", "AcDbMLeader": "MULTILEADER", "AcDbLeader": "LEADER",
    "AcDbRasterImage": "IMAGE", "AcDbViewport": "VIEWPORT", "AcDbRay": "RAY", "AcDbXline": "XLINE",
    "AcDbFace": "3DFACE", "AcDbRegion": "REGION", "AcDb3dSolid": "3DSOLID", "AcDbTable": "ACAD_TABLE",
    "AcDbWipeout": "WIPEOUT", "AcDbOle2Frame": "OLE2FRAME",
}
#: apelidos amigáveis aceitos em query_entities(type=...)
TYPE_ALIASES = {"BLOCK": "INSERT", "BLOCKREF": "INSERT", "POLYLINE": "LWPOLYLINE,POLYLINE", "PLINE": "LWPOLYLINE,POLYLINE"}


def dxf_type(object_name: str) -> str:
    if object_name in DXF_NAMES:
        return DXF_NAMES[object_name]
    if object_name.startswith("AcDb") and "Dimension" in object_name:
        return "DIMENSION"
    return object_name[4:].upper() if object_name.startswith("AcDb") else object_name.upper()


def block_name(ent: Any) -> str:
    """Nome efetivo do bloco (blocos dinâmicos têm `Name` anônimo tipo *U12)."""
    return str(safe_get(ent, "EffectiveName", "Name", default=""))


def _pt(value: Any) -> list[float] | None:
    try:
        return from_com_point(value)
    except (TypeError, ValueError):
        return None


def _bbox(ent: Any) -> dict[str, list[float]] | None:
    try:
        lo, hi = ent.GetBoundingBox()
        return {"min": from_com_point(lo), "max": from_com_point(hi)}
    except (com_error, TypeError, ValueError, AttributeError):
        return None


def attributes_of(ent: Any) -> dict[str, str]:
    """{TAG: valor} de uma referência de bloco (atributos constantes não aparecem via COM GetAttributes)."""
    out: dict[str, str] = {}
    if not bool(safe_get(ent, "HasAttributes", default=False)):
        return out
    for att in ent.GetAttributes():
        out[str(att.TagString).upper()] = str(att.TextString)
    return out


def describe(s: Session, ent: Any, *, detail: bool = False) -> dict[str, Any]:
    """Resumo (padrão) ou propriedades completas (detail=True) da entidade."""
    obj = str(safe_get(ent, "ObjectName", default=""))
    kind = dxf_type(obj)
    info: dict[str, Any] = {"handle": str(ent.Handle), "type": kind, "layer": str(safe_get(ent, "Layer", default=""))}
    geo: dict[str, Any] = {}

    if kind == "LINE":
        geo = {"start": _pt(ent.StartPoint), "end": _pt(ent.EndPoint), "length": round(float(ent.Length), 6)}
    elif kind == "CIRCLE":
        geo = {"center": _pt(ent.Center), "radius": round(float(ent.Radius), 6)}
    elif kind == "ARC":
        geo = {"center": _pt(ent.Center), "radius": round(float(ent.Radius), 6),
               "start_angle_deg": rad_to_deg(ent.StartAngle), "end_angle_deg": rad_to_deg(ent.EndAngle)}
    elif kind in ("LWPOLYLINE", "POLYLINE"):
        coords = [float(c) for c in ent.Coordinates]
        n = 3 if obj == "AcDb3dPolyline" else 2
        verts = [[round(c, 6) for c in coords[i:i + n]] for i in range(0, len(coords), n)]
        geo = {"vertex_count": len(verts), "closed": bool(safe_get(ent, "Closed", default=False)),
               "length": round(float(safe_get(ent, "Length", default=0.0)), 6)}
        if n == 2:
            geo["elevation"] = round(float(safe_get(ent, "Elevation", default=0.0)), 6)
        if detail or len(verts) <= 8:
            geo["vertices"] = verts
    elif kind in ("TEXT", "MTEXT"):
        geo = {"text": str(ent.TextString), "position": _pt(ent.InsertionPoint),
               "height": round(float(safe_get(ent, "Height", default=0.0)), 6)}
    elif kind == "INSERT":
        geo = {"block": block_name(ent), "position": _pt(ent.InsertionPoint),
               "rotation_deg": rad_to_deg(safe_get(ent, "Rotation", default=0.0)),
               "scale": [round(float(safe_get(ent, a, default=1.0)), 6)
                         for a in ("XScaleFactor", "YScaleFactor", "ZScaleFactor")],
               "has_attributes": bool(safe_get(ent, "HasAttributes", default=False))}
        if detail:
            geo["attributes"] = attributes_of(ent)
    else:
        box = _bbox(ent)
        if box:
            geo = {"bbox": box}
    info["geometry"] = geo

    if detail:
        info.update({
            "object_name": obj,
            "object_id": safe_get(ent, "ObjectID", default=None),
            "color": safe_get(ent, "Color", default=None),
            "linetype": safe_get(ent, "Linetype", default=None),
            "lineweight": safe_get(ent, "Lineweight", default=None),
            "visible": bool(safe_get(ent, "Visible", default=True)),
        })
        if "bbox" not in geo:
            box = _bbox(ent)
            if box:
                info["bbox"] = box
        if kind == "LINE":
            geo["angle_deg"] = rad_to_deg(ent.Angle)
        if kind == "CIRCLE":
            geo["area"] = round(float(ent.Area), 6)
            geo["circumference"] = round(float(ent.Circumference), 6)
    return info
