from collections import deque
from datetime import datetime, timezone
from threading import Lock
from time import perf_counter


MAX_LATENCY_SAMPLES = 300
_samples = deque(maxlen=MAX_LATENCY_SAMPLES)
_lock = Lock()


def now_ms():
    return perf_counter() * 1000


def record_api_latency(method, path, status_code, duration_ms):
    sample = {
        "method": method,
        "path": path,
        "status_code": int(status_code or 0),
        "duration_ms": round(float(duration_ms or 0), 2),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    with _lock:
        _samples.appendleft(sample)


def get_latency_dashboard(limit=75):
    with _lock:
        samples = list(_samples)

    limited_samples = samples[: max(1, min(int(limit or 75), MAX_LATENCY_SAMPLES))]
    endpoint_groups = {}
    for sample in samples:
        key = f"{sample['method']} {sample['path']}"
        group = endpoint_groups.setdefault(
            key,
            {
                "endpoint": key,
                "count": 0,
                "total_ms": 0,
                "max_ms": 0,
                "last_ms": 0,
                "last_status": 0,
                "last_seen_at": None,
            },
        )
        group["count"] += 1
        group["total_ms"] += sample["duration_ms"]
        group["max_ms"] = max(group["max_ms"], sample["duration_ms"])
        if group["last_seen_at"] is None:
            group["last_ms"] = sample["duration_ms"]
            group["last_status"] = sample["status_code"]
            group["last_seen_at"] = sample["recorded_at"]

    endpoints = []
    for group in endpoint_groups.values():
        endpoints.append(
            {
                "endpoint": group["endpoint"],
                "count": group["count"],
                "avg_ms": round(group["total_ms"] / group["count"], 2),
                "max_ms": round(group["max_ms"], 2),
                "last_ms": round(group["last_ms"], 2),
                "last_status": group["last_status"],
                "last_seen_at": group["last_seen_at"],
            }
        )

    endpoints.sort(key=lambda item: item["last_seen_at"] or "", reverse=True)
    slowest = sorted(samples, key=lambda item: item["duration_ms"], reverse=True)[:10]
    return {
        "sample_count": len(samples),
        "max_samples": MAX_LATENCY_SAMPLES,
        "endpoints": endpoints,
        "recent": limited_samples,
        "slowest": slowest,
    }


def clear_latency_samples():
    with _lock:
        _samples.clear()
