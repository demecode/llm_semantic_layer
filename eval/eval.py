import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

# Ensure project root is on the import path when running as a script
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

API_DIR = ROOT / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from api.eng.routing.route_with_ollama import route_with_ollama
from api.eng.semantics.execute_metric import execute_metric  # uses your Databricks client


@dataclass
class TestCase:
    id: str
    question: str
    expected_intent: str  # "metric" | "comparison" | "unknown"
    expected_metric: Optional[str] = None
    expected_left_metric: Optional[str] = None
    expected_right_metric: Optional[str] = None
    expected_params: Dict[str, Any] = None
    expect_non_empty: Optional[bool] = None  # optional sanity expectation


def load_cases(path: str) -> List[TestCase]:
    cases: List[TestCase] = []
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            obj = json.loads(line)

            expected_intent = obj.get("expected_intent")
            if expected_intent not in {"metric", "comparison", "unknown"}:
                raise ValueError(f"Line {line_no}: expected_intent must be metric/comparison/unknown")

            cases.append(
                TestCase(
                    id=obj["id"],
                    question=obj["question"],
                    expected_intent=expected_intent,
                    expected_metric=obj.get("expected_metric"),
                    expected_left_metric=obj.get("expected_left_metric"),
                    expected_right_metric=obj.get("expected_right_metric"),
                    expected_params=obj.get("expected_params", {}) or {},
                    expect_non_empty=obj.get("expect_non_empty"),
                )
            )
    return cases


DATE_RE = __import__("re").compile(r"^\d{4}-\d{2}-\d{2}$")


def normalize_intent(v: Any) -> str:
    if not isinstance(v, str):
        return "unknown"
    v = v.strip().lower()
    return v if v in {"metric", "comparison", "unknown"} else "unknown"


def coerce_int(v: Any) -> Optional[int]:
    try:
        if v is None:
            return None
        return int(v)
    except Exception:
        return None


def param_match(expected: Dict[str, Any], actual: Dict[str, Any], strict_dates: bool) -> Tuple[bool, str]:
    expected = expected or {}
    actual = actual or {}

    # grain
    if "grain" in expected:
        eg = str(expected.get("grain")).lower()
        ag = str(actual.get("grain") or "").lower()
        if eg != ag:
            return False, f"grain mismatch (expected {eg}, got {ag})"

    # limit (if you still use it anywhere)
    if "limit" in expected:
        exp = coerce_int(expected.get("limit"))
        act = coerce_int(actual.get("limit"))
        if exp is None:
            return False, "expected limit not an int"
        if act != exp:
            return False, f"limit mismatch (expected {exp}, got {act})"

    # dates
    for k in ("start_date", "end_date"):
        if k in expected:
            if k not in actual:
                return False, f"missing param {k}"
            if strict_dates:
                if str(actual.get(k)) != str(expected.get(k)):
                    return False, f"{k} mismatch (expected {expected.get(k)}, got {actual.get(k)})"
            else:
                # if not strict, require valid YYYY-MM-DD format if present
                if actual.get(k) and not DATE_RE.match(str(actual.get(k))):
                    return False, f"{k} not YYYY-MM-DD (got {actual.get(k)})"

    return True, "ok"


def contract_check(result: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Checks that execution returned a contract with the key fields.
    """
    if not isinstance(result, dict):
        return False, "result not a dict"
    if "error" in result:
        return False, f"execution error: {result['error']}"
    c = result.get("contract")
    if not isinstance(c, dict):
        return False, "missing contract"
    for k in ("metric", "semantic_model", "relation", "manifest_hash"):
        if not c.get(k):
            return False, f"contract missing {k}"
    return True, "ok"


def sanity_check(metric_name: str, result: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Very lightweight sanity:
      - rows exist (if any)
      - numeric values
      - spend metrics should be >= 0
      - ratio metrics should be between 0 and 1 (if you return ratio as fraction)
    """
    if "error" in result:
        return False, f"execution error: {result['error']}"
    rows = result.get("rows") or []
    if not isinstance(rows, list):
        return False, "rows not a list"

    for r in rows:
        v = r.get("value")
        if v is None:
            return False, "row missing value"
        try:
            fv = float(v)
        except Exception:
            return False, f"non-numeric value: {v}"

        # basic constraints based on naming (simple heuristic)
        if "spend" in metric_name or "total" in metric_name:
            if fv < 0:
                return False, f"negative spend value: {fv}"

        if "share" in metric_name:
            # if your ratio outputs 0..1; if you output percent, adjust this
            if fv < 0 or fv > 1.0:
                return False, f"share out of bounds (expected 0..1): {fv}"

    return True, "ok"


def run_eval(cases: List[TestCase], output_csv: str, repeats: int, strict_dates: bool, run_execution: bool) -> None:
    os.makedirs(os.path.dirname(output_csv) or ".", exist_ok=True)

    rows_out = []
    intent_correct = 0
    metric_correct = 0
    params_correct = 0
    contract_pass = 0
    sanity_pass = 0

    total = len(cases) * repeats

    for case in cases:
        for rep in range(repeats):
            t0 = time.time()
            routing = route_with_ollama(case.question)
            elapsed_ms = int((time.time() - t0) * 1000)

            actual_intent = normalize_intent(routing.get("intent"))
            actual_params = routing.get("params", {}) or {}

            # default values for CSV
            actual_metric = routing.get("metric")
            actual_left = routing.get("left_metric")
            actual_right = routing.get("right_metric")

            intent_ok = actual_intent == case.expected_intent

            metric_ok = False
            params_ok = False
            params_reason = "skipped"

            # metric correctness (only meaningful if intent matches expected)
            if intent_ok and actual_intent == "metric":
                metric_ok = (actual_metric == case.expected_metric)
            elif intent_ok and actual_intent == "comparison":
                metric_ok = (actual_left == case.expected_left_metric and actual_right == case.expected_right_metric)
            elif intent_ok and actual_intent == "unknown":
                metric_ok = True  # nothing else to compare

            # param scoring only when intent matches and is not unknown
            if intent_ok and actual_intent in {"metric", "comparison"}:
                params_ok, params_reason = param_match(case.expected_params, actual_params, strict_dates)
            else:
                params_ok = (case.expected_intent == "unknown")
                params_reason = "ok" if params_ok else "skipped"

            # Optional: execute the metric(s) and run contract/sanity checks
            contract_ok = None
            sanity_ok = None
            contract_reason = "skipped"
            sanity_reason = "skipped"

            if run_execution and intent_ok and metric_ok and actual_intent in {"metric", "comparison"}:
                if actual_intent == "metric":
                    exec_result = execute_metric(actual_metric, actual_params)
                    contract_ok, contract_reason = contract_check(exec_result)
                    sanity_ok, sanity_reason = sanity_check(actual_metric, exec_result)

                    # optional non-empty expectation
                    if case.expect_non_empty is True and not (exec_result.get("rows") or []):
                        sanity_ok, sanity_reason = False, "expected non-empty rows but got empty"
                    if case.expect_non_empty is False and (exec_result.get("rows") or []):
                        sanity_ok, sanity_reason = False, "expected empty rows but got non-empty"

                else:
                    left_res = execute_metric(actual_left, actual_params)
                    right_res = execute_metric(actual_right, actual_params)

                    c1, r1 = contract_check(left_res)
                    c2, r2 = contract_check(right_res)
                    contract_ok = c1 and c2
                    contract_reason = f"left={r1}; right={r2}"

                    s1, sr1 = sanity_check(actual_left, left_res)
                    s2, sr2 = sanity_check(actual_right, right_res)
                    sanity_ok = s1 and s2
                    sanity_reason = f"left={sr1}; right={sr2}"

            # tally
            intent_correct += int(intent_ok)
            metric_correct += int(metric_ok)
            params_correct += int(params_ok)
            if contract_ok is True:
                contract_pass += 1
            if sanity_ok is True:
                sanity_pass += 1

            rows_out.append(
                {
                    "id": case.id,
                    "repeat": rep + 1,
                    "question": case.question,
                    "expected_intent": case.expected_intent,
                    "expected_metric": case.expected_metric or "",
                    "expected_left_metric": case.expected_left_metric or "",
                    "expected_right_metric": case.expected_right_metric or "",
                    "expected_params": json.dumps(case.expected_params or {}, ensure_ascii=False),
                    "actual_intent": actual_intent,
                    "actual_metric": actual_metric or "",
                    "actual_left_metric": actual_left or "",
                    "actual_right_metric": actual_right or "",
                    "actual_params": json.dumps(actual_params, ensure_ascii=False),
                    "intent_pass": intent_ok,
                    "metric_pass": metric_ok,
                    "params_pass": params_ok,
                    "params_reason": params_reason,
                    "contract_pass": contract_ok if contract_ok is not None else "",
                    "contract_reason": contract_reason,
                    "sanity_pass": sanity_ok if sanity_ok is not None else "",
                    "sanity_reason": sanity_reason,
                    "elapsed_ms": elapsed_ms,
                }
            )

    # write CSV
    fieldnames = list(rows_out[0].keys()) if rows_out else []
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_out)

    intent_acc = (intent_correct / total) * 100 if total else 0.0
    metric_acc = (metric_correct / total) * 100 if total else 0.0
    params_acc = (params_correct / total) * 100 if total else 0.0

    print("\n=== Eval Summary ===")
    print(f"Cases: {len(cases)} | Repeats: {repeats} | Total runs: {total}")
    print(f"Intent accuracy: {intent_acc:.1f}%")
    print(f"Metric accuracy: {metric_acc:.1f}%")
    print(f"Param accuracy:  {params_acc:.1f}% (only meaningful for metric/comparison cases)")
    if run_execution:
        print(f"Contract pass:   {contract_pass}/{total} ({(contract_pass/total*100 if total else 0):.1f}%)")
        print(f"Sanity pass:     {sanity_pass}/{total} ({(sanity_pass/total*100 if total else 0):.1f}%)")
    print(f"Results CSV: {output_csv}\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default="eval/test_cases.jsonl", help="Path to JSONL test cases")
    parser.add_argument("--out", default="eval/results.csv", help="Output CSV path")
    parser.add_argument("--repeats", type=int, default=1, help="Repeat each case N times")
    parser.add_argument("--strict-dates", action="store_true", help="Require exact date strings to match expected")
    parser.add_argument("--no-exec", action="store_true", help="Skip executing metrics (router-only)")
    args = parser.parse_args()

    cases = load_cases(args.cases)
    if not cases:
        raise SystemExit("No test cases found. Add lines to eval/test_cases.jsonl")

    run_eval(cases, args.out, args.repeats, args.strict_dates, run_execution=not args.no_exec)


if __name__ == "__main__":
    main()