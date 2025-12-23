import os

# -----------------------------
# Environment
# -----------------------------
ENV = os.getenv("ENV", "dev")

# -----------------------------
# Ollama (LLM)
# -----------------------------

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_GENERATE_ENDPOINT = f"{OLLAMA_HOST}/v1/chat/completions"

MODEL_NAME = os.getenv("MODEL_NAME", "llama3.1")
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