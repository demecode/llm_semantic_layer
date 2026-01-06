# Governed Semantic Analytics  (dbt + LLM)

An open-core prototype of a governed semantic analytics agent. Users ask natural language questions like:

> “Show Digital Solutions spend vs the rest of the company for the last 2 years”

…and get answers backed by:
- dbt semantic models & metrics
- Strict governance and role visibility
- Deterministic SQL generation
- LLM routing (Ollama-compatible)

 it’s a semantic, contract-driven analytics system.

## Repo Layout
```
.
├── api/                # FastAPI backend (routing, execution, contracts)
│   └── eng/            # routing/, semantics/, utils/, etc.
├── ui/                 # Next.js UI
├── dbt/                # dbt project (models, metrics, semantic layer)
│   ├── models/
│   ├── macros/
│   ├── profiles.yml.example
│   └── dbt_project.yml
├── eval/               # LLM evaluation harness
├── deploy/             # Dockerfiles & compose
├── docker-compose.yml
├── .env.example
└── README.md
```

## Quickstart (Local)

### 1) Prerequisites
- Python 3.12+
- Poetry
- Docker + Docker Compose
- Databricks SQL Warehouse
- Ollama (local or Docker)

### 2) Clone
```bash
git clone https://github.com/demecode/llm_semantic_layer.git
cd llm_semantic_layer
```

### 3) Configure environment variables
```bash
cp .env.example .env
```
Edit `.env`:
```
DATABRICKS_SERVER_HOSTNAME=dbc-xxxx.cloud.databricks.com
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/xxxxx
DATABRICKS_TOKEN=your_pat_here

OLLAMA_HOST=http://ollama:11434
OLLAMA_MODEL=llama3.1
```

Configure dbt profile:
```bash
cp dbt/profiles.yml.example dbt/profiles.yml
set -a
source .env
set +a
dbt debug --project-dir dbt --profiles-dir dbt
```

### 5) Generate dbt manifest
```bash
cd dbt
dbt deps
dbt build
dbt docs generate
cd ..
```
Produces `dbt/target/manifest.json`.

### 6) Run everything with Docker
```bash
docker compose up --build
```
- UI → http://localhost:3000  
- API → http://localhost:8000  
- Ollama → http://localhost:11434

## Evaluation (LLM Regression Tests)
```bash
python eval/eval.py --cases eval/test_cases.jsonl --repeats 3
```
Outputs:
- Accuracy by metric
- Parameter correctness
- CSV results for CI/CD

## Governance Guarantees
This system cannot:
- Generate raw SQL
- Access unmodelled tables
- Answer questions outside dbt metrics
- Bypass semantic constraints
- Hallucinate numbers

All results derive from dbt semantic models + metrics.

## Supported Query Types
- ✅ Single metric
- ✅ Metric comparisons
- ✅ Time filtering (last 2 years, last 6 months)
- ❌ Forecasting
- ❌ Root-cause analysis
- ❌ Arbitrary SQL

## Example Questions
- “Show total spend by month”
- “Show Digital Solutions spend vs the rest of the company”
- “Show Digital Solutions share of total spend for the last 2 years”

## Roadmap
- Metrics registry UI
- Role-based metric visibility
- Query caching
- Versioned semantic contracts
- CI-based LLM eval gates
- Multi-warehouse support

## License
Open-core  
- Core: Apache 2.0  
- Enterprise features: planned (RBAC, caching, audit)

## Contributing
PRs welcome — especially:
- More eval cases
- UI improvements
