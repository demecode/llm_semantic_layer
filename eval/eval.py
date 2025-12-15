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

from eng.llm_ollama import route_with_ollama


@dataclass
class TestCase:
    id: str
    question: str
    expected_tool: str
    expected_params: Dict[str, Any]


def load_cases(path: str) -> List[TestCase]:
    cases: List[TestCase] = []
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            obj = json.loads(line)
            cases.append(
                TestCase(
                    id=obj["id"],
                    question=obj["question"],
                    expected_tool=obj["expected_tool"],
                    expected_params=obj.get("expected_params", {}) or {},
                )
            )
    return cases


def normalize_tool(tool: Any) -> str:
    if not isinstance(tool, str):
        return "unknown"
    tool = tool.strip()
    return tool if tool else "unknown"


def coerce_int(v: Any) -> Optional[int]:
    try:
        if v is None:
            return None
        return int(v)
    except Exception:
        return None


def param_match(
    expected: Dict[str, Any],
    actual: Dict[str, Any],
    strict_dates: bool,
) -> Tuple[bool, str]:
    """
    Returns (pass, reason). We do a minimal but useful check:
    - If expected has 'limit', actual must have same int
    - If expected has start_date/end_date and strict_dates=True,
      actual must match exactly.
    - If strict_dates=False, only require that keys exist (if expected includes them)
    """
    expected = expected or {}
    actual = actual or {}

    # limit check
    if "limit" in expected:
        exp = coerce_int(expected.get("limit"))
        act = coerce_int(actual.get("limit"))
        if exp is None:
            return False, "expected limit not an int"
        if act != exp:
            return False, f"limit mismatch (expected {exp}, got {act})"

    # date checks
    for k in ("start_date", "end_date"):
        if k in expected:
            if k not in actual:
                return False, f"missing param {k}"
            if strict_dates:
                if str(actual.get(k)) != str(expected.get(k)):
                    return False, f"{k} mismatch (expected {expected.get(k)}, got {actual.get(k)})"

    return True, "ok"


def run_eval(
    cases: List[TestCase],
    output_csv: str,
    repeats: int,
    strict_dates: bool,
) -> None:
    os.makedirs(os.path.dirname(output_csv) or ".", exist_ok=True)

    rows_out = []
    tool_correct = 0
    params_correct = 0

    by_tool = {}  # expected_tool -> stats

    for case in cases:
        for r in range(repeats):
            t0 = time.time()
            result = route_with_ollama(case.question)
            elapsed_ms = int((time.time() - t0) * 1000)

            actual_tool = normalize_tool(result.get("tool"))
            actual_params = result.get("params", {}) or {}

            tool_ok = actual_tool == case.expected_tool
            params_ok = False
            params_reason = "skipped"

            # Only score params if tool matched (otherwise param scoring is noisy)
            if tool_ok:
                params_ok, params_reason = param_match(case.expected_params, actual_params, strict_dates)

            tool_correct += int(tool_ok)
            params_correct += int(params_ok)

            by_tool.setdefault(case.expected_tool, {"n": 0, "tool_ok": 0, "params_ok": 0})
            by_tool[case.expected_tool]["n"] += 1
            by_tool[case.expected_tool]["tool_ok"] += int(tool_ok)
            by_tool[case.expected_tool]["params_ok"] += int(params_ok)

            rows_out.append(
                {
                    "id": case.id,
                    "repeat": r + 1,
                    "question": case.question,
                    "expected_tool": case.expected_tool,
                    "expected_params": json.dumps(case.expected_params, ensure_ascii=False),
                    "actual_tool": actual_tool,
                    "actual_params": json.dumps(actual_params, ensure_ascii=False),
                    "tool_pass": tool_ok,
                    "params_pass": params_ok,
                    "params_reason": params_reason,
                    "elapsed_ms": elapsed_ms,
                }
            )

    # write CSV
    fieldnames = list(rows_out[0].keys()) if rows_out else []
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_out)

    total = len(cases) * repeats
    tool_acc = (tool_correct / total) * 100 if total else 0.0
    params_acc = (params_correct / total) * 100 if total else 0.0

    print("\n=== Eval Summary ===")
    print(f"Cases: {len(cases)} | Repeats: {repeats} | Total runs: {total}")
    print(f"Tool accuracy:   {tool_acc:.1f}%")
    print(f"Param accuracy:  {params_acc:.1f}% (only scored when tool matched)")
    print(f"Results CSV: {output_csv}\n")

    print("By expected tool:")
    for tool, s in by_tool.items():
        n = s["n"]
        ta = (s["tool_ok"] / n) * 100 if n else 0
        pa = (s["params_ok"] / n) * 100 if n else 0
        print(f"  - {tool:30s}  n={n:3d}  tool_acc={ta:5.1f}%  params_acc={pa:5.1f}%")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default="eval/test_cases.jsonl", help="Path to JSONL test cases")
    parser.add_argument("--out", default="eval/results.csv", help="Output CSV path")
    parser.add_argument("--repeats", type=int, default=1, help="Repeat each case N times")
    parser.add_argument("--strict-dates", action="store_true", help="Require exact date strings to match expected")
    args = parser.parse_args()

    cases = load_cases(args.cases)
    if not cases:
        raise SystemExit("No test cases found. Add lines to eval/test_cases.jsonl")

    run_eval(cases, args.out, args.repeats, args.strict_dates)


if __name__ == "__main__":
    main()
