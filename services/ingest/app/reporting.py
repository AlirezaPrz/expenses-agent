from datetime import datetime, timedelta, timezone

def sum_by_category_firestore(docs, days: int = 30):
    """Client-side aggregation (simple and free): sum totals by category for last N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    buckets = {}
    for d in docs:
        data = d.to_dict()
        ts = data.get("ts")
        if not ts or ts < cutoff:
            continue
        cat = (data.get("category") or "other").lower()
        amt = float(data.get("total") or 0.0)
        buckets[cat] = buckets.get(cat, 0.0) + amt
    # Return sorted list for nice display
    return sorted([{"category": k, "total": round(v, 2)} for k, v in buckets.items()],
                  key=lambda x: x["total"], reverse=True)
