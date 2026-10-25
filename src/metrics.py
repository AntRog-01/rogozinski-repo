# ai-generated: 90% - RED metrics and Prometheus text exposition format implementation
import time
import threading
from typing import Dict, Tuple, List, Optional, Any

# Designed ladder for login antrog-01 (measured q = 212.5 ms):
# 28 finite boundaries (< 30 limit):
# Fine resolution across [180ms, 260ms] covering ±10% around q (191ms to 234ms)
# with 10ms bucket widths (relative width 4.7% <= 20% limit).
# Includes threshold 0.25 for latency SLI.
DESIGNED_LADDER: List[float] = [
    0.005, 0.01, 0.015, 0.02, 0.025, 0.03, 0.035, 0.04, 0.05, 0.075, 0.1, 0.15,
    0.18, 0.19, 0.20, 0.21, 0.22, 0.23, 0.24, 0.25, 0.26, 0.28, 0.30,
    0.40, 0.50, 0.75, 1.0, 2.0
]

class RequestHistogram:
    def __init__(self, ladder: Optional[List[float]] = None):
        self.ladder = ladder if ladder is not None else list(DESIGNED_LADDER)
        self.lock = threading.Lock()
        # Key: (method, route, status_code)
        # Value: {"count": int, "sum": float, "buckets": {boundary: int}}
        self.data: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

    def set_ladder(self, new_ladder: List[float]):
        with self.lock:
            self.ladder = sorted(list(new_ladder))
            self.data.clear()

    def observe(self, method: str, route: str, status_code: str, duration_seconds: float):
        with self.lock:
            key = (method, route, status_code)
            if key not in self.data:
                self.data[key] = {
                    "count": 0,
                    "sum": 0.0,
                    "buckets": {b: 0 for b in self.ladder}
                }
            entry = self.data[key]
            entry["count"] += 1
            entry["sum"] += duration_seconds
            for b in self.ladder:
                if duration_seconds <= b:
                    entry["buckets"][b] += 1

    def generate_prometheus_text(self) -> str:
        lines: List[str] = [
            "# HELP http_server_request_duration_seconds Request duration in seconds",
            "# TYPE http_server_request_duration_seconds histogram"
        ]
        with self.lock:
            for (method, route, status_code), entry in sorted(self.data.items()):
                labels_str = f'http_request_method="{method}",http_response_status_code="{status_code}",http_route="{route}"'
                cumulative = 0
                for b in self.ladder:
                    b_str = f"{b:.6f}".rstrip("0").rstrip(".")
                    if "." not in b_str and "e" not in b_str:
                        b_str += ".0"
                    count = entry["buckets"][b]
                    lines.append(f'http_server_request_duration_seconds_bucket{{{labels_str},le="{b_str}"}} {count}')
                lines.append(f'http_server_request_duration_seconds_bucket{{{labels_str},le="+Inf"}} {entry["count"]}')
                lines.append(f'http_server_request_duration_seconds_sum{{{labels_str}}} {entry["sum"]:.6f}')
                lines.append(f'http_server_request_duration_seconds_count{{{labels_str}}} {entry["count"]}')
        return "\n".join(lines) + "\n"

histogram = RequestHistogram()
