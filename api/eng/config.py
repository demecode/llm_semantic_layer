import os

# -----------------------------
# Environment
# -----------------------------
ENV = os.getenv("ENV", "dev")

# -----------------------------
# Ollama (LLM)
# -----------------------------
import os

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434").rstrip("/")
OLLAMA_CHAT_ENDPOINT = os.getenv("OLLAMA_CHAT_ENDPOINT", f"{OLLAMA_HOST}/api/chat")

MODEL_NAME = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
# -----------------------------
# dbt Semantic Layer
# -----------------------------
DBT_MANIFEST_PATH = os.getenv(
    "DBT_MANIFEST_PATH",
    "/app/dbt/target/manifest.json",
)

# -----------------------------
# Databricks
# -----------------------------
DATABRICKS_SERVER_HOSTNAME = os.getenv("DATABRICKS_SERVER_HOSTNAME")
DATABRICKS_HTTP_PATH = os.getenv("DATABRICKS_HTTP_PATH")
DATABRICKS_ACCESS_TOKEN = os.getenv("DATABRICKS_ACCESS_TOKEN")

# -----------------------------
# Safety / Limits
# -----------------------------
MAX_LLM_TOKENS = int(os.getenv("MAX_LLM_TOKENS", "512"))