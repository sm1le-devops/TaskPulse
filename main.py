from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from core.logger import logger
from middlewares.middlewares import RateLimitMiddleware
from routers import auth, reports, tasks  # Import our router with tasks
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="My Production Ready API",
    docs_url=None,  # Disables /docs
    redoc_url=None,  # Disables /redoc
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