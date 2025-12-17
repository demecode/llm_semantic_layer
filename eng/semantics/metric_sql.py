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


from typing import Any, Dict, Tuple

def _metric_name(m: Any) -> str:
    # sometimes metric refs are strings, sometimes dicts
    if isinstance(m, str):
        return m
    if isinstance(m, dict):
        return m.get("name")
    return ""

def _safe_alias(s: str) -> str:
    return "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in s)

def _base_where_clauses(ts_col: str, params: Dict[str, Any]) -> list[str]:
    where = []
    start_date = params.get("start_date")
    end_date = params.get("end_date")
    if start_date:
        where.append(f"{ts_col} >= DATE('{start_date}')")
    if end_date:
        where.append(f"{ts_col} < DATE('{end_date}')")
    return where


def build_metric_timeseries_sql(
    metric: Dict[str, Any],
    semantic_model: Dict[str, Any],
    nodes: Dict[str, Any],
    params: Dict[str, Any],
    metrics_by_name: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:

    metric_type = (metric.get("type") or "").lower()
    grain = (params.get("grain") or "month").lower()

    # --- resolve semantic model → physical relation ---
    relation = resolve_semantic_model_relation(semantic_model, nodes)

    # --- resolve timestamp ---
    ts_col = (
        (semantic_model.get("defaults") or {}).get("agg_time_dimension")
        or "po_creation_date"
    )

    def build_simple_sql(m: Dict[str, Any], cte_name: str) -> str:
        """Build a CTE that returns (period, value) for a simple metric."""
        measure_obj = (m.get("type_params") or {}).get("measure")
        measure_name = normalize_measure_name(measure_obj)
        if not measure_name:
            raise ValueError(f"Metric '{m.get('name')}' missing measure")

        measure = next(x for x in semantic_model["measures"] if x["name"] == measure_name)
        agg = measure["agg"]
        expr = measure["expr"]

        where = []
        for clause in normalize_metric_filter_to_where_clauses(m.get("filter")):
            where.append(f"({clause})")
        where.extend(_base_where_clauses(ts_col, params))
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""

        return f"""
        {cte_name} AS (
          SELECT
            date_trunc('{grain}', {ts_col}) AS period,
            {agg}({expr}) AS value
          FROM {relation}
          {where_sql}
          GROUP BY period
        )
        """.strip()

    # -------------------------
    # SIMPLE
    # -------------------------
    if metric_type == "simple":
        sql = build_simple_sql(metric, "m")
        final = """
        WITH
        {cte}
        SELECT period, value
        FROM m
        ORDER BY period
        """.format(cte=sql).strip()

        meta = {
            "metric": metric["name"],
            "type": metric_type,
            "relation": relation,
            "grain": grain,
            "timestamp_column": ts_col,
        }
        return final, meta

    # -------------------------
    # RATIO
    # -------------------------
    if metric_type == "ratio":
        tp = metric.get("type_params") or {}
        num_name = _metric_name(tp.get("numerator"))
        den_name = _metric_name(tp.get("denominator"))

        if not num_name or not den_name:
            raise ValueError(f"Ratio metric '{metric.get('name')}' missing numerator/denominator")

        num_metric = metrics_by_name.get(num_name)
        den_metric = metrics_by_name.get(den_name)
        if not num_metric or not den_metric:
            raise ValueError(f"Ratio metric '{metric.get('name')}' references unknown metrics")

        if (num_metric.get("type") or "").lower() != "simple" or (den_metric.get("type") or "").lower() != "simple":
            raise ValueError("For MVP, ratio numerator/denominator must be simple metrics")

        cte_num = build_simple_sql(num_metric, "num")
        cte_den = build_simple_sql(den_metric, "den")

        final = f"""
        WITH
        {cte_num},
        {cte_den}
        SELECT
          COALESCE(num.period, den.period) AS period,
          CASE
            WHEN den.value IS NULL OR den.value = 0 THEN NULL
            ELSE num.value / den.value
          END AS value
        FROM num
        FULL OUTER JOIN den
          ON num.period = den.period
        ORDER BY period
        """.strip()

        meta = {
            "metric": metric["name"],
            "type": metric_type,
            "numerator": num_name,
            "denominator": den_name,
            "relation": relation,
            "grain": grain,
            "timestamp_column": ts_col,
            "unit": "ratio",
        }
        return final, meta

    # -------------------------
    # DERIVED
    # -------------------------
    if metric_type == "derived":
        tp = metric.get("type_params") or {}
        expr = tp.get("expr")
        refs = tp.get("metrics") or []

        if not expr or not refs:
            raise ValueError(f"Derived metric '{metric.get('name')}' missing expr/metrics")

        # Build CTE per referenced metric alias
        ctes = []
        aliases = {}
        for ref in refs:
            ref_name = _metric_name(ref.get("name") if isinstance(ref, dict) else ref)
            alias = (ref.get("alias") if isinstance(ref, dict) else None) or ref_name
            alias = _safe_alias(alias)

            base_metric = metrics_by_name.get(ref_name)
            if not base_metric:
                raise ValueError(f"Derived metric '{metric.get('name')}' references unknown metric '{ref_name}'")
            if (base_metric.get("type") or "").lower() != "simple":
                raise ValueError("For MVP, derived inputs must be simple metrics")

            ctes.append(build_simple_sql(base_metric, alias))
            aliases[alias] = alias  # track for join

        # Build join using FULL OUTER JOIN across all aliases on period
        alias_list = list(aliases.keys())
        first = alias_list[0]

        join_sql = f"FROM {first}\n"
        for a in alias_list[1:]:
            join_sql += f"FULL OUTER JOIN {a} ON {a}.period = {first}.period\n"

        # Create a stable period selector
        period_expr = "COALESCE(" + ", ".join([f"{a}.period" for a in alias_list]) + ")"

        # expr uses aliases like total/ds; we ensured CTE names match alias
        derived_value_expr = expr
        for a in alias_list:
            derived_value_expr = derived_value_expr.replace(a, f"{a}.value")

        final = f"""
        WITH
        {',\n'.join(ctes)}
        SELECT
          {period_expr} AS period,
          {derived_value_expr} AS value
        {join_sql}
        ORDER BY period
        """.strip()

        meta = {
            "metric": metric["name"],
            "type": metric_type,
            "relation": relation,
            "grain": grain,
            "timestamp_column": ts_col,
            "derived_expr": expr,
            "inputs": alias_list,
        }
        return final, meta

    raise ValueError(f"Unsupported metric type: {metric_type}")