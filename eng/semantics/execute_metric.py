from typing import Any, Dict, Optional
from eng.semantics.dbt_semantics import load_metrics_semantic_models_and_nodes
from eng.semantics.metric_sql import build_metric_timeseries_sql, normalize_measure_name
from eng.databricks_client import run_query


def execute_metric(metric_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    metrics, semantic_models, nodes = load_metrics_semantic_models_and_nodes()

    metric = next((m for m in metrics.values() if m.get("name") == metric_name), None)
    if not metric:
        return {"error": f"Metric not found: {metric_name}"}

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

    sql, meta = build_metric_timeseries_sql(metric, chosen_sm, nodes, params, metrics_by_name)
    rows = run_query(sql)

    return {"meta": meta, "sql": sql, "rows": rows}