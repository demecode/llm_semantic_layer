from typing import Any, Dict
from eng.semantics.dbt_semantics import load_metrics_semantic_models_and_nodes
from eng.semantics.metric_sql import build_metric_timeseries_sql, normalize_measure_name
from eng.databricks_client import run_query

from eng.cache import get as cache_get, set as cache_set
from eng.semantics.manifest_utils import manifest_hash


def _resolve_base_metric(
    metric: Dict[str, Any],
    metrics_by_name: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Resolve the underlying SIMPLE metric that determines the semantic model.
    Works recursively for derived / ratio metrics.
    """
    metric_type = metric.get("type")

    # Simple metrics resolve directly
    if metric_type == "simple":
        return metric

    type_params = metric.get("type_params") or {}

    # Derived: use first referenced metric
    if metric_type == "derived":
        refs = type_params.get("metrics") or []
        if not refs:
            raise ValueError(f"Derived metric '{metric['name']}' has no base metrics")

        ref = refs[0]
        ref_name = ref.get("name") if isinstance(ref, dict) else ref
        base_metric = metrics_by_name.get(ref_name)
        if not base_metric:
            raise ValueError(f"Unknown base metric '{ref_name}'")

        return _resolve_base_metric(base_metric, metrics_by_name)

    # Ratio: use numerator
    if metric_type == "ratio":
        num = type_params.get("numerator")
        ref_name = num.get("name") if isinstance(num, dict) else num
        base_metric = metrics_by_name.get(ref_name)
        if not base_metric:
            raise ValueError(f"Unknown numerator metric '{ref_name}'")

        return _resolve_base_metric(base_metric, metrics_by_name)

    raise ValueError(f"Unsupported metric type '{metric_type}'")

def execute_metric(metric_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    mh = manifest_hash()

    cache_payload = {
        "metric": metric_name,
        "params": params,
        "manifest_hash": mh,
    }
    cached = cache_get(cache_payload)
    if cached:
        # attach cache metadata but return same result structure
        cached_out = dict(cached)
        cached_out["cache"] = {"cached": True}
        return cached_out

    metrics, semantic_models, nodes = load_metrics_semantic_models_and_nodes()

    metric = next((m for m in metrics.values() if m.get("name") == metric_name), None)
    if not metric:
        return {"error": f"Metric not found: {metric_name}"}
    metrics_by_name = {m.get("name"): m for m in metrics.values() if m.get("name")}

    measure_obj = (metric.get("type_params") or {}).get("measure")
    measure_name = normalize_measure_name(measure_obj)

    chosen_sm = None
    for sm in semantic_models.values():
        for meas in sm.get("measures", []):
            if meas.get("name") == measure_name:
                chosen_sm = sm
                break
        if chosen_sm:
            break

    if not chosen_sm:
        return {"error": f"Could not resolve semantic model for metric '{metric_name}'"}

    metrics_by_name = {m.get("name"): m for m in metrics.values() if m.get("name")}
    sql, meta = build_metric_timeseries_sql(metric, chosen_sm, nodes, params, metrics_by_name)
    rows = run_query(sql)

    contract = {
        "metric": metric_name,
        "metric_type": metric.get("type"),
        "semantic_model": chosen_sm.get("name"),
        "measure": measure_name,
        "grain": meta.get("grain"),
        "timestamp_column": meta.get("timestamp_column"),
        "relation": meta.get("relation"),
        "manifest_hash": mh,
    }

    out = {"meta": meta, "sql": sql, "rows": rows, "contract": contract}
    cache_set(cache_payload, out, ttl_seconds=300)

    out["cache"] = {"cached": False}
    return out


# def execute_metric(metric_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
#     print(">>> execute_metric called with:", metric_name, params)
#     metrics, semantic_models, nodes = load_metrics_semantic_models_and_nodes()

#     metrics_by_name = {
#         m.get("name"): m
#         for m in metrics.values()
#         if m.get("name")
#     }

#     metric = metrics_by_name.get(metric_name)
#     if not metric:
#         return {"error": f"Metric not found: {metric_name}"}

#     # ---- Resolve base SIMPLE metric for semantic model ----
#     try:
#         base_metric = _resolve_base_metric(metric, metrics_by_name)
#     except Exception as e:
#         return {"error": str(e)}

#     measure_obj = (base_metric.get("type_params") or {}).get("measure")
#     measure_name = normalize_measure_name(measure_obj)

#     # ---- Resolve semantic model from base metric ----
#     chosen_sm = None
#     for sm in semantic_models.values():
#         for meas in sm.get("measures", []):
#             if meas.get("name") == measure_name:
#                 chosen_sm = sm
#                 break
#         if chosen_sm:
#             break

#     if not chosen_sm:
#         return {"error": f"Could not resolve semantic model for metric '{metric_name}'"}

#     # ---- Build SQL (supports simple / derived / ratio) ----
#     sql, meta = build_metric_timeseries_sql(
#         metric=metric,
#         semantic_model=chosen_sm,
#         nodes=nodes,
#         params=params,
#         metrics_by_name=metrics_by_name,
#     )

#     rows = run_query(sql)

#     return {
#         "meta": meta,
#         "sql": sql,
#         "rows": rows,
#     }
