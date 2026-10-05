"""Helpers puros — rodam sem AutoCAD e sem pywin32."""

import datetime as dt

import pytest

from autocad_mcp._com import VARIANT, pythoncom
from autocad_mcp.errors import InvalidParameterError
from autocad_mcp.geometry import (
    dxf_filter,
    dxf_pattern,
    flatten_xy,
    flatten_xyz,
    format_cell,
    from_com_point,
    normalize_bbox,
    normalize_point,
    parse_number,
    to_variant_point,
    units_name,
)


def test_point_variant_type_and_padding():
    v = to_variant_point([1, 2])
    assert isinstance(v, VARIANT)
    assert v.varianttype == pythoncom.VT_ARRAY | pythoncom.VT_R8
    assert list(v.value) == [1.0, 2.0, 0.0]


@pytest.mark.parametrize("bad", [[1], [1, 2, 3, 4], "abc", [1, "x"], [float("nan"), 0], [float("inf"), 0, 0], None])
def test_point_rejects_invalid(bad):
    with pytest.raises(InvalidParameterError):
        normalize_point(bad)


def test_flatten():
    pts = [(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)]
    assert flatten_xy(pts) == [1.0, 2.0, 4.0, 5.0]
    assert flatten_xyz(pts) == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]


def test_bbox_is_ordered_and_2d_supported():
    p1, p2 = normalize_bbox([10, 20, 0, 5])
    assert p1 == (0.0, 5.0, 0.0) and p2 == (10.0, 20.0, 0.0)
    with pytest.raises(InvalidParameterError):
        normalize_bbox([1, 2, 3])


def test_units():
    assert units_name(4) == "mm" and units_name(6) == "m"
    assert "99" in units_name(99)


def test_dxf_pattern_escapes_specials_but_keeps_star_and_question():
    assert dxf_pattern("PIPE-*") == "PIPE-*"
    assert dxf_pattern("A.B") == "A`.B"
    assert dxf_pattern("X[1],#") == "X`[1`]`,`#"
    assert dxf_pattern("SUP-?") == "SUP-?"


def test_dxf_filter_variants():
    ft, fd = dxf_filter([(0, "INSERT"), (8, "PIPE")])
    assert ft.varianttype == pythoncom.VT_ARRAY | pythoncom.VT_I2 and list(ft.value) == [0, 8]
    assert fd.varianttype == pythoncom.VT_ARRAY | pythoncom.VT_VARIANT and list(fd.value) == ["INSERT", "PIPE"]


@pytest.mark.parametrize(
    "raw,expected",
    [(5, 5.0), (2.5, 2.5), ("12,5", 12.5), ("1.234,56", 1234.56), ("1234.56", 1234.56), (" 7 ", 7.0), ("-3,2", -3.2)],
)
def test_parse_number(raw, expected):
    assert parse_number(raw) == pytest.approx(expected)


@pytest.mark.parametrize("bad", ["abc", "", None, True, float("nan"), "1,2,3"])
def test_parse_number_rejects(bad):
    with pytest.raises(InvalidParameterError):
        parse_number(bad)


def test_format_cell():
    assert format_cell(5.0) == "5" and format_cell(5.25) == "5.25" and format_cell(None) == ""
    assert format_cell("  x ") == "x" and format_cell(True) == "TRUE" and format_cell(12) == "12"
    assert format_cell(dt.date(2026, 9, 29)) == "2026-09-29"
    assert format_cell(0.1 + 0.2) == "0.3"


def test_from_com_point_rounds():
    assert from_com_point((1.23456789, 2, 3)) == [1.234568, 2.0, 3.0]
