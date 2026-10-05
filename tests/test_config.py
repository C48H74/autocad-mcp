"""Configuração e logging — sem AutoCAD."""

import logging
import sys

import pytest

from autocad_mcp.config import Config, default_log_dir, load_config, setup_logging


@pytest.fixture(autouse=True)
def _reset_logging_handlers():
    """setup_logging troca os handlers do logger do pacote: restaura ao fim para não vazar entre testes."""
    yield
    root = logging.getLogger("autocad_mcp")
    for h in list(root.handlers):
        h.close()
        root.removeHandler(h)


def test_defaults_are_safe():
    c = Config()
    assert c.enable_lisp is False and c.allow_launch is False and c.com_binding == "dynamic"
    assert c.default_limit <= c.max_limit and c.com_timeout_s > 0


def test_from_dict_normalises_and_survives_bad_values():
    c = Config.from_dict({
        "server": {"enable_lisp": True, "com_binding": "GENCACHE", "com_timeout_s": 0},
        "limits": {"default_limit": 9999, "max_limit": 100},
        "log": {"level": "verbose"},
        "excel": {"allowed_dirs": ["C:/a"]},
    })
    assert c.enable_lisp and c.com_binding == "gencache" and c.com_timeout_s == 1.0
    assert c.default_limit == 100 and c.max_limit == 100 and c.log_level == "INFO" and len(c.excel_allowed_dirs) == 1
    assert Config.from_dict({"server": {"com_binding": "xyz"}}).com_binding == "dynamic"


def test_load_config_from_env_var(tmp_path, monkeypatch):
    f = tmp_path / "c.toml"
    f.write_text("[server]\nenable_lisp = true\n[limits]\ndefault_limit = 7\n", encoding="utf-8")
    monkeypatch.setenv("AUTOCAD_MCP_CONFIG", str(f))
    c = load_config()
    assert c.enable_lisp is True and c.default_limit == 7


def test_load_config_invalid_toml_falls_back_to_defaults(tmp_path, monkeypatch):
    f = tmp_path / "bad.toml"
    f.write_text("isto = = não é toml", encoding="utf-8")
    monkeypatch.setenv("AUTOCAD_MCP_CONFIG", str(f))
    from autocad_mcp.paths import default_workspace

    assert load_config() == Config(read_only=True, excel_allowed_dirs=(default_workspace(),))


def test_load_config_restricts_paths_by_default_and_allow_any_opens(tmp_path, monkeypatch):
    from autocad_mcp.paths import default_workspace

    monkeypatch.delenv("AUTOCAD_MCP_ALLOWED_DIRS", raising=False)
    f = tmp_path / "c.toml"
    f.write_text("[server]\n", encoding="utf-8")
    monkeypatch.setenv("AUTOCAD_MCP_CONFIG", str(f))
    assert load_config().excel_allowed_dirs == (default_workspace(),)
    f.write_text("[paths]\nallow_any = true\n", encoding="utf-8")
    assert load_config().excel_allowed_dirs == ()


def test_default_log_dir_does_not_depend_on_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert tmp_path not in default_log_dir().parents


def test_logging_goes_to_stderr_and_file_never_stdout(tmp_path, capfd):
    cfg = Config(log_dir=tmp_path / "logs", log_level="INFO")
    logfile = setup_logging(cfg)
    logging.getLogger("autocad_mcp.teste").info("mensagem de teste")
    for h in logging.getLogger("autocad_mcp").handlers:
        h.flush()
    out, err = capfd.readouterr()
    assert out == "" and "mensagem de teste" in err
    assert logfile is not None and "mensagem de teste" in logfile.read_text(encoding="utf-8")
    assert all(getattr(h, "stream", None) is not sys.stdout for h in logging.getLogger("autocad_mcp").handlers)


def test_logging_survives_unwritable_dir(tmp_path):
    blocker = tmp_path / "arquivo"
    blocker.write_text("x")
    assert setup_logging(Config(log_dir=blocker / "sub")) is None  # só stderr, sem exceção
