# ai-generated: 90% - RED metrics and Prometheus text exposition format implementation
import time
import threading
from typing import Dict, Tuple, List, Optional, Any

# Initial draft ladder (14 boundaries, standard Prometheus client ladder)
# Will be updated to fine resolution ladder after measuring q with load 3
DEFAULT_LADDER: List[float] = [
    0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0
]

class RequestHistogram:
    def __init__(self, ladder: Optional[List[float]] = None):
        self.ladder = ladder if ladder is not None else list(DEFAULT_LADDER)
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
                    # Format boundary for Prometheus: e.g. 1.0, 0.25
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
