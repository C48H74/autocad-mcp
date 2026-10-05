"""AutoCAD FALSO para testes: simula o subconjunto do modelo de objetos ActiveX que o servidor usa.

Não substitui o AutoCAD real (ver tests/test_integration.py, marcado @pytest.mark.autocad); serve para
provar a LÓGICA das ferramentas: filtros DXF, paginação, dry_run/confirm, undo em grupo, Excel etc.
Fidelidade deliberada a quirks reais: propriedade de camada em minúsculas (`color`), erros com
HRESULT, SelectionSet com nome único, Copy() opcionalmente sem retorno, filtros DXF com curingas.
"""

from __future__ import annotations

import math
import re
from typing import Any

from autocad_mcp._com import VARIANT, com_error


def busy() -> com_error:
    return com_error(-2147418111, "Call was rejected by callee.", None, None)


def disconnected() -> com_error:
    return com_error(-2147417848, "The object invoked has disconnected from its clients.", None, None)


def fail(msg: str) -> com_error:
    return com_error(-2147352567, "Exception occurred.", (0, "AutoCAD", msg, None, 0, 0), None)


def _p3(v: Any) -> tuple[float, float, float]:
    raw = v.value if isinstance(v, VARIANT) else v
    t = tuple(float(x) for x in raw)
    return t if len(t) == 3 else (t + (0.0,))[:3]


def _dxf_regex(pattern: str) -> re.Pattern[str]:
    out, i = [], 0
    while i < len(pattern):
        c = pattern[i]
        if c == "`" and i + 1 < len(pattern):
            out.append(re.escape(pattern[i + 1]))
            i += 2
            continue
        out.append(".*" if c == "*" else "." if c == "?" else re.escape(c))
        i += 1
    return re.compile("^" + "".join(out) + "$", re.IGNORECASE)


DXF_NAME = {
    "AcDbLine": "LINE", "AcDbCircle": "CIRCLE", "AcDbArc": "ARC", "AcDbPolyline": "LWPOLYLINE",
    "AcDb3dPolyline": "POLYLINE", "AcDbText": "TEXT", "AcDbMText": "MTEXT",
    "AcDbBlockReference": "INSERT", "AcDbAttributeDefinition": "ATTDEF",
}


class FakeCom:
    _is_com_ = True


class Journal:
    """Histórico de undo: uma marca agrupa tudo até EndUndoMark em UM passo (como Ctrl+Z)."""

    def __init__(self) -> None:
        self.groups: list[list[Any]] = []
        self.open: list[Any] | None = None

    def record(self, undo_fn: Any) -> None:
        if self.open is not None:
            self.open.append(undo_fn)
        else:
            self.groups.append([undo_fn])

    def start(self) -> None:
        if self.open is not None:
            raise fail("StartUndoMark: já existe uma marca aberta")
        self.open = []

    def end(self) -> None:
        if self.open is not None:
            if self.open:
                self.groups.append(self.open)
            self.open = None

    def undo(self) -> bool:
        if not self.groups:
            return False
        for fn in reversed(self.groups.pop()):
            fn()
        return True


class FakeEntity(FakeCom):
    ObjectName = "AcDbEntity"

    def __init__(self, doc: FakeDoc, layer: str = "0") -> None:
        self._doc = doc
        self.Handle = doc._next_handle()
        self._layer = layer
        self.Color = 256
        self.Linetype = "ByLayer"
        self.Visible = True
        self._deleted = False

    @property
    def Layer(self) -> str:
        return self._layer

    @Layer.setter
    def Layer(self, value: str) -> None:
        if value.casefold() not in {n.casefold() for n in self._doc.Layers.names()}:
            raise fail(f"Camada inexistente: {value}")
        old, self._layer = self._layer, value
        self._doc.journal.record(lambda: setattr(self, "_layer", old))

    @property
    def dxf(self) -> str:
        return DXF_NAME.get(self.ObjectName, self.ObjectName)

    def points(self) -> list[tuple[float, float, float]]:
        return []

    def _shift(self, d: tuple[float, float, float]) -> None:  # pragma: no cover
        raise NotImplementedError

    def Move(self, p1: Any, p2: Any) -> None:
        a, b = _p3(p1), _p3(p2)
        d = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
        self._shift(d)
        self._doc.journal.record(lambda: self._shift((-d[0], -d[1], -d[2])))

    def Copy(self) -> Any:
        new = self._clone()
        self._doc.model._add(new)
        return None if self._doc.copy_returns_none else new

    def _clone(self) -> FakeEntity:  # pragma: no cover
        raise NotImplementedError

    def Delete(self) -> None:
        self._doc.model._remove(self)

    def GetBoundingBox(self) -> tuple[tuple[float, ...], tuple[float, ...]]:
        pts = self.points() or [(0.0, 0.0, 0.0)]
        return (tuple(min(p[i] for p in pts) for i in range(3)), tuple(max(p[i] for p in pts) for i in range(3)))


class FakeDimension(FakeEntity):
    ObjectName = "AcDbRotatedDimension"

    def __init__(self, doc, kind, measurement, layer="0"):
        super().__init__(doc, layer)
        self.kind, self.Measurement, self.TextOverride = kind, measurement, ""

    def points(self):
        return [(0.0, 0.0, 0.0)]


class FakeXRecord(FakeCom):
    def __init__(self):
        self.data = None

    def SetXRecordData(self, types, data):
        self.data = list(data.value if hasattr(data, "value") else data)

    def GetXRecordData(self):
        return ((1,) * len(self.data or ()), tuple(self.data or ()))


class FakeDictionary(FakeCom):
    def __init__(self):
        self._d = {}

    @property
    def Count(self): return len(self._d)

    def Item(self, k):
        if isinstance(k, int):
            k = list(self._d)[k]
        if k not in self._d:
            raise fail("Chave inexistente")
        rec = self._d[k]
        rec.Name = k
        return rec

    def AddXRecord(self, k):
        self._d[k] = FakeXRecord()
        return self._d[k]

    def Remove(self, k):
        if k not in self._d:
            raise fail("Chave inexistente")
        del self._d[k]


class FakeDictionaries(FakeCom):
    def __init__(self):
        self._d = {}

    def Item(self, k):
        if k not in self._d:
            raise fail("Dicionário inexistente")
        return self._d[k]

    def Add(self, k):
        self._d[k] = FakeDictionary()
        return self._d[k]


class FakePlot(FakeCom):
    def __init__(self, doc):
        self._doc = doc
        self.plotted = []

    def PlotToFile(self, path, cfg=None):
        import pathlib
        pathlib.Path(path).write_bytes(b"%PDF-fake")
        self.plotted.append(path)
        return True


class FakeLayout(FakeCom):
    def __init__(self, name):
        self.Name = name
        self.ConfigName = ""
        self.PlotType = 0
        self.StandardScale = 0
        self.CenterPlot = False


class FakeLayouts(FakeCom):
    def __init__(self):
        self._l = {"Model": FakeLayout("Model"), "Folha1": FakeLayout("Folha1")}

    def Item(self, n):
        if n not in self._l:
            raise fail("Layout inexistente")
        return self._l[n]


class FakeLine(FakeEntity):
    ObjectName = "AcDbLine"

    def __init__(self, doc, a, b, layer="0"):
        super().__init__(doc, layer)
        self.StartPoint, self.EndPoint = a, b

    @property
    def Length(self): return math.dist(self.StartPoint, self.EndPoint)
    @property
    def Angle(self): return math.atan2(self.EndPoint[1] - self.StartPoint[1], self.EndPoint[0] - self.StartPoint[0])
    def points(self): return [self.StartPoint, self.EndPoint]

    def _shift(self, d):
        self.StartPoint = tuple(a + b for a, b in zip(self.StartPoint, d))
        self.EndPoint = tuple(a + b for a, b in zip(self.EndPoint, d))

    def _clone(self): return FakeLine(self._doc, self.StartPoint, self.EndPoint, self._layer)


class FakeCircle(FakeEntity):
    ObjectName = "AcDbCircle"

    def __init__(self, doc, c, r, layer="0"):
        super().__init__(doc, layer)
        self.Center, self.Radius = c, r

    @property
    def Area(self): return math.pi * self.Radius**2
    @property
    def Circumference(self): return 2 * math.pi * self.Radius
    def points(self):
        c, r = self.Center, self.Radius
        return [(c[0] - r, c[1] - r, c[2]), (c[0] + r, c[1] + r, c[2])]

    def _shift(self, d): self.Center = tuple(a + b for a, b in zip(self.Center, d))
    def _clone(self): return FakeCircle(self._doc, self.Center, self.Radius, self._layer)


class FakePolyline(FakeEntity):
    """LWPolyline (Coordinates plano XY) ou Polyline 3D (Coordinates plano XYZ)."""

    def __init__(self, doc, coords, layer="0", is3d=False):
        super().__init__(doc, layer)
        self.ObjectName = "AcDb3dPolyline" if is3d else "AcDbPolyline"
        self.Coordinates = tuple(coords)
        self.Closed = False
        self.Elevation = 0.0
        self._n = 3 if is3d else 2

    def points(self):
        c, n = self.Coordinates, self._n
        return [tuple(c[i:i + n]) + ((self.Elevation,) if n == 2 else ()) for i in range(0, len(c), n)]

    @property
    def Length(self):
        p = self.points()
        L = sum(math.dist(a, b) for a, b in zip(p, p[1:]))
        return L + (math.dist(p[-1], p[0]) if self.Closed and len(p) > 2 else 0.0)

    def _shift(self, d):
        n = self._n
        self.Coordinates = tuple(v + d[i % n] for i, v in enumerate(self.Coordinates))
        if n == 2:
            self.Elevation += d[2]

    def _clone(self):
        c = FakePolyline(self._doc, self.Coordinates, self._layer, self._n == 3)
        c.Closed, c.Elevation = self.Closed, self.Elevation
        return c


class FakeText(FakeEntity):
    def __init__(self, doc, text, p, h, layer="0", mtext=False, width=0.0):
        super().__init__(doc, layer)
        self.ObjectName = "AcDbMText" if mtext else "AcDbText"
        self.TextString, self.InsertionPoint, self.Height, self.Width = text, p, h, width
        self.Rotation = 0.0

    def points(self): return [self.InsertionPoint]
    def _shift(self, d): self.InsertionPoint = tuple(a + b for a, b in zip(self.InsertionPoint, d))

    def _clone(self):
        return FakeText(self._doc, self.TextString, self.InsertionPoint, self.Height, self._layer,
                        self.ObjectName == "AcDbMText", self.Width)


class FakeAttribute(FakeCom):
    ObjectName = "AcDbAttribute"

    def __init__(self, doc, tag, text):
        self._doc = doc
        self.TagString = tag
        self._text = text

    @property
    def TextString(self) -> str: return self._text

    @TextString.setter
    def TextString(self, v: str) -> None:
        old, self._text = self._text, str(v)
        self._doc.journal.record(lambda: setattr(self, "_text", old))


class FakeAttDef(FakeCom):
    ObjectName = "AcDbAttributeDefinition"

    def __init__(self, tag, prompt="", default="", constant=False):
        self.TagString, self.PromptString, self.TextString, self.Constant = tag, prompt, default, constant
        self.Layer = "0"


class FakeBlockRef(FakeEntity):
    ObjectName = "AcDbBlockReference"

    def __init__(self, doc, name, p, scale=(1.0, 1.0, 1.0), rot=0.0, layer="0", attdefs=(), anonymous=False):
        super().__init__(doc, layer)
        self.EffectiveName = name
        self.Name = "*U%d" % (len(doc.model._items) + 1) if anonymous else name
        self._ip = p
        self.XScaleFactor, self.YScaleFactor, self.ZScaleFactor = scale
        self.Rotation = rot
        self._attrs = [FakeAttribute(doc, d.TagString.upper(), d.TextString) for d in attdefs if not d.Constant]

    @property
    def InsertionPoint(self): return self._ip

    @InsertionPoint.setter
    def InsertionPoint(self, v):
        old, self._ip = self._ip, _p3(v)
        self._doc.journal.record(lambda: setattr(self, "_ip", old))

    @property
    def HasAttributes(self): return bool(self._attrs)
    def GetAttributes(self): return tuple(self._attrs)
    def points(self): return [self._ip]

    def _shift(self, d): self._ip = tuple(a + b for a, b in zip(self._ip, d))

    def _clone(self):
        c = FakeBlockRef(self._doc, self.EffectiveName, self._ip, (self.XScaleFactor, self.YScaleFactor, self.ZScaleFactor),
                         self.Rotation, self._layer)
        c._attrs = [FakeAttribute(self._doc, a.TagString, a.TextString) for a in self._attrs]
        return c


class FakeLayer(FakeCom):
    _ALLOWED = {"Name", "color", "Linetype", "LayerOn", "Freeze", "Lock", "Plottable", "Description"}

    def __setattr__(self, name, value):
        # como um typelib real: propriedade inexistente (ex. 'Color' maiúsculo) NÃO pode ser definida
        if name not in self._ALLOWED:
            raise AttributeError(f"Property 'FakeLayer.{name}' can not be set.")
        object.__setattr__(self, name, value)

    def __init__(self, name):
        self.Name = name
        self.color = 7  # minúsculo de propósito (quirk do typelib)
        self.Linetype = "Continuous"
        self.LayerOn, self.Freeze, self.Lock, self.Plottable = True, False, False, True
        self.Description = ""


class FakeLayers(FakeCom):
    def __init__(self, doc):
        self._doc = doc
        self._items = [FakeLayer("0")]

    def names(self): return [x.Name for x in self._items]
    @property
    def Count(self): return len(self._items)

    def Item(self, k):
        if isinstance(k, int):
            return self._items[k]
        for x in self._items:
            if x.Name.casefold() == str(k).casefold():
                return x
        raise fail(f"Chave não encontrada: {k}")

    def Add(self, name):
        if name.casefold() in {n.casefold() for n in self.names()}:
            raise fail("Nome duplicado")
        layer = FakeLayer(name)
        self._items.append(layer)
        self._doc.journal.record(lambda: self._items.remove(layer))
        return layer


class FakeLinetypes(FakeCom):
    AVAILABLE = {"HIDDEN", "CENTER", "DASHED", "PHANTOM"}

    def __init__(self):
        self.loaded = {"Continuous", "ByLayer", "ByBlock"}

    def Item(self, name):
        for n in self.loaded:
            if n.casefold() == name.casefold():
                return FakeLayer(n)
        raise fail("Chave não encontrada")

    def Load(self, name, fname):
        if name.upper() not in self.AVAILABLE:
            raise fail("Tipo de linha não encontrado no arquivo")
        self.loaded.add(name.upper())


class FakeBlockDef(FakeCom):
    def __init__(self, name, attdefs=(), is_layout=False, is_xref=False):
        self.Name, self.IsLayout, self.IsXRef = name, is_layout, is_xref
        self._ents: list[Any] = list(attdefs)

    @property
    def Count(self): return len(self._ents)
    def Item(self, i): return self._ents[i]


class FakeBlocks(FakeCom):
    def __init__(self):
        self._items = [FakeBlockDef("*Model_Space", is_layout=True), FakeBlockDef("*Paper_Space", is_layout=True)]

    @property
    def Count(self): return len(self._items)

    def Item(self, k):
        if isinstance(k, int):
            return self._items[k]
        for b in self._items:
            if b.Name.casefold() == str(k).casefold():
                return b
        raise fail(f"Chave não encontrada: {k}")

    def define(self, name, tags=(), **kw):
        defs = [FakeAttDef(t, f"Informe {t}", d) for t, d in (tags.items() if isinstance(tags, dict) else ((t, "") for t in tags))]
        self._items.append(FakeBlockDef(name, defs, **kw))


class FakeModelSpace(FakeCom):
    def __init__(self, doc):
        self._doc = doc
        self._items: list[FakeEntity] = []

    @property
    def Count(self): return len(self._items)
    def Item(self, i): return self._items[i]

    def _add(self, ent):
        self._items.append(ent)
        ent._deleted = False
        self._doc.by_handle[ent.Handle] = ent
        self._doc.journal.record(lambda: self._remove(ent, journal=False))
        return ent

    def _remove(self, ent, journal=True):
        if ent in self._items:
            idx = self._items.index(ent)
            self._items.remove(ent)
            ent._deleted = True
            if journal:
                def restore():
                    self._items.insert(idx, ent)
                    ent._deleted = False
                self._doc.journal.record(restore)

    def AddLine(self, a, b): return self._add(FakeLine(self._doc, _p3(a), _p3(b), self._doc.ActiveLayer))
    def AddCircle(self, c, r): return self._add(FakeCircle(self._doc, _p3(c), float(r), self._doc.ActiveLayer))

    def AddLightWeightPolyline(self, v):
        raw = v.value if isinstance(v, VARIANT) else v
        return self._add(FakePolyline(self._doc, raw, self._doc.ActiveLayer))

    def Add3DPoly(self, v):
        raw = v.value if isinstance(v, VARIANT) else v
        return self._add(FakePolyline(self._doc, raw, self._doc.ActiveLayer, is3d=True))

    def AddText(self, text, p, h): return self._add(FakeText(self._doc, text, _p3(p), float(h), self._doc.ActiveLayer))

    def AddMText(self, p, w, text):
        return self._add(FakeText(self._doc, text, _p3(p), 0.0, self._doc.ActiveLayer, mtext=True, width=float(w)))

    def _dim(self, kind, measurement):
        return self._add(FakeDimension(self._doc, kind, measurement, self._doc.ActiveLayer))

    def AddDimRotated(self, a, b, loc, rot):
        a, b = _p3(a), _p3(b)
        import math as _m
        return self._dim("rotated", abs((b[0] - a[0]) * _m.cos(rot) + (b[1] - a[1]) * _m.sin(rot)))

    def AddDimAligned(self, a, b, loc):
        a, b = _p3(a), _p3(b)
        return self._dim("aligned", sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5)

    def AddDimRadial(self, c, chord, leader):
        c, chord = _p3(c), _p3(chord)
        return self._dim("radial", sum((x - y) ** 2 for x, y in zip(c, chord)) ** 0.5)

    def AddDimDiametric(self, a, b, leader):
        a, b = _p3(a), _p3(b)
        return self._dim("diametric", sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5)

    def AddDimAngular(self, vertex, a, b, text):
        return self._dim("angular", 0.7853981633974483)

    def InsertBlock(self, p, name, xs, ys, zs, rot):
        block = self._doc.Blocks.Item(name)
        defs = [e for e in block._ents if isinstance(e, FakeAttDef)]
        return self._add(FakeBlockRef(self._doc, block.Name, _p3(p), (xs, ys, zs), rot, self._doc.ActiveLayer, defs))


class FakeSelectionSet(FakeCom):
    def __init__(self, doc, name, owner):
        self._doc, self.Name, self._owner, self._items = doc, name, owner, []

    @property
    def Count(self): return len(self._items)
    def Item(self, i): return self._items[i]
    def Clear(self): self._items = []
    def Delete(self): self._owner._sets.pop(self.Name, None)

    def Select(self, Mode, Point1=None, Point2=None, FilterType=None, FilterData=None):
        if self._doc.reject_dxf_filters and FilterType is not None:
            raise fail("Filtro DXF não suportado")
        cands = [e for e in self._doc.model._items if not e._deleted]
        if Mode in (0, 1):
            a, b = _p3(Point1), _p3(Point2)
            lo, hi = tuple(map(min, a, b)), tuple(map(max, a, b))
            def inside(e):
                pts = e.points() or [(0, 0, 0)]
                ins = [all(lo[i] <= p[i] <= hi[i] for i in (0, 1)) for p in pts]
                return all(ins) if Mode == 0 else any(ins)
            cands = [e for e in cands if inside(e)]
        if FilterType is not None:
            codes = list(FilterType.value if isinstance(FilterType, VARIANT) else FilterType)
            vals = list(FilterData.value if isinstance(FilterData, VARIANT) else FilterData)
            for code, val in zip(codes, vals):
                if code == 0:
                    rxs = [_dxf_regex(t.strip()) for t in str(val).split(",")]
                    cands = [e for e in cands if any(r.match(e.dxf) for r in rxs)]
                elif code == 8:
                    rx = _dxf_regex(str(val))
                    cands = [e for e in cands if rx.match(e.Layer)]
                elif code == 2:
                    rx = _dxf_regex(str(val))
                    cands = [e for e in cands if isinstance(e, FakeBlockRef) and rx.match(e.Name)]
        self._items = cands


class FakeSelectionSets(FakeCom):
    def __init__(self, doc):
        self._doc, self._sets = doc, {}
        self.adds = 0  # quantos SelectionSets foram criados (no AutoCAD real cada um deixa um undo vazio)

    @property
    def Count(self): return len(self._sets)

    def Add(self, name):
        if name in self._sets:
            raise fail("Nome de conjunto de seleção duplicado")
        ss = FakeSelectionSet(self._doc, name, self)
        self.adds += 1
        self._sets[name] = ss
        return ss

    def Item(self, name):
        try:
            return self._sets[name]
        except KeyError:
            raise fail("Chave não encontrada") from None


class FakeDoc(FakeCom):
    def __init__(self, name="Drawing1.dwg", path=r"C:\proj", units=4):
        self.Name, self.Path = name, path
        self.FullName = f"{path}\\{name}" if path else name
        self.Saved, self.ReadOnly, self.ActiveSpace = True, False, 1
        self.ActiveLayer = "0"
        self.by_handle: dict[str, FakeEntity] = {}
        self._h = 0x100
        self.journal = Journal()
        self.vars = {"INSUNITS": units, "CMDACTIVE": 0, "CMDNAMES": ""}
        self.copy_returns_none = False
        self.reject_dxf_filters = False
        self.sent_commands: list[str] = []
        self.save_count = 0
        self.model = FakeModelSpace(self)
        self.Layers = FakeLayers(self)
        self.Linetypes = FakeLinetypes()
        self.Blocks = FakeBlocks()
        self.SelectionSets = FakeSelectionSets(self)
        self.Dictionaries = FakeDictionaries()
        self.Layouts = FakeLayouts()
        self.ActiveLayout = self.Layouts.Item("Model")
        self.Plot = FakePlot(self)
        self.vars["BACKGROUNDPLOT"] = 2
        self.app: FakeApp | None = None

    def _next_handle(self) -> str:
        self._h += 1
        return format(self._h, "X")

    @property
    def ModelSpace(self): return self.model
    def GetVariable(self, n): return self.vars[n.upper()]
    def SetVariable(self, n, v): self.vars[n.upper()] = v
    def StartUndoMark(self): self.journal.start()
    def EndUndoMark(self): self.journal.end()

    def HandleToObject(self, h):
        e = self.by_handle.get(str(h).upper())
        if e is None or e._deleted:
            raise fail("Handle inválido")
        return e

    def Save(self):
        if not self.Path:
            raise fail("Diálogo SALVARCOMO necessário")
        self.save_count += 1
        self.Saved = True

    def Activate(self):
        if self.app:
            self.app.active = self

    def SendCommand(self, text):
        self.sent_commands.append(text)
        if self.app:
            self.app.busy_polls = self.app.polls_after_send

    # helpers de teste
    def ctrl_z(self) -> bool:
        return self.journal.undo()

    def live(self) -> list[FakeEntity]:
        return list(self.model._items)


class _State(FakeCom):
    def __init__(self, app): self._app = app

    @property
    def IsQuiescent(self):
        app = self._app
        if app.busy_polls > 0:
            app.busy_polls -= 1
            return False
        return not app.command


class FakeDocs(FakeCom):
    def __init__(self, app): self._app = app
    @property
    def Count(self): return len(self._app.docs)
    def Item(self, i): return self._app.docs[i]


class FakeApp(FakeCom):
    def __init__(self, docs=None):
        self.docs = docs or [FakeDoc()]
        for d in self.docs:
            d.app = self
        self.active = self.docs[0]
        self.Version, self.Visible = "24.3s (LMS Tech)", True
        self._reject, self.dead = 0, False
        self.command = ""
        self.busy_polls = 0
        self.polls_after_send = 0
        self.zoomed = 0

    def reject_next(self, n: int) -> None:
        self._reject = n

    @property
    def Name(self):
        if self.dead:
            raise disconnected()
        if self._reject > 0:
            self._reject -= 1
            raise busy()
        return "AutoCAD"

    @property
    def Documents(self): return FakeDocs(self)

    @property
    def ActiveDocument(self):
        if not self.docs:
            raise fail("Nenhum documento ativo")
        return self.active

    def GetAcadState(self): return _State(self)
    def ZoomExtents(self): self.zoomed += 1

    def set_command(self, name: str) -> None:
        self.command = name
        self.active.vars["CMDNAMES"] = name
