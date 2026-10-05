"""Business QA, revision identity, unit boundaries and real MCP schema calls."""
import copy
from dataclasses import replace

import pytest
from pydantic import ValidationError

from autocad_mcp.errors import InvalidParameterError
from autocad_mcp.support_quality import SupportSnapshot, audit, compare, digest


def row(handle="A1", tag="PS-001", **updates):
    result = {"handle": handle, "block": "SUP-GUIDE", "layer": "SUPORTES", "position": [0, 0, 0],
              "rotation_deg": 0, "scale": [1, 1, 1], "attributes": {"TAG": tag, "TIPO": "GUIA", "LINHA": "L-100"}}
    result.update(updates)
    return result


def snap(*rows, **updates):
    return SupportSnapshot.model_validate({"document": "TEST.dwg", "units_code": 4, "block_filter": "SUP-*", "rows": list(rows), **updates})


def test_audit_reports_all_failures_and_counts_without_claiming_compliance():
    s = snap(row(), row("A2", " ps-001 "), row("A3", "", attributes={"TAG": "", "TIPO": "UNKNOWN"}))
    result = audit(s, ["GUIA"], ["PS-001", "PS-004"], 1)
    assert result["passed"] is False
    assert result["counts_by_code"] == {"missing_attribute": 2, "unexpected_type": 1, "duplicate_tag": 1, "missing_expected_tag": 1}
    assert result["issue_count"] == 5 and len(result["issues"]) == 1 and result["issues_truncated"]
    assert result["records"] == 3 and result["group_count"] == 2
    assert "not structural" in result["basis"]


def test_empty_or_unitless_scope_never_passes_qa():
    assert audit(snap(), None, None, 200)["counts_by_code"] == {"empty_scope": 1}
    assert audit(snap(row(), units_code=0), None, None, 200)["counts_by_code"] == {"unknown_units": 1}


def test_project_attribute_names_are_configurable():
    s = snap(row(attributes={"ID": "S-1", "TYPE": "GUIDE", "LINE": "P-2"}), fields={"key": "id", "kind": "type", "line": "line"})
    assert audit(s, ["guide"], ["s-1"], 200)["passed"]
    assert s.fields.key == "ID"


def test_revision_matches_by_tag_despite_new_handles_and_detects_real_movement():
    before = snap(row(), row("A2", "PS-002"), row("A3", "PS-003"))
    after = snap(row("F1", position=[3, 4, 0], attributes={"TAG": "PS-001", "TIPO": "ANCORA", "LINHA": "L-100"}),
                 row("F2", "PS-002", position=[0.006, 0.008, 0]), row("F4", "PS-004"))
    result = compare(before, after, 0.01, False, 200)
    assert result["counts"] == {"added": 1, "removed": 1, "changed": 1, "unchanged": 1, "ambiguous_tags": 0, "missing_key_before": 0, "missing_key_after": 0}
    assert result["changed"][0]["changes"]["position"]["distance"] == 5
    assert result["changed"][0]["changes"]["attributes"]["TIPO"] == {"from": "GUIA", "to": "ANCORA"}
    assert result["added"] == ["ps-004"] and result["removed"] == ["ps-003"]


def test_duplicate_and_blank_tags_are_not_matched_or_falsely_removed():
    before = snap(row(), row("A2", "PS-001"), row("A3", ""))
    after = snap(row("F1"))
    r = compare(before, after, 0, False, 200)
    assert r["ambiguous_tags"] == ["ps-001"] and r["missing_key_before"] == ["A3"]
    assert not r["identity_complete"] and not r["removed"] and not r["added"] and not r["changed"]


@pytest.mark.parametrize("updates", [{"units_code": 0}, {"units_code": 1}, {"layer_filter": "OTHER"}, {"fields": {"key": "ID"}}, {"document": "OTHER.dwg"}])
def test_revision_refuses_incompatible_units_scope_keys_and_documents(updates):
    with pytest.raises(InvalidParameterError):
        compare(snap(row()), snap(row(), **updates), 0.01, False, 200)


def test_explicit_document_change_and_modulo_rotation():
    assert compare(snap(row()), snap(row(rotation_deg=360), document="REV-B.dwg"), 0.01, True, 200)["counts"]["unchanged"] == 1


@pytest.mark.parametrize("tol", [-1, float("nan"), float("inf")])
def test_nonfinite_and_negative_tolerances_refused(tol):
    with pytest.raises(InvalidParameterError):
        compare(snap(row()), snap(row()), tol, False, 200)


def test_snapshot_rejects_partial_nonfinite_and_duplicate_handles():
    for content in [{"complete": False}, {"rows": [row(position=[float("nan"), 0, 0])]}, {"rows": [row(), row(tag="PS-2")]},
                    {"fields": {"key": "TAG", "kind": "tag"}}, {"rows": [row(attributes={"TAG": "1", " tag ": "2"})]}]:
        with pytest.raises(ValidationError):
            snap(**content)


def test_digest_stable_with_order_and_changes_with_attributes():
    assert digest(snap(row(), row("A2", "PS-2"))) == digest(snap(row("A2", "PS-2"), row()))
    assert digest(snap(row())) != digest(snap(row(tag="CHANGED")))


def test_end_to_end_tools_snapshot_audit_compare_and_no_undo(call, doc):
    doc.Blocks.define("SUP-GUIDE", {"TAG": "", "TIPO": "GUIA", "LINHA": "L-1"})
    assert call("insert_block", name="SUP-GUIDE", point=[1, 2, 3], attributes={"TAG": "PS-1"})["ok"]
    before_undo = len(doc.journal.groups)
    capture = call("snapshot_support_register", block_filter="SUP-*")
    assert capture["ok"], capture
    payload = capture["data"]["snapshot"]
    result = call("audit_support_register", snapshot=payload, allowed_types=["GUIA"])
    assert result["ok"] and result["data"]["passed"], result
    changed = copy.deepcopy(payload)
    changed["rows"][0]["position"][0] += 5
    result = call("compare_support_register", before=payload, after=changed)
    assert result["ok"] and result["data"]["counts"]["changed"] == 1, result
    assert len(doc.journal.groups) == before_undo


def test_snapshot_scope_and_cap_fail_without_partial_success(call, doc, ctx):
    assert not call("snapshot_support_register")["ok"]
    doc.Blocks.define("SUP-GUIDE", {"TAG": "X"})
    for i in range(2):
        call("insert_block", name="SUP-GUIDE", point=[i, 0, 0])
    ctx.cfg = replace(ctx.cfg, max_batch_rows=1)
    ctx.conn.cfg = ctx.cfg
    result = call("snapshot_support_register", block_filter="SUP-*")
    assert not result["ok"] and result["data"] is None


def test_revision_truncates_details_but_not_counts():
    r = compare(snap(row()), snap(row("F1"), row("F2", "PS-2"), row("F3", "PS-3")), 0, False, 1)
    assert r["counts"]["added"] == 2 and len(r["added"]) == 1 and r["truncated"]


def test_invalid_project_lists_refused():
    for allowed, expected in [([], None), ([" "], None), (None, ["A", " a "]), (None, [""])]:
        with pytest.raises(InvalidParameterError):
            audit(snap(row()), allowed, expected, 200)
