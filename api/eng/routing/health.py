from fastapi import APIRouter
from pathlib import Path
import requests

from eng.config import DBT_MANIFEST_PATH, OLLAMA_HOST, MODEL_NAME
from eng.semantics.dbt_semantics import list_metrics

router = APIRouter()

@router.get("/health")
def health():
    out = {"ok": True, "checks": {}}

    # dbt manifest + metrics
    p = Path(DBT_MANIFEST_PATH)
    out["checks"]["dbt_manifest_path"] = str(p)
    out["checks"]["dbt_manifest_exists"] = p.exists()

    if p.exists():
        try:
            ms = list_metrics()
            out["checks"]["dbt_metrics_count"] = len(ms)
        except Exception as e:
            out["ok"] = False
            out["checks"]["dbt_error"] = str(e)
    else:
        out["ok"] = False

    #  ollama 
    out["checks"]["ollama_host"] = OLLAMA_HOST
    out["checks"]["ollama_model"] = MODEL_NAME
    try:
        tags = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        tags.raise_for_status()
        payload = tags.json()

        names = [m.get("name") for m in (payload.get("models") or []) if m.get("name")]
        out["checks"]["ollama_up"] = True
        out["checks"]["ollama_models_sample"] = names[:10]
        out["checks"]["ollama_has_model"] = any(MODEL_NAME == n for n in names)
        if not out["checks"]["ollama_has_model"]:
            out["ok"] = False
    except Exception as e:
        out["ok"] = False
        out["checks"]["ollama_up"] = False
        out["checks"]["ollama_error"] = str(e)

    return out