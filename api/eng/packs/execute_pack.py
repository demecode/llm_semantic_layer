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

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from dateutil.relativedelta import relativedelta

from eng.semantics.execute_metric import execute_metric


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
    """
    Executes a comparison pack:
      - left_metric vs right_metric
      - returns ChatResponse-ish payload
    """
    params = _default_window_params(pack)
    if overrides:
        params.update({k: v for k, v in overrides.items() if v is not None})

    comp = pack.get("comparison") or {}
    left_metric = comp.get("left_metric")
    right_metric = comp.get("right_metric")
    if not left_metric or not right_metric:
        return {"error": "Pack missing comparison.left_metric/right_metric"}

    left_result = execute_metric(left_metric, params)
    if "error" in left_result:
        return {"error": left_result["error"]}

    right_result = execute_metric(right_metric, params)
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
        "answer": answer,
        "kpis": kpis,
        "series": [
            {"name": "Digital Solutions", "data": left_rows},
            {"name": "Rest of Company", "data": right_rows},
        ],
        "chart": {"type": "line", "x": "period", "y": "value", "unit": "GBP"},
        "debug": {
            "pack_id": pack.get("id"),
            "params": params,
            "left_contract": left_result.get("contract"),
            "right_contract": right_result.get("contract"),
            "cache": {
                "left": left_result.get("cache"),
                "right": right_result.get("cache"),
            },
        },
    }