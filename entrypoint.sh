#!/bin/bash
# Entrypoint script for YouTube Feed Aggregator container
# Supports running as either web server or export worker

set -e

MODE="${1:-web}"

case "$MODE" in
    web)
        echo "Starting web server..."
        exec uvicorn main:app --host 0.0.0.0 --port 8080
        ;;
    worker)
        echo "Starting export worker..."
        exec python -m app.export_worker
        ;;
    *)
        echo "Error: Unknown mode '$MODE'"
        echo "Usage: $0 [web|worker]"
        exit 1
        ;;
esac
