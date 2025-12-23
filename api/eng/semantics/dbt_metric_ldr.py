import json
from pathlib import Path
from typing import Any, Dict

_DEFAULT_MANIFEST = Path(__file__).resolve().parents[3] / "dbt" / "target" / "manifest.json"


def load_dbt_metrics(manifest_path: str | Path = _DEFAULT_MANIFEST) -> Dict[str, Dict[str, Any]]:
    """
    Returns a dict keyed by metric name.
    Metric objects come from dbt's manifest.json "metrics" section.
    """
    manifest_path = Path(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    metrics: Dict[str, Dict[str, Any]] = {}
    for metric_id, metric in (manifest.get("metrics") or {}).items():
        name = metric.get("name")
        if not name:
            continue

        metrics[name] = {
            "name": name,
            "label": metric.get("label", name),
            "description": metric.get("description", ""),
            "type": metric.get("type"),
            "type_params": metric.get("type_params", {}) or {},
            "filter": metric.get("filter"),
            "time_grains": metric.get("time_grains", []),
            # model is often stored as a reference to semantic model / ref;
            # we'll resolve the base relation using semantic_models below.
            "semantic_model": metric.get("model"),
        }

    # Also load semantic_models so we can resolve measures → expressions + timestamp column
    semantic_models = {}
    for sm_id, sm in (manifest.get("semantic_models") or {}).items():
        semantic_models[sm.get("name")] = sm

    return metrics, semantic_models
