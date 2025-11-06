# Operations Scripts

This directory contains scripts and configuration for deploying and managing the YouTube Feed Aggregator in production.

## Contents

- `podman_run.sh` - Deploy/redeploy the container
- `update_and_restart.sh` - Check for updates and restart if needed
- `nginx_snippet.conf` - Nginx reverse proxy configuration
- `systemd/` - Systemd timer and service units for automatic updates

## Quick Start

### Initial Deployment

1. **Install scripts:**
   ```bash
   sudo cp ops/podman_run.sh /usr/local/bin/
   sudo cp ops/update_and_restart.sh /usr/local/bin/yt-aggregator-update.sh
   sudo chmod +x /usr/local/bin/podman_run.sh
   sudo chmod +x /usr/local/bin/yt-aggregator-update.sh
   ```

2. **Prepare environment:**
   ```bash
   sudo mkdir -p /srv/yt-aggregator
   sudo cp .env.example /srv/yt-aggregator/.env
   sudo nano /srv/yt-aggregator/.env  # Edit with production values
   sudo chmod 600 /srv/yt-aggregator/.env
   ```

3. **Deploy:**
   ```bash
   sudo /usr/local/bin/podman_run.sh
   ```

### Automatic Updates

Set up systemd timer for automatic updates:

```bash
sudo cp ops/systemd/*.{timer,service} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now yt-aggregator-update.timer
```

Verify:
```bash
sudo systemctl status yt-aggregator-update.timer
sudo systemctl list-timers | grep yt-aggregator
```

## Manual Operations

```bash
# Check for updates and restart if needed
sudo /usr/local/bin/yt-aggregator-update.sh

# View logs
podman logs -f yt-aggregator

# Check health
curl http://localhost:8080/healthz
```

For complete documentation, see the full README in this directory.
