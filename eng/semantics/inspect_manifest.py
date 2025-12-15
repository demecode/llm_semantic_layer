import json
from pathlib import Path
from typing import Any, Dict


def inspect_manifest(manifest_path: str = "target/manifest.json") -> Dict[str, Any]:
    m = json.loads(Path(manifest_path).read_text(encoding="utf-8"))

    metrics = m.get("metrics") or {}
    semantic_models = m.get("semantic_models") or {}

    sample_metric = next(iter(metrics.values()), None)
    sample_sm = next(iter(semantic_models.values()), None)

    def keys(o: Any):
        return sorted(list(o.keys())) if isinstance(o, dict) else []

    return {
        "has_metrics": bool(metrics),
        "has_semantic_models": bool(semantic_models),
        "metrics_count": len(metrics),
        "semantic_models_count": len(semantic_models),
        "sample_metric_keys": keys(sample_metric) if sample_metric else [],
        "sample_semantic_model_keys": keys(sample_sm) if sample_sm else [],
        "sample_semantic_model_name": sample_sm.get("name") if isinstance(sample_sm, dict) else None,
        "sample_metric_name": sample_metric.get("name") if isinstance(sample_metric, dict) else None,
    }