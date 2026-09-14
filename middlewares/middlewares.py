import os

import redis.asyncio as redis
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from core.logger import logger

class RateLimitMiddleware(BaseHTTPMiddleware):

  async def dispatch(self, request: Request, call_next):

    if os.getenv("TESTING") == "true":
        return await call_next(request)

    client_ip = request.client.host
    rate_limit_key = f"ratelimit:ip:{client_ip}"

    # Redis client is created and managed by FastAPI lifespan.
    redis_client = request.app.state.redis

    try:
        current_requests = await redis_client.incr(rate_limit_key)

        if current_requests == 1:
            await redis_client.expire(
                rate_limit_key,
                60,
            )

        if current_requests > 20:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": (
                        "Rate limit exceeded. "
                        "Please wait a minute."
                    )
                },
            )

    except redis.ConnectionError:
      logger.warning("Redis unavailable, rate limiter bypassed")

    response = await call_next(request)
    return response

