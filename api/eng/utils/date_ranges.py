import re
from datetime import date
from dateutil.relativedelta import relativedelta

LAST_N_YEARS = re.compile(r"\blast\s+(\d+)\s+years?\b", re.IGNORECASE)
LAST_N_MONTHS = re.compile(r"\blast\s+(\d+)\s+months?\b", re.IGNORECASE)

def apply_relative_date_filters(question: str, params: dict) -> dict:
    q = question or ""
    today = date.today()

    # ---- "last N years" ----
    m = LAST_N_YEARS.search(q)
    if m:
        n = int(m.group(1))
        start = today - relativedelta(years=n)
        end = today + relativedelta(days=1)  # exclusive upper bound

        return {
            **params,
            "grain": "month",  # force sensible grain
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        }

    # ---- "last N months" ----
    m = LAST_N_MONTHS.search(q)
    if m:
        n = int(m.group(1))
        start = today - relativedelta(months=n)
        end = today + relativedelta(days=1)

        return {
            **params,
            "grain": "month",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        }

    # ---- No relative date phrase ----
    return params