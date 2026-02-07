import logging
from logging.handlers import RotatingFileHandler
import os
import sys

LOG_FILE = os.getenv("COPILOT_LOG_FILE", "copilot.log")

logger = logging.getLogger("copilot")
logger.setLevel(logging.INFO)

if not logger.handlers:
    # 1) File logs (keep)
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3
    )
    file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(file_handler)

    # 2) Stdout logs (NEW — so docker logs shows it)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(stream_handler)

# Let it propagate if you want uvicorn to also handle it (optional)
logger.propagate = False