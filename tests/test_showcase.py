"""Os exemplos de vitrine (P&ID, tanque, arranjo geral) geram DXF válidos (audit sem erros) e PNG."""
import os
import subprocess
import sys
from pathlib import Path

import ezdxf
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("script,stem", [("pid.py", "05_pid_tanque_bombas_trocador"), ("tanque.py", "06_tanque_bocais_base"),
                                         ("layout.py", "07_layout_arranjo_geral")])
def test_showcase_example_builds_and_audits(script, stem, tmp_path):
    env = dict(os.environ, SHOWCASE_DPI="40", PYTHONPATH=str(ROOT / "src"))
    r = subprocess.run([sys.executable, script, str(tmp_path)], cwd=ROOT / "examples" / "showcase", env=env,
                       capture_output=True, text=True, timeout=170)
    assert r.returncode == 0, r.stderr[-800:]
    assert (tmp_path / f"{stem}.png").stat().st_size > 5_000
    doc = ezdxf.readfile(str(tmp_path / f"{stem}.dxf"))
    auditor = doc.audit()
    assert not auditor.errors, [e.message for e in auditor.errors][:5]
    assert len(doc.modelspace()) > 500
