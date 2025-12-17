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
from eng.semantics.dbt_semantics import load_metrics_semantic_models_and_nodes
from eng.presentation.summaries import summarise_timeseries


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
    meta: Optional[Dict[str, Any]] = None
    data: Optional[List[Dict[str, Any]]] = None
    # kpi: Optional[KpiResponse] = None
    # vendor_kpi: Optional[VendorKpiResponse] = None



from eng.llm_ollama import route_with_ollama 
from eng.semantics.execute_metric import execute_metric
from eng.semantics.dbt_semantics import list_metrics

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    q = req.question

    routing = route_with_ollama(q)
    metric = routing.get("metric", "unknown")
    params = routing.get("params", {}) or {}

    logger.info(f"/chat q={q!r} metric={metric} params={params}")

    # Unknown → show governed options
    if metric == "unknown":
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

    result = execute_metric(metric, params)

    if "error" in result:
        return ChatResponse(answer=result["error"])
    
    summary = summarise_timeseries(metric, result["rows"])
    return ChatResponse(
        answer=summary,
        meta=result["meta"],
        data=result["rows"],
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


from eng.semantics.dbt_semantics import list_metrics

@app.get("/metrics")
def metrics():
    return {"metrics": list_metrics()}

from eng.semantics.dbt_semantics import load_manifest
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
from eng.databricks_client import run_query
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