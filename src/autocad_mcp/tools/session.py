"""Sessão e documento: status, documentos abertos, salvar, zoom."""

from __future__ import annotations

from typing import Any

from autocad_mcp import __version__
from autocad_mcp.errors import DocumentError, InvalidParameterError
from autocad_mcp.session import Session, safe_get
from autocad_mcp.tools._base import com_tool


def _doc_info(doc: Any, active: bool) -> dict[str, Any]:
    return {
        "name": str(safe_get(doc, "Name", default="")),
        "path": str(safe_get(doc, "FullName", default="")),
        "saved": bool(safe_get(doc, "Saved", default=True)),
        "read_only": bool(safe_get(doc, "ReadOnly", default=False)),
        "active": active,
    }


@com_tool(needs_doc=False, mutates=False)
def status(s: Session) -> dict[str, Any]:
    """Diagnóstico do AutoCAD: conectado?, versão, desenho ativo, unidades, nº de entidades, comando ativo.

    QUANDO USAR: sempre como PRIMEIRA chamada de uma conversa e ao suspeitar de problema (erro de
    conexão, "AutoCAD ocupado"). Se o AutoCAD estiver fechado, retorna ok=false com
    error.code="autocad_not_running" (nunca inicia o AutoCAD sozinho).
    Parâmetros: nenhum. Exemplo: status() → data.document.units == "mm".
    """
    app = s.app
    data: dict[str, Any] = {
        "connected": True,
        "server_version": __version__,
        "server_read_only": s.cfg.read_only,
        "application": {
            "name": str(safe_get(app, "Name", default="AutoCAD")),
            "version": str(safe_get(app, "Version", default="?")),
        },
        "documents_open": int(app.Documents.Count),
        "document": None,
        "command_active": False,
        "active_command": None,
    }
    if s.has_document:
        doc = s.doc
        cmd = s.active_command()
        data["command_active"] = cmd is not None
        data["active_command"] = cmd
        data["document"] = {
            **_doc_info(doc, True),
            "units": s.units_name,
            "units_code": s.units_code,
            "model_space_entities": int(doc.ModelSpace.Count),
            "active_space": "model" if int(safe_get(doc, "ActiveSpace", default=1)) == 1 else "paper",
        }
        if cmd:
            s.warn(f"Comando ativo no AutoCAD: {cmd}. Operações de escrita serão bloqueadas até ele terminar (Esc).")
    else:
        s.warn("O AutoCAD está aberto, mas sem nenhum desenho.")
    return data


@com_tool(needs_doc=False, mutates=False)
def list_documents(s: Session) -> dict[str, Any]:
    """Lista os desenhos abertos no AutoCAD (nome, caminho, salvo?, ativo?).

    QUANDO USAR: antes de set_active_document, ou quando há mais de um desenho aberto e é preciso
    saber em qual as ferramentas vão atuar (sempre no desenho ATIVO).
    Exemplo: list_documents() → data.documents[0].name == "SUPORTES-01.dwg".
    """
    docs = s.app.Documents
    active_path = str(safe_get(s.doc, "FullName", default="")) if s.has_document else ""
    items = []
    for i in range(int(docs.Count)):
        d = docs.Item(i)
        info = _doc_info(d, False)
        info["active"] = info["path"] == active_path
        items.append(info)
    return {"documents": items, "count": len(items)}


@com_tool(needs_doc=False)
def set_active_document(s: Session, name: str) -> dict[str, Any]:
    """Torna ativo um desenho já aberto, pelo nome (ex.: "SUPORTES-01.dwg") ou caminho completo.

    QUANDO USAR: para trocar o desenho-alvo das demais ferramentas. Não abre arquivos novos.
    Parâmetros: name (str) — nome ou caminho; comparação sem diferenciar maiúsculas.
    Exemplo: set_active_document("SUPORTES-01.dwg").
    """
    wanted = (name or "").strip().casefold()
    if not wanted:
        raise InvalidParameterError("Informe o nome do desenho.")
    docs = s.app.Documents
    matches = []
    for i in range(int(docs.Count)):
        d = docs.Item(i)
        if wanted in (str(d.Name).casefold(), str(safe_get(d, "FullName", default="")).casefold()):
            matches.append(d)
    if not matches:
        opened = [str(docs.Item(i).Name) for i in range(int(docs.Count))]
        raise DocumentError(f"Desenho '{name}' não está aberto. Abertos: {opened}")
    if len(matches) > 1:
        raise DocumentError(f"'{name}' é ambíguo ({len(matches)} desenhos). Use o caminho completo.")
    matches[0].Activate()
    return {"active": _doc_info(matches[0], True)}


@com_tool()
def save_document(s: Session, confirm: bool = False) -> dict[str, Any]:
    """Salva o desenho ativo POR CIMA do arquivo atual (operação destrutiva: exige confirm=true).

    QUANDO USAR: só quando o usuário pediu para gravar. Desenho sem nome (nunca salvo) é recusado —
    peça ao usuário para usar SALVARCOMO no AutoCAD. Sem confirm=true retorna ok=false com a prévia.
    Parâmetros: confirm (bool). Exemplo: save_document(confirm=true).
    """
    doc = s.doc
    path = str(safe_get(doc, "FullName", default=""))
    saved_once = bool(str(safe_get(doc, "Path", default="")).strip())
    s.require_confirm(confirm, "salvar por cima do arquivo", {"file": path or str(doc.Name)})
    s.assert_writable()
    if not saved_once:
        raise DocumentError("O desenho ainda não tem arquivo (sem nome). Use SALVARCOMO no AutoCAD primeiro.")
    doc.Save()
    return {"saved": True, "file": path}


@com_tool(needs_doc=False)
def zoom_extents(s: Session) -> dict[str, Any]:
    """Enquadra a vista atual em todos os objetos do desenho (ZOOM Extents).

    QUANDO USAR: depois de inserir/desenhar coisas, para o usuário enxergar o resultado.
    Não altera o desenho (não entra no histórico de desfazer). Exemplo: zoom_extents().
    """
    s.app.ZoomExtents()
    return {"zoomed": True}


TOOLS = [status, list_documents, set_active_document, save_document, zoom_extents]
