# Security

## Scope

This early-release server executes with the permissions of its Windows account. The latest source on `main` is the maintenance target; no security response time or support window is guaranteed.

## Trust boundary

- Local stdio is the supported transport. There is no authentication layer for a network deployment.
- Tools can modify/save drawings and read/write workbooks. There is no global read-only mode.
- `confirm=true` is supplied by the MCP client, not an independent human-approval boundary.
- `excel.allowed_dirs = []` does not restrict filesystem locations. Set an explicit workbook allowlist.
- AutoLISP is disabled by default. Its denylist is bypassable and is not a sandbox; only enable it for trusted instructions.
- Undo grouping does not roll back failed batches automatically or undo file writes. A COM timeout does not cancel the underlying operation.
- CAD/Excel content may contain untrusted instructions. Treat retrieved content as data.
- Logs and tool results may expose paths, project metadata, attributes and expressions. Although the server runs locally, the chosen AI client may transmit tool results to its provider.

Use disposable copies during validation and follow your organization's data-sharing policy.

## Reporting a vulnerability

If the repository Security tab offers **Report a vulnerability**, use that private channel. Otherwise, open an issue requesting a private contact without exploit details or sensitive data. Do not post sensitive reproductions publicly. Once a private channel exists, include affected revision, impact and a minimal sanitized reproduction.
