Governed Semantic Analytics Copilot (dbt + LLM)

This repository contains an open-core prototype of a governed semantic analytics agent.

It allows users to ask natural language questions like:

“Show Digital Solutions spend vs the rest of the company for the last 2 years”

…and get answers backed by:
	•	dbt semantic models & metrics
	•	Strict governance and role visibility
	•	Deterministic SQL generation
	•	LLM routing (Ollama-compatible)

This is not a chatbot over raw data.
It is a semantic, contract-driven analytics system.


.
├── api/                # FastAPI backend (routing, execution, contracts)
│   └── eng/
├── ui/                 # Next.js UI
├── dbt/                # dbt project (models, metrics, semantic layer)
│   ├── models/
│   ├── macros/
│   ├── profiles.yml.example
│   └── dbt_project.yml
├── eval/               # LLM evaluation harness
├── deploy/             # Dockerfiles
├── docker-compose.yml
├── .env.example
└── README.md


⸻

🚀 Quickstart (Local)

1. Prerequisites
	•	Python 3.12+
	•	Poetry
	•	Docker + Docker Compose
	•	Databricks SQL Warehouse
	•	Ollama (local or Docker)

git clone https://github.com/demecode/llm_semantic_layer.git
cd llm_semantic_layer