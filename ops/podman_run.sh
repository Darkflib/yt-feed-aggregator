#!/usr/bin/env bash
#
# Podman run script for YouTube Feed Aggregator
# Example script for production deployment
#

set -e

# Configuration
IMAGE_NAME="${IMAGE_NAME:-ghcr.io/youruser/yt-feed-aggregator:latest}"
CONTAINER_NAME="${CONTAINER_NAME:-yt-feed-aggregator}"
ENV_FILE="${ENV_FILE:-/srv/yt-feed-aggregator/.env}"
HOST_PORT="${HOST_PORT:-8080}"
CONTAINER_PORT="${CONTAINER_PORT:-8080}"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}YouTube Feed Aggregator - Podman Deployment${NC}"
echo "=============================================="

# Pull latest image
echo -e "${YELLOW}Pulling latest image: ${IMAGE_NAME}${NC}"
podman pull "${IMAGE_NAME}"

# Stop existing container if running
echo -e "${YELLOW}Stopping existing container (if any)...${NC}"
podman stop "${CONTAINER_NAME}" 2>/dev/null || true
podman rm "${CONTAINER_NAME}" 2>/dev/null || true

# Run container
echo -e "${YELLOW}Starting new container: ${CONTAINER_NAME}${NC}"
podman run -d \
  --name "${CONTAINER_NAME}" \
  -p "${HOST_PORT}:${CONTAINER_PORT}" \
  --env-file="${ENV_FILE}" \
  --restart=always \
  --health-cmd="curl -f http://localhost:8080/healthz || exit 1" \
  --health-interval=30s \
  --health-timeout=3s \
  --health-retries=3 \
  "${IMAGE_NAME}"

# Wait for container to be healthy
echo -e "${YELLOW}Waiting for container to be healthy...${NC}"
for i in {1..30}; do
  HEALTH=$(podman inspect --format='{{.State.Health.Status}}' "${CONTAINER_NAME}" 2>/dev/null || echo "starting")
  if [ "$HEALTH" = "healthy" ]; then
    echo -e "${GREEN}Container is healthy!${NC}"
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo -e "${YELLOW}Warning: Container health check timed out. Check logs with: podman logs ${CONTAINER_NAME}${NC}"
  fi
  sleep 2
done

# Show container status
echo ""
echo -e "${GREEN}Container started successfully!${NC}"
echo ""
podman ps -f name="${CONTAINER_NAME}"
echo ""
echo -e "${BLUE}View logs:${NC} podman logs -f ${CONTAINER_NAME}"
echo -e "${BLUE}Stop container:${NC} podman stop ${CONTAINER_NAME}"
echo -e "${BLUE}Restart container:${NC} podman restart ${CONTAINER_NAME}"
echo -e "${BLUE}Health check:${NC} curl http://localhost:${HOST_PORT}/healthz"
