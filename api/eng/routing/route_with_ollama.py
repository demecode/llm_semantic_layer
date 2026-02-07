import json
import re
import requests
from typing import Any, Dict, Tuple

from eng.semantics.dbt_semantics import list_metrics
from eng.config import MODEL_NAME, LLM_TIMEOUT_SECONDS, OLLAMA_BASE_URL
from eng.logger import logger


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

ALLOWED_GRAINS = {"day", "week", "month", "quarter", "year"}


def _strip_code_fences(s: str) -> str:
    s = (s or "").strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s.lower().startswith("json"):
            s = s[4:].strip()
    return s.strip()


def _post_ollama(system_prompt: str, question: str) -> Tuple[str, Dict[str, Any]]:
    """
    Try /api/chat first. If 404, fallback to /api/generate.
    Returns: (content, debug_meta)
    """
    base = (OLLAMA_BASE_URL or "http://ollama:11434").rstrip("/")
    chat_url = f"{base}/api/chat"
    gen_url = f"{base}/api/generate"

    chat_body = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"User question: {question}"},
        ],
        "stream": False,
        "temperature": 0,
    }

    prompt = f"""{system_prompt}

User question: {question}

Return ONLY the JSON object.
""".strip()

    gen_body = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "temperature": 0,
    }

    # 1) Try chat
    try:
        r = requests.post(chat_url, json=chat_body, timeout=LLM_TIMEOUT_SECONDS)
        if r.status_code != 404:
            r.raise_for_status()
            data = r.json()
            content = ((data.get("message") or {}).get("content") or "").strip()
            return content, {"mode": "chat", "url": chat_url}
    except requests.HTTPError:
        # chat exists but errored (e.g. model missing) -> bubble so logs show it
        raise
    except Exception:
        # network/timeout -> fallback below
        pass

    # 2) Fallback generate
    r = requests.post(gen_url, json=gen_body, timeout=LLM_TIMEOUT_SECONDS)
    r.raise_for_status()
    data = r.json()
    content = (data.get("response") or "").strip()
    return content, {"mode": "generate", "url": gen_url}


def route_with_ollama(question: str) -> Dict[str, Any]:
    logger.warning("ROUTER HIT question=%r", question)

    q_raw = (question or "").strip()
    if not q_raw or FORBIDDEN_PATTERNS.search(q_raw):
        return {"intent": "unknown"}

    q_lower = q_raw.lower()

    # Load governed metrics
    metrics = list_metrics()
    metric_names = [m["name"] for m in metrics if m.get("name")]

    # Map metric type for deterministic overrides (simple/derived/ratio)
    type_by_name = {
        m["name"]: (m.get("type") or "").lower()
        for m in metrics
        if m.get("name")
    }

    metric_descriptions = "\n".join(
        f"- {m['name']}: {m.get('description','')}".strip()
        for m in metrics
        if m.get("name")
    )

    intent_hint = (
        "comparison" if any(k in q_lower for k in COMPARISON_KEYWORDS) else "metric"
    )

    # Heuristics for overrides
    wants_spend = "spend" in q_lower
    wants_share = (
        ("share" in q_lower)
        or ("%" in q_lower)
        or ("percent" in q_lower)
        or ("percentage" in q_lower)
        or ("rate" in q_lower)
    )

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
- start_date: "YYYY-MM-DD" (optional)
- end_date: "YYYY-MM-DD" (optional)

INTENT HINT: {intent_hint}

IMPORTANT ROUTING RULES:
- ONLY choose a "share"/percentage metric when user asks for share/percent/%.
- If user asks "spend vs rest of company", choose spend metrics:
    left_metric: digital_solutions_spend
    right_metric: rest_of_company_spend
- NEVER mix a ratio metric with a currency metric in a comparison.
- If the question asks for forecasting/prediction/explanations/SQL/raw data, return intent unknown.
- If you cannot clearly map, return intent unknown.

If the question cannot be clearly mapped:
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
""".strip()

    # Call Ollama
    try:
        content, dbg = _post_ollama(system_prompt, q_raw)
        logger.info("ROUTER ollama_mode=%s url=%s", dbg.get("mode"), dbg.get("url"))
        logger.info("ROUTER raw_ollama=%s", content)
    except Exception as e:
        logger.exception("ROUTER ollama_error=%s", str(e))
        return {"intent": "unknown"}

    content = _strip_code_fences(content)

    # Parse JSON
    try:
        obj = json.loads(content)
        if not isinstance(obj, dict):
            return {"intent": "unknown"}
    except Exception:
        return {"intent": "unknown"}

    intent = (obj.get("intent") or "unknown").lower()

    # Normalize params EARLY (so overrides can safely use clean_params)
    raw_params = obj.get("params") or {}
    grain = (raw_params.get("grain") or "month").lower()
    if grain not in ALLOWED_GRAINS:
        grain = "month"

    start_date = raw_params.get("start_date")
    end_date = raw_params.get("end_date")

    if start_date and not DATE_RE.match(str(start_date)):
        start_date = None
    if end_date and not DATE_RE.match(str(end_date)):
        end_date = None

    clean_params: Dict[str, Any] = {"grain": grain}
    if start_date:
        clean_params["start_date"] = str(start_date)
    if end_date:
        clean_params["end_date"] = str(end_date)

    # Guard against unit-mix comparisons (share vs spend)
    q = q_raw
    q_lower = q.lower()
    wants_share = (
        ("share" in q_lower)
        or ("percent" in q_lower)
        or ("percentage" in q_lower)
        or ("%" in q_lower)
    )
    wants_spend = "spend" in q_lower
    has_vs = any(k in q_lower for k in COMPARISON_KEYWORDS)
    if wants_share and has_vs and wants_spend:
        return {"intent": "unknown"}

    # -------------------------
    # Deterministic overrides
    # -------------------------

    # If user wants share/percent, always return the ratio metric as a SINGLE metric.
    # (Prevents mixing units on the chart)
    if wants_share:
        if "digital_solutions_share" in metric_names:
            return {
                "intent": "metric",
                "metric": "digital_solutions_share",
                "params": clean_params,
            }

    # If user wants spend comparison, force spend metrics (and block ratio metrics)
    if wants_spend and any(k in q_lower for k in COMPARISON_KEYWORDS):
        if (
            "digital_solutions_spend" in metric_names
            and "rest_of_company_spend" in metric_names
        ):
            return {
                "intent": "comparison",
                "left_metric": "digital_solutions_spend",
                "right_metric": "rest_of_company_spend",
                "params": clean_params,
            }

    # If LLM returned comparison but included ratio metric while user wants spend, override.
    if intent == "comparison" and wants_spend and not wants_share:
        left = obj.get("left_metric")
        right = obj.get("right_metric")
        left_type = type_by_name.get(left or "", "")
        right_type = type_by_name.get(right or "", "")
        if left_type == "ratio" or right_type == "ratio":
            if (
                "digital_solutions_spend" in metric_names
                and "rest_of_company_spend" in metric_names
            ):
                return {
                    "intent": "comparison",
                    "left_metric": "digital_solutions_spend",
                    "right_metric": "rest_of_company_spend",
                    "params": clean_params,
                }

    # -------------------------
    # Normal routing
    # -------------------------
    if intent == "metric":
        metric = obj.get("metric")
        if metric not in metric_names:
            return {"intent": "unknown"}
        return {"intent": "metric", "metric": metric, "params": clean_params}

    if intent == "comparison":
        left = obj.get("left_metric")
        right = obj.get("right_metric")
        if left not in metric_names or right not in metric_names or left == right:
            return {"intent": "unknown"}

        # Block mixing ratio + currency in a comparison
        left_type = type_by_name.get(left, "")
        right_type = type_by_name.get(right, "")
        if left_type == "ratio" or right_type == "ratio":
            return {"intent": "unknown"}

        return {
            "intent": "comparison",
            "left_metric": left,
            "right_metric": right,
            "params": clean_params,
        }

    return {"intent": "unknown"}
