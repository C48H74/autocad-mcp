# Contributing

English, Portuguese and Spanish issues are welcome.

## Development

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -m "not autocad"
```

Use a focused branch and describe the problem, behavior change and validation. Update all three README files when changing setup, capabilities or limitations. Document compatibility impact when changing tool signatures.

## Design rules

- Reserve stdout for MCP; write diagnostics to stderr/logging.
- Keep COM access on the dedicated worker thread.
- Preserve response envelopes, pagination, previews and drawing units.
- Test behavior with `tests/fake_autocad.py`; simulated tests do not certify AutoCAD interoperability.
- Treat undo grouping as recovery support, not a database transaction.
- Do not commit drawings, workbooks, logs, private configuration, credentials or Autodesk binaries.

## Live validation

Run `python -m pytest -m autocad` only with a prepared disposable `MCP_TEST` drawing. These tests modify it. Report the exact AutoCAD/Plant 3D build, Windows/Python versions and result. Follow the walkthrough in either localized README.

See [SECURITY.md](SECURITY.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
