from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

REQUEST_TIME = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint", "status"]
)

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"]
)

DB_POOL_SIZE = Gauge("db_pool_size", "Current DB connection pool size")

import asyncio

def metrics_response():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)