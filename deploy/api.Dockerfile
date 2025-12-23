FROM python:3.12-slim

WORKDIR /app

# Install only runtime deps needed to run the API
RUN pip install --no-cache-dir \
    fastapi \
    "uvicorn[standard]" \
    pydantic \
    python-dotenv \
    requests \
    faker \
    python-dateutil \
    "databricks-sql-connector[pyarrow]>=4.1.1,<4.1.4"

# Copy API code
COPY api /app

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]



# FROM python:3.12-slim

# WORKDIR /app

# RUN pip install --no-cache-dir poetry

# # Copy Poetry metadata FIRST (this layer gets cached)
# COPY api/pyproject.toml api/poetry.lock* api/README.md /app/

# RUN poetry config virtualenvs.create false \
#  && poetry install --no-interaction --no-ansi

# # Copy the rest of the API code
# COPY api /app

# EXPOSE 8000
# CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]