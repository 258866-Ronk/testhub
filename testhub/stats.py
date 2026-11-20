"""Percentiles by linear interpolation."""
from .store import case_latencies


def percentile(values, p):
    if not values:
        return 0
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * p
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return round(s[f] + (s[c] - s[f]) * (k - f), 2)


def summary(run_no):
    v = case_latencies(run_no)
    return {"count": len(v), "avg": round(sum(v) / len(v), 2) if v else 0,
            "max": max(v) if v else 0, "p50": percentile(v, .50),
            "p90": percentile(v, .90), "p95": percentile(v, .95), "p99": percentile(v, .99)}
