from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import date, time

from eng.routing.route_with_ollama import route_with_ollama
from eng.logger import logger
from eng.semantics.dbt_semantics import (
    load_manifest,
    load_metrics_semantic_models_and_nodes,
    list_metrics,
)
from eng.presentation.summaries import summarise_timeseries
from eng.utils.date_ranges import apply_relative_date_filters
from eng.databricks_client import run_query
from eng.semantics.dbt_semantics import list_semantic_models



app = FastAPI(title="LLM x1")

from eng.routing.health import router as health_router
app.include_router(health_router)

class TimeSeriesPoint(BaseModel):
    month: str
    digital_solutions_spend_gbp: float
    total_spend_gbp: float


class KpiResponse(BaseModel):
    sql: str
    points: List[TimeSeriesPoint]
    total_digital_solutions_spend_gbp: float
    total_spend_gbp: float


class VendorSpend(BaseModel):
    vendor_name: str
    total_spend_gbp: float


class VendorKpiResponse(BaseModel):
    sql: str
    vendors: List[VendorSpend]


@app.get("/health")
def health():
    return {"status": "ok"}



@app.get("/semantic-models")
def semantic_models():
    return {
        "semantic_models": list_semantic_models()
    }

@app.get("/kpi/digital-solutions-spend-vs-total", response_model=KpiResponse)
def digital_solutions_spend_vs_total(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
):
    date_filter = ""
    if start_date:
        date_filter += f" AND po_creation_date >= DATE('{start_date}')"
    if end_date:
        date_filter += f" AND po_creation_date < DATE('{end_date}')"
    # Build final SQL with optional date filters
    sql = f"""
    SELECT
        date_trunc('month', po_creation_date) AS month,
        SUM(CASE WHEN line_of_business = 'Digital Solutions'
                 THEN value_in_gbp ELSE 0 END) AS digital_solutions_spend_gbp,
        SUM(value_in_gbp) AS total_spend_gbp
    FROM `llm-v1`.analytics.fct_po_spend
    WHERE 1=1{date_filter}
    GROUP BY date_trunc('month', po_creation_date)
    ORDER BY month;
    """

    rows = run_query(sql)

    # Build time series points
    points: List[TimeSeriesPoint] = [
        TimeSeriesPoint(
            month=str(row["month"]),
            digital_solutions_spend_gbp=float(row["digital_solutions_spend_gbp"] or 0),
            total_spend_gbp=float(row["total_spend_gbp"] or 0),
        )
        for row in rows
    ]

    total_digital = sum(p.digital_solutions_spend_gbp for p in points)
    total_all = sum(p.total_spend_gbp for p in points)

    return KpiResponse(
        sql=sql,
        points=points,
        total_digital_solutions_spend_gbp=total_digital,
        total_spend_gbp=total_all,
    )

class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str
    kpis: Optional[Dict[str, Any]] = None
    series: Optional[List[Dict[str, Any]]] = None
    chart: Optional[Dict[str, Any]] = None
    meta: Optional[Dict[str, Any]] = None
    data: Optional[List[Dict[str, Any]]] = None


from eng.semantics.execute_metric import execute_metric
from eng.semantics.dbt_semantics import list_metrics

def _unit_for_metric_type(metric_type: str) -> str:
    t = (metric_type or "").lower()
    return "PERCENT" if t == "ratio" else "GBP"

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    print("🔥 CHAT ENDPOINT HIT 🔥")
    q = req.question
    logger.info("CHAT HIT question=%r", q)
    routing = route_with_ollama(q)
    logger.info("CHAT routing=%s", routing)

    intent = routing.get("intent", "unknown")
    params = routing.get("params", {}) or {}
    params = apply_relative_date_filters(q, params)
    logger.info(f"/chat final_params={params}")
    routing["params"] = params



    # Unknown → show governed options
    if intent == "unknown":
        q_lower = (q or "").lower()
        looks_like_unit_mix = (
            ("share" in q_lower or "percent" in q_lower or "%" in q_lower)
            and (" vs " in q_lower or "versus" in q_lower)
            and ("spend" in q_lower)
        )
        if looks_like_unit_mix:
            return ChatResponse(
                answer=(
                    "I can’t compare a *share (%)* metric against a *spend (£)* metric in one chart. "
                    "Try either:\n"
                    "• 'Show Digital Solutions share of total spend by month'\n"
                    "• 'Show Digital Solutions spend vs the rest of the company by month'"
                )
            )
        available = ", ".join(m["name"] for m in list_metrics())
        return ChatResponse(
            answer=(
                "I couldn't map your question to a known governed metric yet.\n\n"
                f"Available governed metrics: {available}\n\n"
                "Try:\n"
                "• 'Show me total spend by month'\n"
                "• 'Show me Digital Solutions spend by month'\n"
            )
        )

    if intent == "comparison":
        left = routing["left_metric"]
        right = routing["right_metric"]
        params = routing["params"]

        left_result = execute_metric(left, params)
        right_result = execute_metric(right, params)

        if "error" in left_result:
            return ChatResponse(answer=left_result["error"])
        if "error" in right_result:
            return ChatResponse(answer=right_result["error"])

        left_type = (left_result.get("meta") or {}).get("type")
        right_type = (right_result.get("meta") or {}).get("type")

        left_unit = _unit_for_metric_type(left_type)
        right_unit = _unit_for_metric_type(right_type)

        if left_unit != right_unit:
            return ChatResponse(
                answer=(
                    "I can’t compare those directly because they use different units "
                    "(percent vs currency). Try either a share metric alone, or a spend "
                    "vs spend comparison."
                ),
                series=[],
                chart=None,
                meta={
                    "error": "unit_mismatch",
                    "left_unit": left_unit,
                    "right_unit": right_unit,
                },
                data=[],
            )

        def display_name(metric_name: str) -> str:
            # nicer demo labels
            if metric_name == "rest_of_company_spend":
                return "Rest of Company"
            if metric_name == "digital_solutions_spend":
                return "Digital Solutions"
            if metric_name.endswith("_spend"):
                return metric_name.replace("_spend", "").replace("_", " ").title()
            return metric_name.replace("_", " ").title()

        def latest_and_mom(rows: list[dict]):
            if not rows:
                return None, None, None
            latest_period = rows[-1].get("period")
            latest_val = rows[-1].get("value")
            prev_val = rows[-2].get("value") if len(rows) >= 2 else None
            mom = ((latest_val - prev_val) / prev_val) if (prev_val not in (None, 0)) else None
            return latest_period, latest_val, mom

        left_rows = left_result.get("rows") or []
        right_rows = right_result.get("rows") or []

        left_period, left_latest, left_mom = latest_and_mom(left_rows)
        right_period, right_latest, right_mom = latest_and_mom(right_rows)

        # Prefer a period that exists (they should align, but be safe)
        latest_period = left_period or right_period

        left_latest = float(left_latest or 0)
        right_latest = float(right_latest or 0)

        total_latest = left_latest + right_latest
        share_latest = (left_latest / total_latest) if total_latest else 0.0

        # Friendly summary text
        period_txt = latest_period[:10] if isinstance(latest_period, str) else "the latest period"
        answer = (
            f"In {period_txt}, {display_name(left)} accounted for {share_latest:.1%} "
            f"of total company spend."
        )

        kpis = {
            "period_latest": period_txt,
            "left_metric": left,
            "right_metric": right,
            "left_latest_gbp": left_latest,
            "right_latest_gbp": right_latest,
            "total_latest_gbp": total_latest,
            "left_share_latest": share_latest,
            "left_mom_change_pct": (left_mom * 100) if left_mom is not None else None,
            "right_mom_change_pct": (right_mom * 100) if right_mom is not None else None,
        }

        return ChatResponse(
            answer=answer,
            kpis=kpis,
            series=[
                {"name": display_name(left), "data": left_rows},
                {"name": display_name(right), "data": right_rows},
            ],
            chart={
                "type": "line",
                "x": "period",
                "y": "value",
                "unit": "GBP",
            },
        )
    if intent == "metric":
        metric_name = routing.get("metric")
        logger.info(f"INTENT={intent} METRIC={routing.get('metric')}")
        if not metric_name:
                return ChatResponse(answer="No metric resolved.")

        result = execute_metric(metric_name, params)

    if "error" in result:
        return ChatResponse(answer=result["error"])

    answer = summarise_timeseries(metric_name, result.get("rows") or [])


    meta = result.get("meta") or {}
    metric_type = (meta.get("type") or "").lower()

    unit = "PERCENT" if metric_type == "ratio" else "GBP"

    return ChatResponse(
        answer=answer,
        series=[
            {
                "name": metric_name.replace("_", " ").title(),
                "data": result.get("rows") or [],
            }
        ],
        chart={"type": "line", "x": "period", "y": "value", "unit": unit},
        meta=result.get("meta"),
        data=result.get("rows") or [],
    )

@app.get("/kpi/top-vendors", response_model=VendorKpiResponse)
def top_vendors(limit: int = 10):
    sql = f"""
        SELECT
            vendor_name,
            SUM(value_in_gbp) AS total_spend_gbp
        FROM `llm-v1`.analytics.fct_po_spend
        GROUP BY vendor_name
        ORDER BY total_spend_gbp DESC
        LIMIT {limit}
    """

    rows = run_query(sql)

    vendors = [
        VendorSpend(
            vendor_name=row["vendor_name"],
            total_spend_gbp=float(row["total_spend_gbp"] or 0),
        )
        for row in rows
    ]

    return VendorKpiResponse(sql=sql, vendors=vendors)


@app.get("/metrics")
def metrics():
    return {"metrics": list_metrics()}

@app.get("/debug/manifest")
def debug_manifest():
    m = load_manifest()
    return {
        "manifest_path": load_manifest.__globals__["DBT_MANIFEST_PATH"],
        "top_level_keys": sorted(list(m.keys())),
        "metrics_count": len(m.get("metrics") or {}),
        "semantic_models_count": len(m.get("semantic_models") or {}),
        "nodes_count": len(m.get("nodes") or {}),
    }


from eng.semantics.metric_sql import build_metric_timeseries_sql
from fastapi import Query, HTTPException


@app.get("/metric/{metric_name}")
def get_metric(
    metric_name: str,
    grain: str = Query(default="month"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """
    Execute a governed dbt metric and return time series data.
    Supports simple, derived, and ratio metrics.
    """

    # ---- Load dbt semantic context ----
    metrics, semantic_models, nodes = load_metrics_semantic_models_and_nodes()

    metrics_by_name = {
        m.get("name"): m
        for m in metrics.values()
        if m.get("name")
    }

    metric = metrics_by_name.get(metric_name)
    if not metric:
        raise HTTPException(status_code=404, detail=f"Unknown metric '{metric_name}'")

    # ---- Resolve semantic model ----
    # MVP assumption: one semantic model
    if not semantic_models:
        raise HTTPException(status_code=500, detail="No semantic models found")

    semantic_model = next(iter(semantic_models.values()))

    # ---- Build SQL via semantic layer ----
    params = {
        "grain": grain,
        "start_date": start_date,
        "end_date": end_date,
    }

    sql, meta = build_metric_timeseries_sql(
        metric=metric,
        semantic_model=semantic_model,
        nodes=nodes,
        params=params,
        metrics_by_name=metrics_by_name,
    )

    # ---- Execute SQL ----
    rows =run_query(sql)

    return {
        "meta": meta,
        "sql": sql,        # keep for demo/debug; hide later if needed
        "rows": rows,
    }


from eng.packs.registry import list_packs, get_pack
from eng.packs.execute_pack import run_pack

@app.get("/packs")
def packs():
    return {"packs": list_packs()}

@app.post("/packs/{pack_id}/run")
def run_pack_endpoint(pack_id: str):
    try:
        pack = get_pack(pack_id)
    except KeyError as e:
        return {"error": str(e)}

    out = run_pack(pack)
    if "error" in out:
        return {"error": out["error"]}
    return out
