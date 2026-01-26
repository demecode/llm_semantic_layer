'''	•	load all *.yml from api/eng/packs/
	•	validate minimal schema (id/title/queries)
	•	return list for UI
'''
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml

PACKS_DIR = Path(__file__).resolve().parent

REQUIRED_KEYS = {"id"}
TITLE_KEYS = ("title", "name")


def _load_yaml(path: Path) -> Dict[str, Any]:
    obj = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"Pack file {path.name} must be a YAML mapping/object")
    return obj


def _validate_min_schema(obj: Dict[str, Any], path: Path) -> None:
    missing = [k for k in REQUIRED_KEYS if not obj.get(k)]
    if missing:
        raise ValueError(f"Pack {path.name} missing required field(s): {missing}")

    # Ensure it has something displayable
    if not any(obj.get(k) for k in TITLE_KEYS):
        raise ValueError(f"Pack {path.name} must include one of {TITLE_KEYS}")


def list_packs() -> List[Dict[str, Any]]:
    packs: List[Dict[str, Any]] = []

    for p in sorted(PACKS_DIR.glob("*.yml")):
        obj = _load_yaml(p)
        _validate_min_schema(obj, p)

        title = obj.get("title") or obj.get("name") or obj.get("id")
        packs.append(
            {
                "id": obj.get("id"),
                "title": title,
                "description": obj.get("description", "") or "",
                "intent": obj.get("intent", "unknown"),
            }
        )

    # Unique IDs
    seen = set()
    out = []
    for x in packs:
        pid = x["id"]
        if pid in seen:
            raise ValueError(f"Duplicate pack id found: {pid}")
        seen.add(pid)
        out.append(x)

    return out


def get_pack(pack_id: str) -> Dict[str, Any]:
    for p in PACKS_DIR.glob("*.yml"):
        obj = _load_yaml(p)
        if obj.get("id") == pack_id:
            _validate_min_schema(obj, p)
            return obj
    raise KeyError(f"Pack not found: {pack_id}")