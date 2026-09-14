from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from core.logger import logger
from middlewares.middlewares import RateLimitMiddleware
from routers import auth, reports, tasks  # Import our router with tasks
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os
import redis.asyncio as redis

@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_url = os.getenv(
        "REDIS_URL_BROKER",
        "redis://redis_broker:6379/0",
        )
    app.state.redis = redis.Redis.from_url(
        redis_url,
        decode_responses=True,
        socket_connect_timeout=0.5,
        socket_timeout=0.5,)
    try:
        yield
    finally:
        await app.state.redis.aclose()
        
app = FastAPI(
    title="My Production Ready API",
    docs_url=None,  
    redoc_url=None, 
    lifespan=lifespan,
)

# Include task routers to our application
app.include_router(tasks.router)
app.include_router(auth.router)
app.include_router(reports.router)

app.mount("/static", StaticFiles(directory="static"), name="static")

origins = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:52330",
    "https://taskpulse-f5zy.onrender.com",
]

# CORS должен быть добавлен ПЕРЕД кастомными middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)
        
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
  # Log the error itself at ERROR level (works for debugging)
  logger.error(
      f"Unexpected error on endpoint {request.url}: {exc}", exc_info=True
  )

  # Return a clean and safe response to the client
  return JSONResponse(
      status_code=500,
      content={
          "detail": (
              "Internal server error. We are already logging it and will fix"
              " it soon."
          )
      },
  )


@app.get("/", response_class=HTMLResponse)
def read_root():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()
    
@app.get("/health")
def health_check():
    return {"status": "ok"}