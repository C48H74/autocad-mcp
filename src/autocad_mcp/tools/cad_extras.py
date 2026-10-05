"""Ferramentas COM novas na v0.3: cotas nativas, plotagem em PDF e dados de projeto (XRecord)."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from autocad_mcp._com import VARIANT, com_error, pythoncom
from autocad_mcp.errors import InvalidParameterError
from autocad_mcp.geometry import normalize_point, to_variant_point
from autocad_mcp.paths import resolve_path
from autocad_mcp.session import Session, safe_get
from autocad_mcp.tools._base import com_tool

_DIM_KINDS = ("linear", "aligned", "radius", "diameter", "angular")
_DICT_NAME = "AUTOCAD_MCP"
_MAX_VALUE = 2000


def _pos(value: float, name: str) -> float:
    v = float(value)
    if not (v > 0 and math.isfinite(v)):
        raise InvalidParameterError(f"{name} deve ser um número > 0.")
    return v


@com_tool(coords=True)
def add_dimension(s: Session, kind: str, p1: list[float] | None = None, p2: list[float] | None = None,
                  location: list[float] | None = None, center: list[float] | None = None,
                  radius: float | None = None, angle_deg: float | None = None, vertex: list[float] | None = None,
                  layer: str | None = None) -> dict[str, Any]:
    """Cria uma cota nativa (entidade DIMENSION) no espaço modelo. Desfazível com um Ctrl+Z.

    QUANDO USAR: cotar distâncias entre suportes, diâmetros, raios e ângulos direto no desenho aberto.
    Parâmetros por tipo: linear (rotação por `angle_deg`: 0 = horizontal [padrão], 90 = vertical): p1, p2, location
    (ponto por onde passa a linha de cota); aligned: p1, p2, location (ponto do texto); radius e diameter: center, radius,
    angle_deg (direção do ponto na circunferência; padrão 45); angular: vertex, p1, p2, location (ponto do texto). layer opcional.
    Exemplo: add_dimension(kind="linear", p1=[0,0], p2=[1500,0], location=[750,-200], layer="COTAS")
    O estilo/tamanho vem do estilo de cota ativo do desenho (DIMSTYLE); a ferramenta não o altera.
    """
    kind = str(kind).lower()
    if kind not in _DIM_KINDS:
        raise InvalidParameterError(f"kind deve ser um de {list(_DIM_KINDS)}.")
    lay = s.ensure_layer(layer)

    def need(value: Any, name: str) -> tuple[float, float, float]:
        if value is None:
            raise InvalidParameterError(f"'{name}' é obrigatório para kind={kind}.")
        return normalize_point(value, name=name)

    with s.undo_mark():
        ms = s.model_space
        if kind == "linear":
            a, b, loc = need(p1, "p1"), need(p2, "p2"), need(location, "location")
            ent = ms.AddDimRotated(to_variant_point(a), to_variant_point(b), to_variant_point(loc), math.radians(float(angle_deg or 0.0)))
        elif kind == "aligned":
            ent = ms.AddDimAligned(to_variant_point(need(p1, "p1")), to_variant_point(need(p2, "p2")),
                                   to_variant_point(need(location, "location")))
        elif kind in ("radius", "diameter"):
            c = need(center, "center")
            if radius is None:
                raise InvalidParameterError("'radius' é obrigatório.")
            r = _pos(radius, "radius")
            ang = math.radians(45.0 if angle_deg is None else float(angle_deg))
            near = (c[0] + r * math.cos(ang), c[1] + r * math.sin(ang), c[2])
            far = (c[0] - r * math.cos(ang), c[1] - r * math.sin(ang), c[2])
            if kind == "radius":
                ent = ms.AddDimRadial(to_variant_point(c), to_variant_point(near), max(r * 0.5, 1.0))
            else:
                ent = ms.AddDimDiametric(to_variant_point(near), to_variant_point(far), max(r * 0.5, 1.0))
        else:
            ent = ms.AddDimAngular(to_variant_point(need(vertex, "vertex")), to_variant_point(need(p1, "p1")),
                                   to_variant_point(need(p2, "p2")), to_variant_point(need(location, "location")))
        if lay:
            ent.Layer = lay
        return {"handle": str(ent.Handle), "type": "DIMENSION", "kind": kind,
                "measurement": safe_get(ent, "Measurement", default=None),
                "text": str(safe_get(ent, "TextOverride", default="") or ""), "layer": str(safe_get(ent, "Layer", default=""))}


@com_tool(mutates=True, needs_doc=True)
def plot_to_pdf(s: Session, path: str, layout: str | None = None, plot_extents: bool = True,
                overwrite: bool = False) -> dict[str, Any]:
    """Plota o desenho aberto para PDF usando a impressora "DWG To PDF.pc3" do próprio AutoCAD (plotter real).

    QUANDO USAR: gerar o PDF de entrega com a mesma fidelidade do comando PLOT; para PDF sem AutoCAD use dxf_export.
    Parâmetros: path (.pdf, dentro das pastas permitidas); layout (nome; omita para o layout ativo; "Model" = modelo);
    plot_extents (true = enquadra a extensão; false = usa a configuração salva do layout); overwrite (padrão false).
    Exemplo: plot_to_pdf(path="C:/Users/eu/autocad-mcp-workspace/S12.pdf", layout="Folha1", overwrite=true)
    Efeitos: desliga BACKGROUNDPLOT durante a plotagem (restaura depois) e pode mudar a configuração de plotagem do layout.
    """
    out = resolve_path(path, s.cfg, write=True, suffixes=(".pdf",), must_exist=False)
    if out.exists() and not overwrite:
        raise InvalidParameterError(f"'{out.name}' já existe; use overwrite=true.")
    doc = s.doc
    previous_layout = None
    previous_bg = None
    try:
        if layout:
            try:
                target = doc.Layouts.Item(layout)
            except com_error as exc:
                raise InvalidParameterError(f"Layout '{layout}' não existe no desenho.") from exc
            previous_layout = doc.ActiveLayout
            doc.ActiveLayout = target
        lay = doc.ActiveLayout
        previous_bg = doc.GetVariable("BACKGROUNDPLOT")
        doc.SetVariable("BACKGROUNDPLOT", 0)
        lay.ConfigName = "DWG To PDF.pc3"
        if plot_extents:
            lay.PlotType = 1  # acExtents
            lay.StandardScale = 0  # acScaleToFit
            lay.CenterPlot = True
        ok = bool(doc.Plot.PlotToFile(str(out)))
    finally:
        if previous_bg is not None:
            try:
                doc.SetVariable("BACKGROUNDPLOT", previous_bg)
            except com_error:
                s.warn("Não consegui restaurar BACKGROUNDPLOT.")
        if previous_layout is not None:
            try:
                doc.ActiveLayout = previous_layout
            except com_error:
                s.warn("Não consegui restaurar o layout ativo.")
    if not ok or not out.is_file():
        raise InvalidParameterError("O AutoCAD não gerou o PDF (verifique a impressora 'DWG To PDF.pc3' e o layout).")
    return {"path": str(out), "bytes": out.stat().st_size, "layout": layout or str(safe_get(doc, "ActiveLayout", default="")) or None}


def _project_dict(s: Session, create: bool) -> Any:
    dicts = s.doc.Dictionaries
    try:
        return dicts.Item(_DICT_NAME)
    except com_error:
        if not create:
            return None
        return dicts.Add(_DICT_NAME)


@com_tool(mutates=True)
def project_data_set(s: Session, key: str, value: str) -> dict[str, Any]:
    """Guarda um texto de projeto DENTRO do DWG (dicionário XRecord "AUTOCAD_MCP"), preservado ao salvar/abrir.

    QUANDO USAR: registrar metadados do projeto no próprio desenho (revisão, nº do documento, norma, responsável).
    Parâmetros: key (até 64 caracteres; sem espaços nas pontas), value (texto até 2000 caracteres).
    Exemplo: project_data_set(key="REV", value="B - 2026-10-05")
    """
    key, value = str(key).strip(), str(value)
    if not key or len(key) > 64:
        raise InvalidParameterError("key deve ter de 1 a 64 caracteres.")
    if len(value) > _MAX_VALUE:
        raise InvalidParameterError(f"value excede {_MAX_VALUE} caracteres.")
    with s.undo_mark():
        d = _project_dict(s, True)
        try:
            d.Remove(key)
        except com_error:
            pass
        xr = d.AddXRecord(key)
        types = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_I2, [1])
        data = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_VARIANT, [value])
        xr.SetXRecordData(types, data)
    return {"key": key, "stored": True}


@com_tool(mutates=False)
def project_data_get(s: Session, key: str | None = None) -> dict[str, Any]:
    """Lê dados de projeto gravados no DWG por project_data_set (uma chave ou todas).

    QUANDO USAR: recuperar metadados do projeto guardados no desenho.
    Parâmetros: key (omita para listar todas as chaves).
    Exemplo: project_data_get(key="REV")
    """
    d = _project_dict(s, False)
    if d is None:
        return {"values": {}}
    names = [key] if key else [str(d.Item(i).Name) for i in range(int(d.Count))]
    out: dict[str, str | None] = {}
    for name in names:
        try:
            xr = d.Item(name)
        except com_error:
            out[name] = None
            continue
        # Medido no Plant 3D 2021: chamar SEM argumentos devolve ((tipos...), (dados...)); VARIANT byref volta vazio.
        _types, raw = xr.GetXRecordData()
        out[name] = str(raw[0]) if raw else ""
    return {"values": out}


TOOLS = [add_dimension, plot_to_pdf, project_data_set, project_data_get]
