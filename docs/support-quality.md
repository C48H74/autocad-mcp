# Support register QA / Conferência de suportes / Revisión de soportes

Version 0.2.0 adds an attribute-register review workflow for piping/support teams. It inspects generic AutoCAD blocks, not native Plant 3D support objects. It does not validate loads, stress, allowable spans, material suitability or compliance with an engineering standard.

## Workflow

1. Call `system_capabilities` without connecting to AutoCAD. Use `status` to verify the actual connection, drawing and units.
2. Call `snapshot_support_register(block_filter="SUP-*", layer_filter="SUPORTES")`.
3. Pass the returned **data.snapshot** object to `audit_support_register`. Supply approved `allowed_types` and/or `expected_tags` from your project when available. No standard or support type list is invented by the server.
4. Keep the complete snapshot in your MCP client's approved storage. Capture the same scope after a revision and pass both objects as `before` and `after` to `compare_support_register`.

The snapshot contains editable attributes, handle, block name, layer, position, rotation and scale. It is limited to the lower of `max_batch_rows` and 2000 blocks and refuses an oversized scope instead of returning an incomplete register. It neither saves the DWG nor writes snapshot files. An SHA-256 digest identifies snapshot content; it does not authenticate its origin or prove that the drawing was unchanged during capture.

## Português

Exemplo: «Capture os blocos SUP-* da camada SUPORTES. Confira TAGs duplicadas, TAG/TIPO/LINHA vazios e os tipos aprovados do meu projeto. Mostre o total por linha e tipo. Não altere o desenho.»

Para atributos em inglês, use `key_tag="TAG", type_tag="TYPE", line_tag="LINE"`. Os nomes são explícitos: o servidor não escolhe automaticamente entre campos potencialmente ambíguos. As quantidades são de referências de bloco, não uma lista de materiais de fabricação.

Compare revisões pelo objeto `data.snapshot`. Mudanças de TAG aparecem como remoção + adição. TAGs duplicadas ou vazias ficam pendentes, sem casar por proximidade. Informe `allow_document_change=true` somente quando nomes de DWG diferentes representam revisões do mesmo cadastro.

## Español

Ejemplo: «Captura los bloques SUP-* de la capa SUPORTES. Comprueba TAG duplicadas, campos TAG/TIPO/LINHA vacíos y los tipos aprobados del proyecto. Muestra el recuento por línea y tipo, sin modificar el dibujo.»

Los nombres de atributos son configurables. Los recuentos representan referencias de bloque, no cantidades certificadas para fabricación. Una TAG renombrada aparece como eliminación + adición. Las TAG duplicadas o vacías quedan sin resolver. Solo utiliza `allow_document_change=true` si ambos archivos corresponden al mismo registro.

## Comparison contract

- Keys are trimmed and case-insensitive. Exact attribute text differences are still reported.
- Handles can change between revisions without losing TAG identity.
- Document names must match unless explicitly overridden. Field mappings and block/layer filters must match exactly.
- Both snapshots must use the same known unit code. There is no implicit unit or coordinate-system conversion. The operator must confirm a shared coordinate origin/orientation.
- Default position tolerance is **0.01 drawing units**, an algorithm setting rather than an engineering acceptance tolerance. Distance is Euclidean in 3D. Rotation is compared modulo 360 degrees; scale and other fields are compared exactly.
- Added/removed/changed counts remain complete when detail lists are capped (`limit=1..500`). `identity_complete=false` means missing or duplicated keys prevent full matching. `truncated=true` means some details were omitted.
- Snapshots must be complete and valid. Do not concatenate repeated pages or manually claim a partial extract is complete.
- Block-definition geometry, xref contents, constant attributes and the Plant project database are not compared.
- Capture while no other operator is editing the drawing; COM reads do not provide transaction isolation.

## Read-only review mode

Set `read_only=true` under `[server]` or add `AUTOCAD_MCP_READ_ONLY="1"` to the client's server environment, then restart. This blocks all mutating tools, including their dry-run calls, Excel export, LISP, save, zoom and document activation. Reading, snapshots, audit and comparison remain available. Logging and temporary COM SelectionSets remain; no OS sandbox is implied.

MCP read-only annotations are advisory to clients; the server-side gate enforces the configured restriction. The default remains writable for backward compatibility. The independent environment override survives malformed config files; malformed files/values also fall back to read-only mode.
