import json
import os
from pathlib import Path
from typing import Any, Dict, Tuple

DBT_MANIFEST_PATH = os.getenv("DBT_MANIFEST_PATH", "../llm_co/target/manifest.json")


def load_manifest() -> Dict[str, Any]:
    return json.loads(Path(DBT_MANIFEST_PATH).read_text(encoding="utf-8"))


def load_metrics_semantic_models_and_nodes() -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    m = load_manifest()
    metrics = m.get("metrics") or {}
    semantic_models = m.get("semantic_models") or {}
    nodes = m.get("nodes") or {}
    return metrics, semantic_models, nodes


from typing import Any, Dict, List

def list_metrics() -> List[Dict[str, Any]]:
    metrics, _, _ = load_metrics_semantic_models_and_nodes()

    out = []
    for m in metrics.values():
        out.append({
            "name": m.get("name"),
            "label": m.get("label"),
            "description": m.get("description", ""),
            "type": m.get("type"),
            "time_grains": m.get("time_grains", []),
            "filter": m.get("filter"),
        })

    out = [x for x in out if x["name"]]
    out.sort(key=lambda x: x["name"])
    return out
