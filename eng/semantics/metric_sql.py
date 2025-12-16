from typing import Any, Dict, List, Optional, Tuple

from eng.semantics.relation_resolver import resolve_semantic_model_relation


def normalize_measure_name(measure: Any) -> Optional[str]:
    if measure is None:
        return None
    if isinstance(measure, str):
        return measure
    if isinstance(measure, dict):
        return measure.get("name")
    return None


def normalize_metric_filter_to_where_clauses(metric_filter: Any) -> List[str]:
    """
    dbt metric 'filter' can be None, a string, or a dict with where_filters.
    Return a list of SQL WHERE clauses (strings).
    """
    if not metric_filter:
        return []

    if isinstance(metric_filter, str):
        return [metric_filter]

    if isinstance(metric_filter, dict):
        where_filters = metric_filter.get("where_filters") or []
        clauses = []
        for wf in where_filters:
            tmpl = (wf or {}).get("where_sql_template")
            if tmpl:
                clauses.append(tmpl)
        return clauses

    return []


def build_metric_timeseries_sql(
    metric: Dict[str, Any],
    semantic_model: Dict[str, Any],
    nodes: Dict[str, Any],
    params: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:

    grain = (params.get("grain") or "month").lower()
    start_date = params.get("start_date")
    end_date = params.get("end_date")

    # --- resolve measure ---
    measure_obj = (metric.get("type_params") or {}).get("measure")
    measure_name = normalize_measure_name(measure_obj)
    if not measure_name:
        raise ValueError(f"Metric '{metric['name']}' missing measure")

    # --- resolve semantic model → physical relation ---
    relation = resolve_semantic_model_relation(semantic_model, nodes)

    # --- resolve timestamp ---
    ts_col = (
        (semantic_model.get("defaults") or {}).get("agg_time_dimension")
        or "po_creation_date"
    )

    # --- resolve measure expression ---
    measure = next(
        m for m in semantic_model["measures"] if m["name"] == measure_name
    )
    agg = measure["agg"]
    expr = measure["expr"]

    where = []
    for clause in normalize_metric_filter_to_where_clauses(metric.get("filter")):
        where.append(f"({clause})")
    if start_date:
        where.append(f"{ts_col} >= DATE('{start_date}')")
    if end_date:
        where.append(f"{ts_col} < DATE('{end_date}')")

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    sql = f"""
    SELECT
      date_trunc('{grain}', {ts_col}) AS period,
      {agg}({expr}) AS value
    FROM {relation}
    {where_sql}
    GROUP BY period
    ORDER BY period
    """.strip()

    meta = {
        "metric": metric["name"],
        "relation": relation,
        "grain": grain,
        "timestamp_column": ts_col,
        "measure": measure_name,
    }

    return sql, meta
