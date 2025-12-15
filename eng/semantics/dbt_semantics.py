import json
from pathlib import Path
from typing import Any, Dict, Tuple


def load_manifest() -> Dict[str, Any]:
    return json.loads(Path(DBT_MANIFEST_PATH).read_text(encoding="utf-8"))


def load_metrics_and_semantic_models() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    m = load_manifest()
    metrics = m.get("metrics") or {}
    semantic_models = m.get("semantic_models") or {}
    return metrics, semantic_models


def list_metrics(manifest_path: str = "target/manifest.json"):
    metrics, _ = load_metrics_and_semantic_models(manifest_path)
    out = []
    for _id, metric in metrics.items():
        out.append({
            "name": metric.get("name"),
            "label": metric.get("label"),
            "description": metric.get("description", ""),
            "type": metric.get("type"),
            "type_params": metric.get("type_params", {}),
            "filter": metric.get("filter"),
            "time_grains": metric.get("time_grains", []),
        })
    out = [m for m in out if m["name"]]
    out.sort(key=lambda x: x["name"])
    return 



import os
import json
from pathlib import Path

DBT_MANIFEST_PATH = os.getenv(
    "DBT_MANIFEST_PATH",
    "../llm_co/target/manifest.json",  # safe default
)

def load_manifest():
    return json.loads(
        Path(DBT_MANIFEST_PATH).read_text(encoding="utf-8")
    )