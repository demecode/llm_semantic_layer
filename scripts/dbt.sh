#!/usr/bin/env bash
set -a
source .env
set +a
cd dbt
exec poetry run dbt "$@"