import logging
from logging.handlers import RotatingFileHandler
import os

LOG_FILE = os.getenv("COPILOT_LOG_FILE", "copilot.log")

logger = logging.getLogger("llm_co")
logger.setLevel(logging.INFO)

# Prevent duplicate handlers when using uvicorn --reload
if not logger.handlers:
    handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3
    )
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

logger.propagate = False