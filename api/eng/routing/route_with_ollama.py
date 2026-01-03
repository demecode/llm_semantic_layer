import json
import re
import requests
from typing import Any, Dict

from eng.semantics.dbt_semantics import list_metrics
from eng.config import OLLAMA_CHAT_ENDPOINT, MODEL_NAME, LLM_TIMEOUT_SECONDS

FORBIDDEN_PATTERNS = re.compile(
    r"\b(forecast|predict|prediction|next quarter|next month|next year|why|explain|reason|cause|root cause|write sql|show sql|give me sql|raw data|dump data|ignore rules|bypass)\b",
    re.IGNORECASE,
)

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

COMPARISON_KEYWORDS = [
    " vs ",
    " versus ",
    " compared to ",
    " against ",
    " rest of the company",
]


def route_with_ollama(question: str) -> Dict[str, Any]:
    """
    dbt-first router supporting:
      - single metric
      - metric comparison

    Returns:
      { intent: "metric", metric: ..., params: {...} }
      { intent: "comparison", left_metric: ..., right_metric: ..., params: {...} }
      { intent: "unknown" }
    """

    # Hard safety gate (pre-LLM)
    if FORBIDDEN_PATTERNS.search(question or ""):
        return {"intent": "unknown"}

    # Load governed metrics 
    metrics = list_metrics()
    metric_names = [m["name"] for m in metrics]
    metric_descriptions = "\n".join(
        f"- {m['name']}: {m.get('description','')}".strip()
        for m in metrics
    )

    intent_hint = (
        "comparison"
        if any(k in (question or "").lower() for k in COMPARISON_KEYWORDS)
        else "metric"
    )

    #  System prompt
    system_prompt = f"""
You are a routing assistant for a governed data copilot.

You MUST respond with a SINGLE JSON object ONLY.
No markdown. No explanations. No extra text.

You may ONLY use these governed metrics (exact names):

{", ".join(metric_names)}

Metric descriptions:
{metric_descriptions}

Allowed params:
- grain: one of ["day","week","month","quarter","year"] (default "month")
- start_date: "YYYY-MM-DD"
- end_date: "YYYY-MM-DD"

INTENT HINT: {intent_hint}

If the question:
- asks for forecasting or prediction
- asks for explanations or causes
- asks for SQL or raw data
- cannot be clearly mapped

Return:
{{ "intent": "unknown" }}

Response formats:

Single metric:
{{
  "intent": "metric",
  "metric": "<metric_name>",
  "params": {{
    "grain": "month",
    "start_date": "YYYY-MM-DD",
    "end_date": "YYYY-MM-DD"
  }}
}}

Comparison:
{{
  "intent": "comparison",
  "left_metric": "<metric_name>",
  "right_metric": "<metric_name>",
  "params": {{
    "grain": "month",
    "start_date": "YYYY-MM-DD",
    "end_date": "YYYY-MM-DD"
  }}
}}

Example:
Question: "Show Digital Solutions spend vs the rest of the company by month"
Response:
{{
  "intent": "comparison",
  "left_metric": "digital_solutions_spend",
  "right_metric": "rest_of_company_spend",
  "params": {{ "grain": "month" }}
}}
""".strip()

    # Call Ollama
    prompt = f"""{system_prompt}

User question: {question}

Return ONLY the JSON object.
""".strip()
    body = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"User question: {question}"},
        ],
        "stream": False,
        "temperature": 0,
    }

    resp = requests.post(
        OLLAMA_CHAT_ENDPOINT,
        json=body,
        timeout=LLM_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    data = resp.json()

    # Ollama /api/chat format:
    # { "message": { "content": "..." }, ... }
    content = ((data.get("message") or {}).get("content") or "").strip()

    # Optional: support OpenAI-compatible format if you ever switch endpoints
    if not content and "choices" in data:
        content = (
            ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        ).strip()

    # Parse JSON safely 
    try:
        if content.startswith("```"):
            content = content.strip("`").replace("json", "", 1).strip()
        obj = json.loads(content)
    except Exception:
        return {"intent": "unknown"}

    intent = obj.get("intent", "unknown")

    #Normalize params 
    raw_params = obj.get("params") or {}

    grain = (raw_params.get("grain") or "month").lower()
    if grain not in {"day", "week", "month", "quarter", "year"}:
        grain = "month"

    start_date = raw_params.get("start_date")
    end_date = raw_params.get("end_date")

    if start_date and not DATE_RE.match(str(start_date)):
        start_date = None
    if end_date and not DATE_RE.match(str(end_date)):
        end_date = None

    clean_params = {"grain": grain}
    if start_date:
        clean_params["start_date"] = str(start_date)
    if end_date:
        clean_params["end_date"] = str(end_date)

    # Return intents 
    if intent == "metric":
        metric = obj.get("metric")
        if metric not in metric_names:
            return {"intent": "unknown"}

        return {
            "intent": "metric",
            "metric": metric,
            "params": clean_params,
        }

    if intent == "comparison":
        left = obj.get("left_metric")
        right = obj.get("right_metric")

        if left not in metric_names or right not in metric_names:
            return {"intent": "unknown"}

        return {
            "intent": "comparison",
            "left_metric": left,
            "right_metric": right,
            "params": clean_params,
        }

    return {"intent": "unknown"}