import time
from dataclasses import dataclass

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


@dataclass
class _Bucket:
    tokens: float
    last_refill: float


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute: int = 20, burst: int = 10):
        super().__init__(app)
        self.capacity = float(burst)
        self.refill_rate = requests_per_minute / 60.0
        self.buckets: dict[str, _Bucket] = {}

    @staticmethod
    def _client_ip(request: Request) -> str:
        # Cloud Run injects X-Forwarded-For; leftmost is the original client.
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request, call_next):
        ip = self._client_ip(request)
        now = time.monotonic()
        bucket = self.buckets.get(ip)
        if bucket is None:
            bucket = _Bucket(tokens=self.capacity, last_refill=now)
            self.buckets[ip] = bucket
        else:
            elapsed = now - bucket.last_refill
            bucket.tokens = min(
                self.capacity, bucket.tokens + elapsed * self.refill_rate
            )
            bucket.last_refill = now

        if bucket.tokens < 1:
            retry_after = max(1, int((1 - bucket.tokens) / self.refill_rate) + 1)
            return JSONResponse(
                {"error": "rate_limited", "error_description": "Too Many Requests"},
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )
        bucket.tokens -= 1
        return await call_next(request)
