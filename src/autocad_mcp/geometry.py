"""Helpers puros de geometria/VARIANT/unidades/filtros DXF (testáveis sem AutoCAD)."""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Sequence
from datetime import date, datetime
from typing import Any

from autocad_mcp._com import VARIANT, pythoncom
from autocad_mcp.errors import InvalidParameterError

# --- Unidades (variável de sistema INSUNITS) ---------------------------------------------------
INSUNITS: dict[int, str] = {
    0: "sem unidade", 1: "polegadas", 2: "pés", 3: "milhas", 4: "mm", 5: "cm", 6: "m", 7: "km",
    8: "micropolegadas", 9: "mils", 10: "jardas", 11: "angstroms", 12: "nanômetros",
    13: "mícrons", 14: "dm", 15: "dam", 16: "hm", 17: "Gm", 18: "UA", 19: "anos-luz",
    20: "parsecs", 21: "pés (US survey)", 22: "polegadas (US survey)", 23: "jardas (US survey)",
    24: "milhas (US survey)",
}


def units_name(code: int) -> str:
    return INSUNITS.get(int(code), f"código {int(code)}")


# --- Pontos ------------------------------------------------------------------------------------
Point3 = tuple[float, float, float]


def normalize_point(value: Any, *, name: str = "ponto") -> Point3:
    """Aceita [x, y] ou [x, y, z] e devolve (x, y, z) finitos."""
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise InvalidParameterError(f"{name}: esperado lista [x, y] ou [x, y, z], recebido {value!r}")
    if len(value) not in (2, 3):
        raise InvalidParameterError(f"{name}: esperado 2 ou 3 coordenadas, recebido {len(value)}")
    try:
        nums = [float(v) for v in value]
    except (TypeError, ValueError) as exc:
        raise InvalidParameterError(f"{name}: coordenada não numérica em {value!r}") from exc
    if not all(math.isfinite(v) for v in nums):
        raise InvalidParameterError(f"{name}: coordenadas devem ser finitas ({value!r})")
    if len(nums) == 2:
        nums.append(0.0)
    return (nums[0], nums[1], nums[2])


def to_variant_point(value: Any, *, name: str = "ponto") -> Any:
    """Helper ÚNICO de ponto: VARIANT(VT_ARRAY | VT_R8, [x, y, z]) (regra 5)."""
    x, y, z = normalize_point(value, name=name)
    return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [x, y, z])


def to_variant_doubles(values: Iterable[float]) -> Any:
    """Array plano de doubles (vértices de polilinha: [x1, y1, x2, y2, ...])."""
    return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [float(v) for v in values])


def variant_value(v: Any) -> Any:
    """Valor Python de um VARIANT (ou o próprio valor, se já for nativo)."""
    return v.value if isinstance(v, VARIANT) else v


def from_com_point(v: Any, *, ndigits: int = 6) -> list[float]:
    """Tupla/array COM → lista de floats arredondados."""
    return [round(float(x), ndigits) for x in v]


def flatten_xy(points: Sequence[Point3]) -> list[float]:
    return [c for p in points for c in (p[0], p[1])]


def flatten_xyz(points: Sequence[Point3]) -> list[float]:
    return [c for p in points for c in p]


def deg_to_rad(deg: float) -> float:
    return math.radians(float(deg))


def rad_to_deg(rad: float, ndigits: int = 6) -> float:
    return round(math.degrees(float(rad)), ndigits)


def normalize_bbox(bbox: Any) -> tuple[Point3, Point3]:
    """[xmin, ymin, xmax, ymax] (2D) ou [xmin, ymin, zmin, xmax, ymax, zmax] → (p1, p2) ordenados."""
    if isinstance(bbox, (str, bytes)) or not isinstance(bbox, Sequence) or len(bbox) not in (4, 6):
        raise InvalidParameterError("bbox: use [xmin, ymin, xmax, ymax] ou [xmin, ymin, zmin, xmax, ymax, zmax]")
    try:
        n = [float(v) for v in bbox]
    except (TypeError, ValueError) as exc:
        raise InvalidParameterError(f"bbox com valor não numérico: {bbox!r}") from exc
    if len(n) == 4:
        n = [n[0], n[1], 0.0, n[2], n[3], 0.0]
    p1 = (min(n[0], n[3]), min(n[1], n[4]), min(n[2], n[5]))
    p2 = (max(n[0], n[3]), max(n[1], n[4]), max(n[2], n[5]))
    return p1, p2


# --- Filtros DXF para SelectionSet.Select ------------------------------------------------------
_DXF_SPECIAL = set("`#@.~[],")  # curingas do AutoCAD, exceto * e ?  (tratados à parte)


def dxf_pattern(text: str) -> str:
    """Texto do usuário → padrão DXF: `*` e `?` continuam curingas; o resto é escapado com `.

    Assim "PIPE.A" casa literalmente (e não como "PIPE" + qualquer caractere + "A").
    """
    out: list[str] = []
    for ch in text:
        out.append("`" + ch if ch in _DXF_SPECIAL else ch)
    return "".join(out)


def dxf_filter(pairs: Sequence[tuple[int, Any]]) -> tuple[Any, Any]:
    """[(0, "INSERT"), (8, "PIPE-*")] → (FilterType, FilterData) como VARIANTs de SAFEARRAY."""
    codes = [int(c) for c, _ in pairs]
    data = [v for _, v in pairs]
    return (
        VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_I2, codes),
        VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_VARIANT, data),
    )


# --- Valores de célula/atributo ----------------------------------------------------------------
_NUM_PT = re.compile(r"^[+-]?\d{1,3}(\.\d{3})*,\d+$")   # 1.234,56
_NUM_EN = re.compile(r"^[+-]?\d+([.,]\d+)?$")           # 1234.56 | 1234,56


def parse_number(value: Any, *, name: str = "valor") -> float:
    """Número vindo do Excel: aceita int/float e texto com vírgula decimal ("1.234,56", "12,5")."""
    if isinstance(value, bool):
        raise InvalidParameterError(f"{name}: booleano não é número")
    if isinstance(value, (int, float)):
        f = float(value)
    elif isinstance(value, str):
        s = value.strip().replace(" ", "")
        if _NUM_PT.match(s):
            s = s.replace(".", "").replace(",", ".")
        elif _NUM_EN.match(s):
            s = s.replace(",", ".")
        try:
            f = float(s)
        except ValueError as exc:
            raise InvalidParameterError(f"{name}: '{value}' não é numérico") from exc
    else:
        raise InvalidParameterError(f"{name}: tipo não suportado ({type(value).__name__})")
    if not math.isfinite(f):
        raise InvalidParameterError(f"{name}: valor não finito")
    return f


def format_cell(value: Any) -> str:
    """Valor de célula → texto de atributo. None → ''. 5.0 → '5'. Datas → ISO."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else format(value, ".10g")
    if isinstance(value, (datetime, date)):
        return value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat()
    return str(value).strip()
