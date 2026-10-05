"""Garantias estáticas: nenhum print() (stdout é do protocolo MCP) e nada de import top-level de win32."""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "autocad_mcp"


def _py_files():
    return sorted(SRC.rglob("*.py"))


def test_no_print_calls_anywhere_in_package():
    offenders = []
    for f in _py_files():
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print":
                offenders.append(f"{f.name}:{node.lineno}")
            if isinstance(node, ast.Attribute) and node.attr == "stdout" and isinstance(node.value, ast.Name) and node.value.id == "sys":
                offenders.append(f"{f.name}:{node.lineno} (sys.stdout)")
    assert not offenders, f"stdout é exclusivo do MCP: {offenders}"


def test_win32_modules_imported_only_in_compat_layer():
    for f in _py_files():
        if f.name == "_com.py":
            continue
        text = f.read_text(encoding="utf-8")
        for bad in ("import pythoncom", "import pywintypes", "import win32com", "from win32com"):
            assert bad not in text, f"{f.name} importa win32 diretamente ({bad})"
