"""Deterministic support-register QA. No CAD writes, inferred loads or code compliance claims."""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator

from autocad_mcp.errors import InvalidParameterError


class Fields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(default="TAG", min_length=1, max_length=80)
    kind: str = Field(default="TIPO", min_length=1, max_length=80)
    line: str = Field(default="LINHA", min_length=1, max_length=80)

    @model_validator(mode="after")
    def normalize(self):
        for name in ("key", "kind", "line"):
            setattr(self, name, getattr(self, name).strip().upper())
        if not all((self.key, self.kind, self.line)) or len({self.key, self.kind, self.line}) != 3:
            raise ValueError("key, kind e line devem ser nomes de atributo distintos e não vazios.")
        return self


class SupportRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    handle: str = Field(min_length=1, max_length=80)
    block: str = Field(min_length=1, max_length=255)
    layer: str = Field(max_length=255)
    position: tuple[FiniteFloat, FiniteFloat, FiniteFloat]
    rotation_deg: FiniteFloat
    scale: tuple[FiniteFloat, FiniteFloat, FiniteFloat]
    attributes: dict[str, str]

    @model_validator(mode="after")
    def bounded_attributes(self):
        if len(self.attributes) > 100 or any(len(k) > 80 or len(v) > 2000 for k, v in self.attributes.items()):
            raise ValueError("Atributos excedem os limites (100 campos, 80/2000 caracteres).")
        normalized = {k.strip().upper(): v for k, v in self.attributes.items()}
        if "" in normalized or len(normalized) != len(self.attributes):
            raise ValueError("Nomes de atributo vazios ou ambíguos após normalização.")
        self.attributes = normalized
        return self


class SupportSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    document: str = Field(min_length=1, max_length=1024)
    units_code: int = Field(ge=0, le=24, strict=True)
    coordinate_frame: Literal["COM-WCS"] = "COM-WCS"
    block_filter: str | None = Field(default=None, max_length=255)
    layer_filter: str | None = Field(default=None, max_length=255)
    fields: Fields = Field(default_factory=Fields)
    complete: Literal[True] = True
    rows: list[SupportRow] = Field(max_length=2000)

    @model_validator(mode="after")
    def complete_scope(self):
        if not (self.block_filter or self.layer_filter):
            raise ValueError("Defina block_filter ou layer_filter para delimitar o cadastro.")
        handles = [r.handle.upper() for r in self.rows]
        if len(set(handles)) != len(handles):
            raise ValueError("Handles duplicados: snapshot possivelmente montado com páginas repetidas.")
        if len(self.model_dump_json()) > 2_000_000:
            raise ValueError("Snapshot excede 2 MB; restrinja o escopo.")
        return self


def key(value: str) -> str:
    return value.strip().casefold()


def digest(snapshot: SupportSnapshot) -> str:
    data = snapshot.model_dump(mode="json")
    data["rows"] = sorted(data["rows"], key=lambda row: row["handle"].upper())
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def index(snapshot: SupportSnapshot):
    by_tag = defaultdict(list)
    missing = []
    for row in snapshot.rows:
        tag = key(row.attributes.get(snapshot.fields.key, ""))
        if tag:
            by_tag[tag].append(row)
        else:
            missing.append(row.handle)
    return by_tag, missing


def audit(snapshot: SupportSnapshot, allowed_types: list[str] | None, expected_tags: list[str] | None, limit: int):
    if not 1 <= limit <= 500:
        raise InvalidParameterError("limit deve estar entre 1 e 500.")
    if allowed_types is not None and (not allowed_types or len(allowed_types) > 200 or any(not key(t) for t in allowed_types)):
        raise InvalidParameterError("allowed_types deve conter 1..200 valores não vazios, ou null.")
    if expected_tags is not None and (len(expected_tags) > 2000 or any(not key(t) for t in expected_tags)):
        raise InvalidParameterError("expected_tags aceita até 2000 TAGs não vazias.")
    if expected_tags is not None and len({key(t) for t in expected_tags}) != len(expected_tags):
        raise InvalidParameterError("expected_tags contém duplicidades após normalização.")
    issues, counts = [], Counter()
    def issue(code, **details):
        counts[code] += 1
        if len(issues) < limit:
            issues.append({"code": code, **details})
    if not snapshot.rows:
        issue("empty_scope")
    if snapshot.units_code == 0:
        issue("unknown_units")
    allowed = {key(t) for t in allowed_types} if allowed_types is not None else None
    grouped = Counter()
    for row in snapshot.rows:
        for field in snapshot.fields.model_dump().values():
            if not row.attributes.get(field, "").strip():
                issue("missing_attribute", handle=row.handle, field=field)
        kind = row.attributes.get(snapshot.fields.kind, "").strip()
        line = row.attributes.get(snapshot.fields.line, "").strip()
        if allowed is not None and kind and key(kind) not in allowed:
            issue("unexpected_type", handle=row.handle, value=kind)
        grouped[(line, kind)] += 1
    by_tag, _ = index(snapshot)
    for tag, rows in sorted(by_tag.items()):
        if len(rows) > 1:
            issue("duplicate_tag", tag=tag, count=len(rows), handles=[r.handle for r in rows[:50]], handles_truncated=len(rows) > 50)
    if expected_tags is not None:
        expected = {key(t) for t in expected_tags}
        for tag in sorted(expected - by_tag.keys()):
            issue("missing_expected_tag", tag=tag)
        for tag in sorted(by_tag.keys() - expected):
            issue("unexpected_tag", tag=tag)
    groups = [{"line": line, "type": kind, "count": n} for (line, kind), n in sorted(grouped.items())]
    return {"passed": not counts, "snapshot_sha256": digest(snapshot), "records": len(snapshot.rows),
            "issue_count": sum(counts.values()), "counts_by_code": dict(counts), "issues": issues,
            "issues_truncated": sum(counts.values()) > limit, "groups": groups[:limit], "group_count": len(groups),
            "groups_truncated": len(groups) > limit, "basis": "Project-supplied fields/types/register only; not structural or code compliance."}


def compare(before: SupportSnapshot, after: SupportSnapshot, position_tolerance: float, allow_document_change: bool, limit: int):
    if not math.isfinite(position_tolerance) or position_tolerance < 0 or not 1 <= limit <= 500:
        raise InvalidParameterError("Tolerância finita >= 0 e limit entre 1 e 500 são obrigatórios.")
    if before.units_code == 0 or before.units_code != after.units_code:
        raise InvalidParameterError("Unidades desconhecidas ou diferentes; não há conversão implícita.")
    if before.fields != after.fields or (before.block_filter, before.layer_filter) != (after.block_filter, after.layer_filter):
        raise InvalidParameterError("Mapeamento de atributos e filtros devem ser idênticos entre revisões.")
    if before.document != after.document and not allow_document_change:
        raise InvalidParameterError("Documentos diferentes: confirme o mesmo cadastro com allow_document_change=true.")
    old, missing_old = index(before)
    new, missing_new = index(after)
    ambiguous = {k for k in old.keys() | new.keys() if len(old.get(k, [])) > 1 or len(new.get(k, [])) > 1}
    # Never guess identity by proximity or handle when the business key is ambiguous.
    old_keys, new_keys = old.keys() - ambiguous, new.keys() - ambiguous
    added, removed = sorted(new_keys - old_keys), sorted(old_keys - new_keys)
    changed, changed_count, unchanged = [], 0, 0
    for tag in sorted(old_keys & new_keys):
        a, b = old[tag][0], new[tag][0]
        changes: dict[str, Any] = {}
        distance = math.dist(a.position, b.position)
        if distance > position_tolerance:
            changes["position"] = {"from": a.position, "to": b.position, "distance": distance}
        for field in ("block", "layer", "scale"):
            if getattr(a, field) != getattr(b, field):
                changes[field] = {"from": getattr(a, field), "to": getattr(b, field)}
        if abs((b.rotation_deg - a.rotation_deg + 180) % 360 - 180) > 1e-9:
            changes["rotation_deg"] = {"from": a.rotation_deg, "to": b.rotation_deg}
        attrs = {k: {"from": a.attributes.get(k), "to": b.attributes.get(k)}
                 for k in sorted(a.attributes.keys() | b.attributes.keys()) if a.attributes.get(k) != b.attributes.get(k)}
        if attrs:
            changes["attributes"] = attrs
        if changes:
            changed_count += 1
            if len(changed) < limit:
                changed.append({"tag": tag, "before_handle": a.handle, "after_handle": b.handle, "changes": changes})
        else:
            unchanged += 1
    return {"before_sha256": digest(before), "after_sha256": digest(after), "units_code": before.units_code,
            "position_tolerance": position_tolerance, "identity": "trimmed case-insensitive TAG; handles not used for matching",
            "counts": {"added": len(added), "removed": len(removed), "changed": changed_count, "unchanged": unchanged,
                       "ambiguous_tags": len(ambiguous), "missing_key_before": len(missing_old), "missing_key_after": len(missing_new)},
            "added": added[:limit], "removed": removed[:limit], "changed": changed,
            "ambiguous_tags": sorted(ambiguous)[:limit], "missing_key_before": missing_old[:limit], "missing_key_after": missing_new[:limit],
            "truncated": any(n > limit for n in (len(added), len(removed), changed_count, len(ambiguous), len(missing_old), len(missing_new))),
            "identity_complete": not (ambiguous or missing_old or missing_new),
            "note": "TAG renames appear as removal/addition. No load, stress, geometry-definition or Plant database validation."}
