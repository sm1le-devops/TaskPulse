import logging
import sys

# Configure log format: time, level (INFO/ERROR), module name, and message text
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

# Create a logger for our application
logger = logging.getLogger("fastapi_app")
logger.setLevel(logging.INFO)
