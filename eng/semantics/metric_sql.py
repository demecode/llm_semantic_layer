from typing import Any, Dict, Tuple


def _find_measure(semantic_model: Dict[str, Any], measure_name: str) -> Dict[str, Any]:
    for m in (semantic_model.get("measures") or []):
        if m.get("name") == measure_name:
            return m
    raise KeyError(f"Measure '{measure_name}' not found in semantic model '{semantic_model.get('name')}'")


def _resolve_relation(semantic_model: Dict[str, Any]) -> str:
    # Different dbt versions store this differently; try the common fields.
    return (
        semantic_model.get("relation_name")
        or semantic_model.get("model")          # sometimes a string-like ref
        or semantic_model.get("name")           # last resort
    )


def _resolve_timestamp_column(semantic_model: Dict[str, Any]) -> str:
    defaults = semantic_model.get("defaults") or {}
    # In your YAML you used agg_time_dimension: po_creation_date
    return defaults.get("agg_time_dimension") or "po_creation_date"


def build_metric_timeseries_sql(
    metric: Dict[str, Any],
    semantic_model: Dict[str, Any],
    params: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    """
    Build a time-series query for a SIMPLE metric.
    Params:
      - grain: day|month|quarter|year (default month)
      - start_date: YYYY-MM-DD (optional)
      - end_date: YYYY-MM-DD (optional)
    """
    metric_name = metric["name"]
    grain = (params.get("grain") or "month").lower()
    start_date = params.get("start_date")
    end_date = params.get("end_date")

    type_params = metric.get("type_params") or {}
    measure_name = type_params.get("measure")
    if not measure_name:
        raise ValueError(f"Metric '{metric_name}' missing type_params.measure")

    measure = _find_measure(semantic_model, measure_name)

    agg = (measure.get("agg") or "sum").lower()
    expr = measure.get("expr") or "value_in_gbp"

    relation = _resolve_relation(semantic_model)
    ts_col = _resolve_timestamp_column(semantic_model)

    where = []
    if metric.get("filter"):
        where.append(f"({metric['filter']})")
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
        "metric": metric_name,
        "grain": grain,
        "relation": relation,
        "timestamp_column": ts_col,
        "measure": measure_name,
    }
    return sql, meta