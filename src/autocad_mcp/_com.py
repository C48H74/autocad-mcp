"""Camada de compatibilidade COM.

No Windows com pywin32 instalado, reexporta os módulos reais. Em qualquer outro caso
(Linux/macOS/CI sem pywin32) fornece *stubs mínimos* — o suficiente para importar o
pacote, montar VARIANTs "de mentira" e rodar a suíte `pytest -m "not autocad"`.
Os stubs NUNCA conectam ao AutoCAD: `HAS_PYWIN32` é False e a conexão falha de forma limpa.
"""

from __future__ import annotations

from types import SimpleNamespace

try:  # pragma: no cover - depende da plataforma
    import pythoncom
    import pywintypes
    import win32com.client as win32client

    HAS_PYWIN32 = True
    com_error = pywintypes.com_error
    VARIANT = win32client.VARIANT
except ImportError:
    HAS_PYWIN32 = False
    win32client = None

    class com_error(Exception):  # noqa: N801 - mesmo nome do pywintypes
        """Stub de pywintypes.com_error: args = (hresult, strerror, excepinfo, argerror)."""

        def __init__(self, hresult=0, strerror="", excepinfo=None, argerror=None):
            super().__init__(hresult, strerror, excepinfo, argerror)
            self.hresult = hresult
            self.strerror = strerror
            self.excepinfo = excepinfo
            self.argerror = argerror

    class VARIANT:  # noqa: N801
        """Stub de win32com.client.VARIANT: guarda o tipo (vt) e o valor Python."""

        def __init__(self, vt, value=None):
            self.varianttype = vt
            self.value = value

        def __repr__(self) -> str:
            return f"VARIANT(vt={self.varianttype:#x}, value={self.value!r})"

    _MISSING = type("_Missing", (), {"__repr__": lambda self: "pythoncom.Missing"})()

    pythoncom = SimpleNamespace(
        VT_ARRAY=0x2000,
        VT_R8=5,
        VT_I2=2,
        VT_VARIANT=12,
        VT_BYREF=0x4000,
        Missing=_MISSING,
        Empty=None,
        CoInitialize=lambda: None,
        CoUninitialize=lambda: None,
    )
    pywintypes = SimpleNamespace(com_error=com_error, IID=lambda value: value)

__all__ = ["HAS_PYWIN32", "pythoncom", "pywintypes", "win32client", "com_error", "VARIANT"]
