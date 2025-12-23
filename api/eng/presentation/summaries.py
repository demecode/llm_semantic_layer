from typing import List, Dict


def summarise_timeseries(metric: str, rows: List[Dict]) -> str:
    if not rows:
        return f"No data found for metric '{metric}'."

    first = rows[0]["value"]
    last = rows[-1]["value"]
    delta = last - first
    pct = (delta / first) * 100 if first else 0

    direction = "increased" if delta > 0 else "decreased"

    return (
        f"{metric.replace('_', ' ').title()} {direction} from "
        f"£{first:,.0f} to £{last:,.0f} "
        f"({pct:+.1f}%) over the selected period."
    )