#!/usr/bin/env bash
set -e

echo "1) Installing UI deps..."
cd ui && npm install && cd ..

echo "2) Installing dbt deps..."
cd dbt && dbt deps && cd ..

echo "3) Generating dbt manifest..."
cd dbt && dbt parse && cd ..

echo "Done."