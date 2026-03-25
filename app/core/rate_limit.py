from collections import defaultdict, deque
from collections.abc import Callable
from time import time

from fastapi import HTTPException, Request, status

_REQUEST_BUCKETS: dict[str, deque[float]] = defaultdict(deque)


def rate_limiter(bucket_name: str, max_requests: int, window_seconds: int) -> Callable:
    """
    Simple in-memory sliding-window rate limiter.

    Notes:
    - Good enough for local learning and interview demos.
    - In production, move this state to Redis so multiple app instances
      share the same counters.
    """

    def dependency(request: Request) -> None:
        now = time()
        client_host = request.client.host if request.client else "unknown"
        user_hint = request.headers.get("X-User-Id", client_host)
        bucket_key = f"{bucket_name}:{user_hint}"
        queue = _REQUEST_BUCKETS[bucket_key]

        while queue and now - queue[0] > window_seconds:
            queue.popleft()

        if len(queue) >= max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded for {bucket_name}.",
            )

        queue.append(now)

    return dependency
