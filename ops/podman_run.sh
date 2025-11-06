#!/usr/bin/env bash
# Podman run script for YouTube Feed Aggregator
# This script pulls the latest image and runs the container

set -euo pipefail

IMAGE="${IMAGE:-ghcr.io/darkflib/yt-feed-aggregator:latest}"
CONTAINER_NAME="${CONTAINER_NAME:-yt-aggregator}"
PORT="${PORT:-8080}"
ENV_FILE="${ENV_FILE:-/srv/yt-aggregator/.env}"

echo "Starting YouTube Feed Aggregator deployment..."
echo "Image: $IMAGE"
echo "Container: $CONTAINER_NAME"
echo "Port: $PORT"

# Pull latest image
echo "Pulling latest image..."
podman pull "$IMAGE"

# Stop existing container if running
if podman ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Stopping existing container..."
    podman stop "$CONTAINER_NAME" || true
    echo "Removing existing container..."
    podman rm "$CONTAINER_NAME" || true
fi

# Run new container
echo "Starting new container..."
podman run -d \
    --name "$CONTAINER_NAME" \
    -p "${PORT}:8080" \
    --env-file "$ENV_FILE" \
    --restart always \
    "$IMAGE"

# Check if container is running
sleep 2
if podman ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "✓ Container started successfully"
    podman ps --filter "name=${CONTAINER_NAME}"

    # Wait for health check
    echo "Waiting for health check..."
    for i in {1..30}; do
        if curl -sf http://localhost:${PORT}/healthz > /dev/null 2>&1; then
            echo "✓ Health check passed"
            exit 0
        fi
        echo -n "."
        sleep 1
    done
    echo ""
    echo "⚠ Health check did not pass within 30 seconds"
    echo "Container logs:"
    podman logs "$CONTAINER_NAME" | tail -20
    exit 1
else
    echo "✗ Container failed to start"
    podman logs "$CONTAINER_NAME"
    exit 1
fi
