import json
import os
import redis

# Get cache URL from environment variable (database /1)
REDIS_CACHE_URL = os.getenv("REDIS_URL_CACHE", "redis://localhost:6379/1")

# Create a single client for cache and rate limiting with string decoding
redis_cache = redis.Redis.from_url(REDIS_CACHE_URL, decode_responses=True)


def get_cached_tasks(user_id: int):
  """Retrieves the cached task list of the user from Redis (Cache Hit).

  If there is no cache, returns None (Cache Miss).
  """
  cached_data = redis_cache.get(f"cache:tasks:user:{user_id}")
  if cached_data:
    return json.loads(cached_data)
  return None


def set_cached_tasks(user_id: int, tasks_data: list):
  """Saves the user's task list in Redis with a 60-second TTL."""
  redis_cache.set(
    name=f"cache:tasks:user:{user_id}", value=json.dumps(tasks_data), ex=60
  )


def invalidate_user_cache(user_id: int):
  """Forcefully deletes (invalidates) the user's task cache.

  Called upon creating, updating, or deleting a task.
  """
  redis_cache.delete(f"cache:tasks:user:{user_id}")