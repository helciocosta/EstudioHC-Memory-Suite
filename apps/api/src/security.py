from time import monotonic
from collections import defaultdict, deque
from fastapi import Header, HTTPException, Request

from .config import settings


def require_api_key(x_api_key: str = Header(default="")):
    if settings.API_KEY and x_api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True


_requests: dict[str, deque[float]] = defaultdict(deque)


async def rate_limiter(request: Request):
    if not settings.API_KEY:
        return
    ip = request.client.host if request.client else "unknown"
    now = monotonic()
    dq = _requests[ip]
    while dq and now - dq[0] > 60:
        dq.popleft()
    if len(dq) >= settings.RATE_LIMIT_PER_MIN:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    dq.append(now)
