#!/bin/sh
# =============================================================================
# ReliefOps AI — Non-Destructive Docker Container Entrypoint Script
# Verifies SQLite and ChromaDB state non-destructively before starting Streamlit.
# Never overwrites or re-seeds an existing /app/data/reliefops.db or ChromaDB.
# =============================================================================
set -e

echo "[ReliefOps AI] Running non-destructive startup verification..."
python /app/docker_entrypoint.py "$@"
