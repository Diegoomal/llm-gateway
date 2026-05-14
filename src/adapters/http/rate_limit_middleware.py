import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        enabled: bool,
        requests_limit: int,
        window_seconds: int,
    ):
        super().__init__(app)
        self.enabled = enabled
        self.requests_limit = max(1, requests_limit)
        self.window_seconds = max(1, window_seconds)
        self.requests_by_identity = defaultdict(deque)

    async def dispatch(self, request: Request, call_next) -> Response:
        if not self.enabled:
            return await call_next(request)

        identity = self._identity_for(request)
        now = time.monotonic()
        bucket = self.requests_by_identity[identity]
        while bucket and now - bucket[0] >= self.window_seconds:
            bucket.popleft()

        remaining = self.requests_limit - len(bucket)
        if remaining <= 0:
            return JSONResponse(
                {"detail": "rate limit exceeded"},
                status_code=429,
                headers={
                    "Retry-After": str(self.window_seconds),
                    "X-RateLimit-Limit": str(self.requests_limit),
                    "X-RateLimit-Remaining": "0",
                },
            )

        bucket.append(now)
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.requests_limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining - 1)
        return response

    def _identity_for(self, request: Request) -> str:
        api_key = request.headers.get("x-api-key")
        authorization = request.headers.get("authorization")
        if api_key:
            return f"api_key:{api_key}"
        if authorization:
            return f"authorization:{authorization}"
        client = request.client.host if request.client else "unknown"
        return f"ip:{client}"
