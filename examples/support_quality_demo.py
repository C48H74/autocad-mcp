"""Synthetic, offline review example. Run from an installed checkout; no AutoCAD is contacted."""
import copy
import json

from autocad_mcp.support_quality import SupportSnapshot, audit, compare

before = {"document": "SYNTHETIC.dwg", "units_code": 4, "block_filter": "SUP-*", "rows": [
    {"handle": "A1", "block": "SUP-GUIDE", "layer": "SUPORTES", "position": [0, 0, 0],
     "rotation_deg": 0, "scale": [1, 1, 1], "attributes": {"TAG": "PS-001", "TIPO": "GUIA", "LINHA": "DEMO-100"}}
]}
after = copy.deepcopy(before)
after["rows"][0]["handle"] = "F1"
after["rows"][0]["position"] = [3, 4, 0]
after["rows"][0]["attributes"]["TIPO"] = "ANCORA"
a, b = SupportSnapshot.model_validate(before), SupportSnapshot.model_validate(after)
print(json.dumps({"synthetic_example": True, "audit": audit(b, ["GUIA", "ANCORA"], ["PS-001"], 200),
                  "comparison": compare(a, b, 0.01, False, 200)}, ensure_ascii=False, indent=2))
