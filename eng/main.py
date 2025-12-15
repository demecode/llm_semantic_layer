from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict, Any

from .databricks_client import run_query
from eng.llm_ollama import route_with_ollama

from typing import Optional
from pydantic import BaseModel
from datetime import date, time
from eng.logger import logger
from eng.semantics.dbt_metric_ldr import load_dbt_metrics
from eng.semantics.inspect_manifest import inspect_manifest

app = FastAPI(title="LLM x1")


class TimeSeriesPoint(BaseModel):
    month: str
    digital_solutions_spend_gbp: float
    total_spend_gbp: float


class KpiResponse(BaseModel):
    sql: str
    points: List[TimeSeriesPoint]
    total_digital_solutions_spend_gbp: float
    total_spend_gbp: float



# ... you already have TimeSeriesPoint and KpiResponse

class VendorSpend(BaseModel):
    vendor_name: str
    total_spend_gbp: float


class VendorKpiResponse(BaseModel):
    sql: str
    vendors: List[VendorSpend]


@app.get("/health")
def health():
    return {"status": "ok"}


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
    kpi: Optional[KpiResponse] = None
    vendor_kpi: Optional[VendorKpiResponse] = None

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    import time
    start_time = time.time()
    q = req.question

    routing = route_with_ollama(q)
    tool = routing.get("tool", "unknown")
    params = routing.get("params", {})

    # 1) Digital Solutions spend vs total
    if tool == "digital_solutions_spend_vs_total":
        kpi = digital_solutions_spend_vs_total()

        answer = (
            "I routed your question to the 'Digital Solutions spend vs total' metric. "
            "Here’s Digital Solutions spend vs total spend by month, "
            "based on the governed fct_po_spend model in Databricks. "
            f"Total Digital Solutions spend: £{kpi.total_digital_solutions_spend_gbp:,.2f}. "
            f"Total overall spend: £{kpi.total_spend_gbp:,.2f}."
        )

        return ChatResponse(answer=answer, kpi=kpi)

    # 2) Top vendors by spend
    if tool == "top_vendors":
        limit = int(params.get("limit", 10) or 10)
        vendor_kpi = top_vendors(limit=limit)

        top_list = ", ".join(
            f"{v.vendor_name} (£{v.total_spend_gbp:,.0f})"
            for v in vendor_kpi.vendors[: min(limit, 5)]
        )

        answer = (
            f"I routed your question to the 'top vendors by spend' metric "
            f"(limit={limit}). "
            f"Here are some of the top vendors by total spend in GBP: {top_list}."
        )

        return ChatResponse(answer=answer, vendor_kpi=vendor_kpi)

    # 3) Fallback when Ollama returns 'unknown'
    elapsed_ms = int((time.time() - start_time) * 1000)

    logger.info(
        "question=%s tool=%s params=%s elapsed_ms=%d",
        q,
        tool,
        params,
        elapsed_ms,
    )
    return ChatResponse(
        answer=(
            "I couldn't map your question to a known governed metric yet.\n\n"
            "Right now I know how to answer:\n"
            "- Digital Solutions spend vs total spend over time\n"
            "- Top vendors by total spend\n\n"
            "Try asking one of those, e.g.:\n"
            "• 'Show me Digital Solutions spend vs total spend by month'\n"
            "• 'Who are the top vendors by spend?'"
        )
    )
from .databricks_client import run_query

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
def list_metrics():
    metrics, _ = load_dbt_metrics()
    return {
        "metrics": [
            {"name": m["name"], "label": m["label"], "description": m["description"]}
            for m in metrics.values()
        ]
    }


@app.get("/debug/manifest")
def debug_manifest():
    return inspect_manifest()

from eng.semantics.dbt_semantics import list_metrics as dbt_list_metrics

@app.get("/metrics")
def metrics():
    return {"metrics": dbt_list_metrics()}

from eng.semantics.dbt_semantics import load_metrics_and_semantic_models
from eng.semantics.metric_sql import build_metric_timeseries_sql
from eng.databricks_client import run_query

@app.get("/metric/{metric_name}")
def run_metric(metric_name: str, grain: str = "month", start_date: str | None = None, end_date: str | None = None):
    metrics, semantic_models = load_metrics_and_semantic_models()

    # find metric by name
    metric = None
    for _id, m in metrics.items():
        if m.get("name") == metric_name:
            metric = m
            break
    if not metric:
        return {"error": f"Metric not found: {metric_name}"}

    # choose the semantic model (for now: first one that contains the referenced measure)
    measure_name = (metric.get("type_params") or {}).get("measure")
    chosen_sm = None
    for sm in semantic_models.values():
        for meas in (sm.get("measures") or []):
            if meas.get("name") == measure_name:
                chosen_sm = sm
                break
        if chosen_sm:
            break
    if not chosen_sm:
        return {"error": f"Could not resolve semantic model for metric '{metric_name}' (measure '{measure_name}')"}

    params = {"grain": grain, "start_date": start_date, "end_date": end_date}
    sql, meta = build_metric_timeseries_sql(metric, chosen_sm, params)
    rows = run_query(sql)

    return {"meta": meta, "sql": sql, "rows": rows}