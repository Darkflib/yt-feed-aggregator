#!/usr/bin/env bash
# Automatic update script for YouTube Feed Aggregator
# This script checks for new image digests and restarts if changed
# Suitable for use with cron or systemd timer

set -euo pipefail

IMAGE="${IMAGE:-ghcr.io/darkflib/yt-feed-aggregator:latest}"
CONTAINER_NAME="${CONTAINER_NAME:-yt-aggregator}"

echo "[$(date -Iseconds)] Checking for updates to $IMAGE"

# Pull latest image quietly
podman pull "$IMAGE" > /dev/null 2>&1

# Get new and current digests
NEW_DIGEST=$(podman inspect "$IMAGE" --format '{{.Digest}}' 2>/dev/null || echo "")
CUR_DIGEST=$(podman inspect "$CONTAINER_NAME" --format '{{.ImageDigest}}' 2>/dev/null || echo "")

if [ -z "$NEW_DIGEST" ]; then
    echo "[$(date -Iseconds)] ERROR: Failed to get new image digest"
    exit 1
fi

# Compare digests
if [ "$NEW_DIGEST" != "$CUR_DIGEST" ]; then
    echo "[$(date -Iseconds)] New image detected"
    echo "[$(date -Iseconds)]   Current: $CUR_DIGEST"
    echo "[$(date -Iseconds)]   New:     $NEW_DIGEST"

    # Run the deployment script
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    "$SCRIPT_DIR/podman_run.sh"

    if [ $? -eq 0 ]; then
        echo "[$(date -Iseconds)] ✓ Update completed successfully"
    else
        echo "[$(date -Iseconds)] ✗ Update failed"
        exit 1
    fi
else
    echo "[$(date -Iseconds)] No changes detected (digest: ${NEW_DIGEST:0:20}...)"
fi
