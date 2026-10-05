"""Gera a planilha de teste `suportes_teste.xlsx` (100 suportes) para validar o servidor.

Uso:   python examples/make_test_workbook.py [caminho_de_saida.xlsx]

As 3 primeiras linhas repetem as TAGs PS-001..PS-003 que você insere à mão no desenho de teste
(passo 5 do README): importar com key_tag="TAG" ATUALIZA esses 3 e INSERE os outros 97.
Unidade das coordenadas = unidade do desenho (mm no desenho de teste).
"""

from __future__ import annotations

import sys
from pathlib import Path

from openpyxl import Workbook

TIPOS = ["GUIA", "SHOE", "ANCORA", "MOLA"]


def main(out: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Suportes"
    ws.append(["TAG", "TIPO", "X", "Y", "Z", "LINHA", "CAMADA"])
    for i in range(1, 101):
        ws.append([
            f"PS-{i:03d}",
            TIPOS[i % len(TIPOS)],
            (i - 1) * 1000.0,
            2000.0 + (i // 10) * 500.0,
            4200.0,
            f"10-P-{1000 + i // 5}",
            "SUPORTES",
        ])
    wb.save(out)
    sys.stderr.write(f"Planilha gerada: {out} (100 linhas)\n")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("suportes_teste.xlsx"))
