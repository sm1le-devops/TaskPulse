import os
import redis
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import time

# Connect to Redis (in Docker it is redis_broker, locally localhost)
# decode_responses=True to work with strings
redis_url = os.getenv("REDIS_URL_BROKER", "redis://redis_broker:6379/0")
redis_client = redis.Redis.from_url(redis_url, decode_responses=True)


class RateLimitMiddleware(BaseHTTPMiddleware):

  async def dispatch(self, request: Request, call_next):
    if os.getenv("TESTING") == "true":
        return await call_next(request)
    # 1. Get the IP address of the client sending the request
    client_ip = request.client.host

    # (Optional) If you want to rate limit by authorization token instead of IP —
    # you can extract the token from request.headers.get("Authorization")

    # 2. Form a unique key for Redis based on the IP address
    rate_limit_key = f"ratelimit:ip:{client_ip}"

    try:
      # 3. Increment the request counter in Redis by 1 (atomically)
      current_requests = redis_client.incr(rate_limit_key)

      # If this is the first request in the time window — set a TTL of 60 seconds
      if current_requests == 1:
        redis_client.expire(rate_limit_key, 60)

      # 4. Check the limit (e.g., maximum 10 requests per minute from a single IP)
      if current_requests > 20:
        # If the limit is exhausted — IMMEDIATELY return a 429 error,
        # WITHOUT passing the request further to endpoints!
        return JSONResponse(
            status_code=429,
            content={
                "detail": (
                    "Rate limit exceeded. Please wait a minute."
                )
            },
        )

    except redis.ConnectionError:
      # If Redis unexpectedly goes down, so the app doesn't crash entirely,
      # we can let the request through (Fail Open) or block it
      pass

    # 5. If the limit is not exceeded — let the request pass through to the endpoint
    response = await call_next(request)
    return response