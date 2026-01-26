from typing import Any, Dict
from eng.semantics.dbt_semantics import load_metrics_semantic_models_and_nodes
from eng.semantics.metric_sql import build_metric_timeseries_sql, normalize_measure_name
from eng.databricks_client import run_query

from eng.cache import get as cache_get, set as cache_set
from eng.semantics.manifest_utils import manifest_hash
import concurrent.futures
import time

import logging
import concurrent.futures
import time

logger = logging.getLogger("copilot")
logger.setLevel(logging.INFO)
logger.propagate = True




def _resolve_base_metric(
    metric: Dict[str, Any],
    metrics_by_name: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Resolve the underlying SIMPLE metric that determines the semantic model.
    Works recursively for derived / ratio metrics.
    """
    metric_type = (metric.get("type") or "").lower()

    if metric_type == "simple":
        return metric

    type_params = metric.get("type_params") or {}

    if metric_type == "derived":
        refs = type_params.get("metrics") or []
        if not refs:
            raise ValueError(f"Derived metric '{metric.get('name')}' has no base metrics")

        ref = refs[0]
        ref_name = ref.get("name") if isinstance(ref, dict) else ref
        base_metric = metrics_by_name.get(ref_name)
        if not base_metric:
            raise ValueError(f"Unknown base metric '{ref_name}'")
        return _resolve_base_metric(base_metric, metrics_by_name)

    if metric_type == "ratio":
        num = type_params.get("numerator")
        ref_name = num.get("name") if isinstance(num, dict) else num
        base_metric = metrics_by_name.get(ref_name)
        if not base_metric:
            raise ValueError(f"Unknown numerator metric '{ref_name}'")
        return _resolve_base_metric(base_metric, metrics_by_name)

    raise ValueError(f"Unsupported metric type '{metric_type}'")


def _rows_to_map(rows):
    """
    Map rows -> period(str) -> value(float)
    """
    out = {}
    for r in rows or []:
        p = r.get("period")
        if p is None:
            continue
        out[str(p)] = float(r.get("value") or 0.0)
    return out



def run_with_timeout(fn, timeout_s=60):
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(fn)
        return fut.result(timeout=timeout_s)

def execute_metric(metric_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    mh = manifest_hash()

    cache_payload = {"metric": metric_name, "params": params, "manifest_hash": mh}
    cached = cache_get(cache_payload)
    if cached:
        cached_out = dict(cached)
        cached_out["cache"] = {"cached": True}
        return cached_out

    metrics, semantic_models, nodes = load_metrics_semantic_models_and_nodes()
    metrics_by_name = {m.get("name"): m for m in metrics.values() if m.get("name")}

    metric = metrics_by_name.get(metric_name)
    if not metric:
        return {"error": f"Metric not found: {metric_name}"}

    metric_type = (metric.get("type") or "").lower()

    # --- Resolve semantic model via BASE simple metric (works for simple/derived/ratio) ---
    try:
        base_metric = _resolve_base_metric(metric, metrics_by_name)
    except Exception as e:
        return {"error": str(e)}

    base_measure_obj = (base_metric.get("type_params") or {}).get("measure")
    base_measure_name = normalize_measure_name(base_measure_obj)

    chosen_sm = None
    for sm in semantic_models.values():
        for meas in sm.get("measures", []):
            if meas.get("name") == base_measure_name:
                chosen_sm = sm
                break
        if chosen_sm:
            break

    if not chosen_sm:
        return {"error": f"Could not resolve semantic model for metric '{metric_name}'"}

    # ------------------------
    # DERIVED: first metric minus the rest (covers rest_of_company_spend)
    # ------------------------
    if metric_type == "derived":
        tp = metric.get("type_params") or {}
        refs = tp.get("metrics") or []
        if len(refs) < 2:
            return {"error": f"Derived metric '{metric_name}' must reference >= 2 metrics"}

        ref_names = [
            r.get("name") if isinstance(r, dict) else r
            for r in refs
        ]

        # Execute each referenced metric with same params
        results = []
        for rn in ref_names:
            res = execute_metric(rn, params)
            if "error" in res:
                return {"error": f"Derived component '{rn}' failed: {res['error']}"}
            results.append(res)

        # Align by period
        maps = [_rows_to_map(r.get("rows")) for r in results]

        
        periods = sorted(set().union(*[set(m.keys()) for m in maps]))

        rows = []
        for p in periods:
            base_val = maps[0].get(p, 0.0)
            sub_val = sum(m.get(p, 0.0) for m in maps[1:])
            rows.append({"period": p, "value": base_val - sub_val})

        # Use relation/timestamp from first component meta if present
        meta0 = results[0].get("meta") or {}
        meta = {
            "metric": metric_name,
            "relation": meta0.get("relation"),
            "grain": params.get("grain", "month"),
            "timestamp_column": meta0.get("timestamp_column"),
            "type": "derived",
            "components": ref_names,
            "expression": "first_minus_rest",
        }

        contract = {
            "metric": metric_name,
            "metric_type": metric_type,
            "semantic_model": chosen_sm.get("name"),
            "measure": None,
            "grain": meta.get("grain"),
            "timestamp_column": meta.get("timestamp_column"),
            "relation": meta.get("relation"),
            "manifest_hash": mh,
        }

        out = {"meta": meta, "sql": None, "rows": rows, "contract": contract}
        cache_set(cache_payload, out, ttl_seconds=300)
        out["cache"] = {"cached": False}
        return out

    # ------------------------
    # RATIO: (keep your ratio handler from earlier if you added it)
    # ------------------------
    # ... your ratio block here ...

    # ------------------------
    # SIMPLE (and any others that compile to SQL directly)
    # ------------------------
    # sql, meta = build_metric_timeseries_sql(metric, chosen_sm, nodes, params, metrics_by_name)
    # rows = run_query(sql)

    sql, meta = build_metric_timeseries_sql(metric, chosen_sm, nodes, params, metrics_by_name)

    timeout_s = int(params.get("timeout_s") or 60)

    def _exec():
        return run_query(sql)

    logger.info("METRIC start name=%s type=%s timeout_s=%s", metric_name, metric_type, timeout_s)
    logger.info("METRIC sql name=%s sql=%s", metric_name, sql)

    t0 = time.time()
    try:
        rows = run_with_timeout(_exec, timeout_s=timeout_s)
    except concurrent.futures.TimeoutError:
        return {
            "error": (
                f"Databricks query timed out after {timeout_s}s for metric '{metric_name}'. "
                "Warehouse may be cold/suspended or query may be slow. "
                "Try reducing the time window or increasing warehouse size."
            )
        }
    except Exception as e:
        return {"error": f"Databricks query failed for metric '{metric_name}': {e}"}
    finally:
        logger.info("METRIC end name=%s elapsed_s=%.2f", metric_name, time.time() - t0)

    contract = {
        "metric": metric_name,
        "metric_type": metric_type,
        "semantic_model": chosen_sm.get("name"),
        "measure": base_measure_name,
        "grain": meta.get("grain"),
        "timestamp_column": meta.get("timestamp_column"),
        "relation": meta.get("relation"),
        "manifest_hash": mh,
    }

    out = {"meta": meta, "sql": sql, "rows": rows, "contract": contract}
    cache_set(cache_payload, out, ttl_seconds=300)
    out["cache"] = {"cached": False}
    return out