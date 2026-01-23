'''	•	load all *.yml from api/eng/packs/
	•	validate minimal schema (id/title/queries)
	•	return list for UI
'''

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml

PACKS_DIR = Path(__file__).resolve().parent

def _load_yaml(path: Path) -> Dict[str, Any]:
    obj = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"Pack file {path.name} must be a YAML mapping/object")
    return obj

def list_packs() -> List[Dict[str, Any]]:
    packs = []
    for p in sorted(PACKS_DIR.glob("*.yml")):
        obj = _load_yaml(p)
        packs.append(
            {
                "id": obj.get("id"),
                "title": obj.get("title", obj.get("id")),
                "description": obj.get("description", ""),
            }
        )
    packs = [x for x in packs if x.get("id")]
    return packs

def get_pack(pack_id: str) -> Dict[str, Any]:
    for p in PACKS_DIR.glob("*.yml"):
        obj = _load_yaml(p)
        if obj.get("id") == pack_id:
            return obj
    raise KeyError(f"Pack not found: {pack_id}")