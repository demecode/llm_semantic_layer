'''
Docstring for api.eng.packs.execute_pack
	resolve defaults → build params (grain + start/end using your relative date helper)
	•	for each query: call your existing execute_metric(metric, params)
	•	assemble:
	•	series: array of timeseries by query
	•	kpis: computed from series
	•	narrative: fill template
'''

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from dateutil.relativedelta import relativedelta

from eng.semantics.execute_metric import execute_metric
from eng.semantics.dbt_semantics import load_metrics_semantic_models_and_nodes
from eng.semantics.metric_sql import normalize_measure_name, normalize_metric_filter_to_where_clauses
from eng.semantics.relation_resolver import resolve_semantic_model_relation
from eng.databricks_client import run_query
from eng.logger import logger


def _iso(d: date) -> str:
    return d.isoformat()



def _default_window_params(pack: Dict[str, Any]) -> Dict[str, Any]:
    defaults = pack.get("defaults") or {}
    grain = (defaults.get("grain") or "month").lower()

    window = defaults.get("window") or {}
    last_n_months = window.get("last_n_months")

    params: Dict[str, Any] = {"grain": grain}

    if last_n_months:
        today = date.today()

        if grain == "month":
            # exclude current partial month
            end = today.replace(day=1)  # first day of current month (exclusive end)
            start = end - relativedelta(months=int(last_n_months))
        else:
            # default behavior for non-month grains
            start = today - relativedelta(months=int(last_n_months))
            end = today + relativedelta(days=1)  # exclusive end

        params["start_date"] = _iso(start)
        params["end_date"] = _iso(end)

    return params

def _latest(rows: List[Dict[str, Any]]) -> Optional[float]:
    if not rows:
        return None
    v = rows[-1].get("value")
    try:
        return float(v)
    except Exception:
        return None


def _mom_pct(rows: List[Dict[str, Any]]) -> Optional[float]:
    if not rows or len(rows) < 2:
        return None
    try:
        prev = float(rows[-2]["value"])
        last = float(rows[-1]["value"])
    except Exception:
        return None
    if prev == 0:
        return None
    return ((last - prev) / prev) * 100.0


def _share_latest(left_rows: List[Dict[str, Any]], right_rows: List[Dict[str, Any]]) -> Optional[float]:
    left = _latest(left_rows)
    right = _latest(right_rows)
    if left is None or right is None:
        return None
    total = left + right
    if total == 0:
        return None
    return left / total


def _share_change_pp(left_rows: List[Dict[str, Any]], right_rows: List[Dict[str, Any]]) -> Optional[float]:
    if len(left_rows) < 2 or len(right_rows) < 2:
        return None

    def val(rows, idx):
        try:
            return float(rows[idx]["value"])
        except Exception:
            return None

    left_prev, left_last = val(left_rows, -2), val(left_rows, -1)
    right_prev, right_last = val(right_rows, -2), val(right_rows, -1)
    if None in (left_prev, left_last, right_prev, right_last):
        return None

    total_prev = left_prev + right_prev
    total_last = left_last + right_last
    if total_prev == 0 or total_last == 0:
        return None

    share_prev = left_prev / total_prev
    share_last = left_last / total_last
    return (share_last - share_prev) * 100.0  # percentage points


def _fmt_gbp(v: Optional[float]) -> str:
    if v is None:
        return "n/a"
    return f"£{v:,.0f}"


def _fmt_pct(v: Optional[float]) -> str:
    if v is None:
        return "n/a"
    return f"{v:+.1f}%"


def _fmt_share_pct(v: Optional[float]) -> str:
    if v is None:
        return "n/a"
    return f"{(v * 100):.1f}%"


def _fmt_pp(v: Optional[float]) -> str:
    if v is None:
        return "n/a"
    return f"{v:+.1f} pp"

def run_pack(pack: Dict[str, Any], overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    intent = (pack.get("intent") or "").lower()

    if intent == "ranking":
        return run_ranking_pack(pack, overrides)

    if intent == "comparison":
        return run_comparison_pack(pack, overrides)

    return {
        "error": f"Unsupported pack intent '{intent}'"
    }

def run_comparison_pack(pack: Dict[str, Any], overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:

    """
    Executes a comparison pack:
      - left_metric vs right_metric
      - returns ChatResponse-ish payload
    """
    params = _default_window_params(pack)
    if overrides:
        params.update({k: v for k, v in overrides.items() if v is not None})

    logger.info("PACK start %s params=%s", pack.get("id"), params)

    comp = pack.get("comparison") or {}
    left_metric = comp.get("left_metric")
    right_metric = comp.get("right_metric")
    if not left_metric or not right_metric:
        return {"error": "Pack missing comparison.left_metric/right_metric"}

    logger.info("PACK executing left_metric=%s", left_metric)
    left_result = execute_metric(left_metric, params)
    logger.info("PACK left_metric done rows=%s", len(left_result.get("rows") or []))

    if "error" in left_result:
        return {"error": left_result["error"]}

    logger.info("PACK executing right_metric=%s", right_metric)
    right_result = execute_metric(right_metric, params)
    logger.info("PACK right_metric done rows=%s", len(right_result.get("rows") or []))

    if "error" in right_result:
        return {"error": right_result["error"]}

    left_rows = left_result.get("rows") or []
    right_rows = right_result.get("rows") or []

    left_latest = _latest(left_rows)
    right_latest = _latest(right_rows)
    left_mom = _mom_pct(left_rows)
    right_mom = _mom_pct(right_rows)

    share_latest = _share_latest(left_rows, right_rows)
    share_pp = _share_change_pp(left_rows, right_rows)

    # Narrative
    template = ((pack.get("narrative") or {}).get("template") or "").strip()
    if not template:
        template = "In the latest period, Digital Solutions accounted for {left_share_latest_pct} of total company spend."

    answer = template.format(
        left_share_latest_pct=_fmt_share_pct(share_latest),
        left_mom_pct=_fmt_pct(left_mom),
        right_mom_pct=_fmt_pct(right_mom),
    )

    kpis = {
        "period_latest": "the latest period",
        "left_metric": left_metric,
        "right_metric": right_metric,
        "left_latest_gbp": left_latest or 0,
        "right_latest_gbp": right_latest or 0,
        "total_latest_gbp": (left_latest or 0) + (right_latest or 0),
        "left_share_latest": share_latest or 0,
        "left_share_latest_pct": _fmt_share_pct(share_latest),
        "left_share_change_pp": share_pp or 0,
        "left_share_change_pp_fmt": _fmt_pp(share_pp),
        "left_mom_change_pct": left_mom,
        "right_mom_change_pct": right_mom,
    }

    return {
        "pack_id": pack.get("id"),
        "answer": answer,
        "kpis": kpis,
        "series": [
            {"name": "Digital Solutions", "data": left_rows},
            {"name": "Rest of Company", "data": right_rows},
        ],
        "chart": {"type": "line", "x": "period", "y": "value", "unit": "GBP"},
        "meta": {
            "metrics": [left_metric, right_metric],
            "grain": params.get("grain"),
            "filters": {
                "start_date": params.get("start_date"),
                "end_date": params.get("end_date"),
            },
            # optional but useful if execute_metric includes it:
            "contracts": {
                "left": left_result.get("contract"),
                "right": right_result.get("contract"),
            },
        },
        "debug": {
            "params": params,
            "cache": {
                "left": left_result.get("cache"),
                "right": right_result.get("cache"),
            },
        },
    }

def _find_semantic_model_for_metric(metric_name: str):
    """
    Resolve the semantic model used by a metric by inspecting its base measure.
    Mirrors execute_metric() logic (simple/derived/ratio supported via base metric resolution).
    """
    metrics, semantic_models, nodes = load_metrics_semantic_models_and_nodes()
    metrics_by_name = {m.get("name"): m for m in metrics.values() if m.get("name")}

    metric = metrics_by_name.get(metric_name)
    if not metric:
        raise ValueError(f"Metric not found: {metric_name}")

    # Reuse your existing base-metric resolver if available
    # If not, simplest V1: assume 'simple' metrics for ranking
    metric_type = (metric.get("type") or "").lower()
    if metric_type != "simple":
        raise ValueError("V1 ranking only supports simple metrics (for now).")

    measure_obj = (metric.get("type_params") or {}).get("measure")
    measure_name = normalize_measure_name(measure_obj)
    if not measure_name:
        raise ValueError(f"Metric '{metric_name}' missing measure")

    chosen_sm = None
    for sm in semantic_models.values():
        for meas in sm.get("measures", []):
            if meas.get("name") == measure_name:
                chosen_sm = sm
                break
        if chosen_sm:
            break

    if not chosen_sm:
        raise ValueError(f"Could not resolve semantic model for metric '{metric_name}'")

    return metric, chosen_sm, nodes


def run_ranking_pack(pack: Dict[str, Any], overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Executes a ranking pack:
      - metric + dimension + window -> Top N
    Output is stable for UI: ranking rows + bar chart spec.
    """
    params = _default_window_params(pack)
    if overrides:
        params.update({k: v for k, v in overrides.items() if v is not None})

    grain = (params.get("grain") or "month").lower()

    ranking = pack.get("ranking") or {}
    metric_name = (params.get("metric") or ranking.get("metric") or "").strip()
    dimension_name = (params.get("dimension") or ranking.get("dimension") or "").strip()

    # default N: pack.defaults.n or 10
    defaults = pack.get("defaults") or {}
    n = int(params.get("n") or defaults.get("n") or ranking.get("n") or 10)

    if not metric_name:
        return {"error": "Ranking pack missing metric (ranking.metric)"}
    if not dimension_name:
        return {"error": "Ranking pack missing dimension (ranking.dimension)"}

    logger.info("PACK start %s intent=ranking params=%s", pack.get("id"), params)
    logger.info("PACK ranking metric=%s dimension=%s n=%s", metric_name, dimension_name, n)

    try:
        metric, semantic_model, nodes = _find_semantic_model_for_metric(metric_name)
    except Exception as e:
        return {"error": str(e)}

    # Validate dimension exists on semantic model
    dims = semantic_model.get("dimensions", []) or []
    dim_obj = next((d for d in dims if d.get("name") == dimension_name), None)
    if not dim_obj:
        allowed = [d.get("name") for d in dims if d.get("name")]
        return {"error": f"Dimension '{dimension_name}' not found on semantic model '{semantic_model.get('name')}'. Allowed: {allowed}"}

    # Dimension expression
    dim_expr = dim_obj.get("expr") or dim_obj.get("name")

    # Measure expression
    measure_obj = (metric.get("type_params") or {}).get("measure")
    measure_name = normalize_measure_name(measure_obj)
    meas_obj = next((m for m in (semantic_model.get("measures") or []) if m.get("name") == measure_name), None)
    if not meas_obj:
        return {"error": f"Measure '{measure_name}' not found on semantic model '{semantic_model.get('name')}'"}

    agg = meas_obj.get("agg")   # e.g. sum
    expr = meas_obj.get("expr") # e.g. value_in_gbp

    relation = resolve_semantic_model_relation(semantic_model, nodes)

    ts_col = (
        (semantic_model.get("defaults") or {}).get("agg_time_dimension")
        or "po_creation_date"
    )

    grain = (params.get("grain") or "month").lower()
    start_date = params.get("start_date")
    end_date = params.get("end_date")

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
      {dim_expr} AS label,
      {agg}({expr}) AS value
    FROM {relation}
    {where_sql}
    GROUP BY label
    ORDER BY value DESC
    LIMIT {n}
    """.strip()

    logger.info("PACK ranking sql=%s", sql.replace("\n", " "))

    # Execute
    t0 = time.time()
    try:
        rows = run_query(sql)
    except Exception as e:
        return {"error": f"Ranking query failed: {e}"}
    finally:
        logger.info("PACK ranking done elapsed_s=%.2f rows=%s", time.time() - t0, len(rows or []))

    ranking_rows = [
        {"label": r.get("label"), "value": float(r.get("value") or 0.0)}
        for r in (rows or [])
    ]

    answer = f"Top {n} {dimension_name.replace('_',' ')} by {metric_name.replace('_',' ')}."

    return {
        "pack_id": pack.get("id"),
        "answer": answer,
        "ranking": ranking_rows,
        "chart": {"type": "bar", "x": "label", "y": "value", "unit": "GBP"},
        "meta": {
            "metric": metric_name,
            "dimension": dimension_name,
            "grain": grain,
            "filters": {"start_date": start_date, "end_date": end_date},
            "relation": relation,
            "timestamp_column": ts_col,
        },
        "debug": {"sql": sql},
    }