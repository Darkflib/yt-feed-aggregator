# Deployment Guide - YouTube Feed Aggregator

This guide covers containerized deployment of the YouTube Feed Aggregator using Podman or Docker.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Building the Container](#building-the-container)
- [Local Development with Compose](#local-development-with-compose)
- [Production Deployment](#production-deployment)
- [Environment Configuration](#environment-configuration)
- [Database Migrations](#database-migrations)
- [Reverse Proxy Setup](#reverse-proxy-setup)
- [Monitoring and Health Checks](#monitoring-and-health-checks)
- [Troubleshooting](#troubleshooting)

## Prerequisites

- **Podman** (recommended) or **Docker**
- **Podman Compose** or **Docker Compose** (for local development)
- **PostgreSQL 16** (for production)
- **Redis 7** (for caching)
- **Nginx** or similar reverse proxy (for production)

## Building the Container

### Build with Podman

```bash
# From project root
podman build -t yt-feed-aggregator:latest -f Containerfile .

# Or build with specific tag
podman build -t ghcr.io/youruser/yt-feed-aggregator:v1.0.0 -f Containerfile .
```

### Build with Docker

```bash
# From project root
docker build -t yt-feed-aggregator:latest -f Containerfile .
```

### Multi-stage Build Details

The `Containerfile` uses a multi-stage build:

1. **Stage 1 (frontend)**: Builds the React frontend using Node.js 20
   - Installs npm dependencies
   - Compiles TypeScript and builds production bundle
   - Outputs to `dist/` directory

2. **Stage 2 (backend)**: Creates the Python backend image
   - Uses Python 3.13 slim
   - Installs `uv` for fast dependency management
   - Installs Python dependencies from `pyproject.toml`
   - Copies backend source code
   - Copies built frontend from stage 1 to `static/`
   - Exposes port 8080
   - Includes health check on `/healthz`

## Local Development with Compose

The `compose.yaml` file provides a complete local development environment with all services.

### Start All Services

```bash
# From project root
podman-compose up -d

# Or with Docker
docker-compose up -d
```

This starts:
- **api**: FastAPI backend (port 8080)
- **redis**: Redis cache (port 6379)
- **db**: PostgreSQL database (port 5432)

### Run Database Migrations

```bash
# Run migrations in the api container
podman-compose exec api alembic upgrade head

# Or with Docker
docker-compose exec api alembic upgrade head
```

### View Logs

```bash
# All services
podman-compose logs -f

# Specific service
podman-compose logs -f api

# Or with Docker
docker-compose logs -f api
```

### Stop Services

```bash
podman-compose down

# Or remove volumes as well
podman-compose down -v
```

### Access the Application

- **Frontend/API**: http://localhost:8080
- **Health Check**: http://localhost:8080/healthz
- **API Docs**: http://localhost:8080/docs

## Production Deployment

### 1. Prepare Environment File

Create a production environment file (e.g., `/srv/yt-feed-aggregator/.env`):

```bash
# Security keys (REQUIRED - generate secure random keys)
YT_APP_SECRET_KEY=your-production-secret-key-here
YT_TOKEN_ENC_KEY=your-32-byte-encryption-key-here

# Google OAuth (REQUIRED - from Google Cloud Console)
YT_GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
YT_GOOGLE_CLIENT_SECRET=your-client-secret
YT_GOOGLE_REDIRECT_URI=https://yourdomain.com/auth/callback

# Database (REQUIRED - use PostgreSQL in production)
YT_DATABASE_URL=postgresql+asyncpg://yt_user:secure_password@localhost:5432/yt_feed_aggregator

# Redis (REQUIRED)
YT_REDIS_URL=redis://localhost:6379/0

# Feed settings
YT_FEED_TTL_SECONDS=1800
YT_FEED_TTL_SPLAY_MAX=780
YT_SUBS_REFRESH_MINUTES=60
YT_INCLUDE_SHORTS=false

# Pagination
YT_PAGE_SIZE_DEFAULT=24
YT_PAGE_SIZE_MAX=60

# CORS (adjust for your domain)
YT_FRONTEND_ORIGIN=https://yourdomain.com

# Environment
YT_ENV=prod
```

### 2. Generate Secure Keys

```bash
# Generate secret key
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate encryption key
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Deploy with Podman Script

Use the provided deployment script:

```bash
# Set environment variables (optional, or edit the script)
export IMAGE_NAME="ghcr.io/youruser/yt-feed-aggregator:latest"
export CONTAINER_NAME="yt-feed-aggregator"
export ENV_FILE="/srv/yt-feed-aggregator/.env"
export HOST_PORT="8080"

# Run deployment script
./ops/podman_run.sh
```

The script will:
1. Pull the latest image
2. Stop and remove existing container
3. Start new container with restart policy
4. Wait for health check to pass
5. Display container status

### 4. Manual Deployment

Alternatively, deploy manually:

```bash
# Pull image
podman pull ghcr.io/youruser/yt-feed-aggregator:latest

# Stop existing container
podman stop yt-feed-aggregator || true
podman rm yt-feed-aggregator || true

# Run container
podman run -d \
  --name yt-feed-aggregator \
  -p 8080:8080 \
  --env-file=/srv/yt-feed-aggregator/.env \
  --restart=always \
  ghcr.io/youruser/yt-feed-aggregator:latest
```

## Environment Configuration

### Required Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `YT_APP_SECRET_KEY` | Secret key for JWT tokens | Random 32+ char string |
| `YT_TOKEN_ENC_KEY` | Encryption key for tokens | Random 32+ char string |
| `YT_GOOGLE_CLIENT_ID` | Google OAuth client ID | `*.apps.googleusercontent.com` |
| `YT_GOOGLE_CLIENT_SECRET` | Google OAuth secret | From Google Console |
| `YT_DATABASE_URL` | Database connection URL | `postgresql+asyncpg://...` |
| `YT_REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |
| `YT_FRONTEND_ORIGIN` | CORS origin for frontend | `https://yourdomain.com` |

### Optional Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `YT_FEED_TTL_SECONDS` | `1800` | Feed cache TTL in seconds |
| `YT_FEED_TTL_SPLAY_MAX` | `780` | Max random splay for TTL |
| `YT_SUBS_REFRESH_MINUTES` | `60` | Subscription refresh interval |
| `YT_INCLUDE_SHORTS` | `false` | Include YouTube Shorts |
| `YT_PAGE_SIZE_DEFAULT` | `24` | Default page size |
| `YT_PAGE_SIZE_MAX` | `60` | Maximum page size |
| `YT_ENV` | `dev` | Environment (dev/prod) |

## Database Migrations

### Run Migrations in Container

```bash
# With Podman
podman exec yt-feed-aggregator alembic upgrade head

# With Docker
docker exec yt-feed-aggregator alembic upgrade head

# With Compose
podman-compose exec api alembic upgrade head
```

### Create New Migration

```bash
# Generate migration from model changes
podman exec yt-feed-aggregator alembic revision --autogenerate -m "description"

# Create empty migration
podman exec yt-feed-aggregator alembic revision -m "description"
```

### Check Migration Status

```bash
podman exec yt-feed-aggregator alembic current
podman exec yt-feed-aggregator alembic history
```

## Reverse Proxy Setup

### Nginx Configuration

Use the provided nginx configuration snippet:

1. Copy the snippet:
   ```bash
   sudo cp ops/nginx_snippet.conf /etc/nginx/snippets/yt-feed-aggregator.conf
   ```

2. Create server block `/etc/nginx/sites-available/yt-feed-aggregator`:
   ```nginx
   server {
       listen 443 ssl http2;
       server_name yourdomain.com;

       ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

       # Include YouTube Feed Aggregator configuration
       include /etc/nginx/snippets/yt-feed-aggregator.conf;
   }

   # Redirect HTTP to HTTPS
   server {
       listen 80;
       server_name yourdomain.com;
       return 301 https://$server_name$request_uri;
   }
   ```

3. Enable the site:
   ```bash
   sudo ln -s /etc/nginx/sites-available/yt-feed-aggregator /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl reload nginx
   ```

### SSL/TLS with Let's Encrypt

```bash
# Install certbot
sudo apt-get install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d yourdomain.com

# Auto-renewal is configured automatically
```

## Monitoring and Health Checks

### Health Check Endpoints

- **Health**: `GET /healthz` - Basic health check
- **Readiness**: `GET /readyz` - Readiness check

### Check Container Health

```bash
# Container health status
podman ps -f name=yt-feed-aggregator

# Detailed health information
podman inspect --format='{{.State.Health.Status}}' yt-feed-aggregator

# Health check logs
podman inspect --format='{{json .State.Health}}' yt-feed-aggregator | jq
```

### Manual Health Check

```bash
# Direct check
curl http://localhost:8080/healthz

# Expected response
{"ok": true}
```

### Container Logs

```bash
# Follow logs
podman logs -f yt-feed-aggregator

# Last 100 lines
podman logs --tail 100 yt-feed-aggregator

# With timestamps
podman logs -f --timestamps yt-feed-aggregator
```

## Troubleshooting

### Container Won't Start

1. **Check logs**:
   ```bash
   podman logs yt-feed-aggregator
   ```

2. **Verify environment variables**:
   ```bash
   podman exec yt-feed-aggregator env | grep YT_
   ```

3. **Check port availability**:
   ```bash
   sudo netstat -tulpn | grep 8080
   ```

### Database Connection Issues

1. **Test database connectivity**:
   ```bash
   podman exec yt-feed-aggregator python -c "from app.db.session import get_session; print('OK')"
   ```

2. **Check database URL format**:
   - PostgreSQL: `postgresql+asyncpg://user:pass@host:5432/dbname`
   - SQLite (dev only): `sqlite+aiosqlite:///./dev.db`

3. **Verify database is accessible from container**:
   ```bash
   podman exec yt-feed-aggregator ping -c 3 your-db-host
   ```

### Redis Connection Issues

1. **Test Redis connectivity**:
   ```bash
   podman exec yt-feed-aggregator python -c "import redis; r=redis.from_url('redis://localhost:6379/0'); r.ping(); print('OK')"
   ```

2. **Check Redis URL format**:
   - Local: `redis://localhost:6379/0`
   - With auth: `redis://:password@host:6379/0`

### Static Files Not Serving

1. **Verify static directory exists**:
   ```bash
   podman exec yt-feed-aggregator ls -la /app/static
   ```

2. **Check mount in main.py**:
   ```bash
   podman exec yt-feed-aggregator cat main.py | grep static
   ```

3. **Test static file access**:
   ```bash
   curl http://localhost:8080/static/index.html
   ```

### Permission Issues

If running rootless Podman:

```bash
# Ensure proper permissions on .env file
chmod 600 /srv/yt-feed-aggregator/.env

# Check SELinux context (if applicable)
ls -Z /srv/yt-feed-aggregator/.env
```

### Health Check Failing

1. **Check health check endpoint directly**:
   ```bash
   curl -v http://localhost:8080/healthz
   ```

2. **Verify curl is available in container**:
   ```bash
   podman exec yt-feed-aggregator curl --version
   ```

3. **Check application logs for errors**:
   ```bash
   podman logs yt-feed-aggregator | grep ERROR
   ```

## Performance Tuning

### Container Resources

Limit container resources:

```bash
podman run -d \
  --name yt-feed-aggregator \
  --cpus=2 \
  --memory=1g \
  --memory-swap=1g \
  -p 8080:8080 \
  --env-file=/srv/yt-feed-aggregator/.env \
  ghcr.io/youruser/yt-feed-aggregator:latest
```

### Uvicorn Workers

Adjust worker count via command override:

```bash
podman run -d \
  --name yt-feed-aggregator \
  -p 8080:8080 \
  --env-file=/srv/yt-feed-aggregator/.env \
  ghcr.io/youruser/yt-feed-aggregator:latest \
  uvicorn main:app --host 0.0.0.0 --port 8080 --workers 4
```

## Backup and Recovery

### Database Backup

```bash
# Backup PostgreSQL database
podman-compose exec db pg_dump -U yt yt_simple > backup_$(date +%Y%m%d).sql

# Or from host
pg_dump -h localhost -U yt -d yt_simple > backup_$(date +%Y%m%d).sql
```

### Restore Database

```bash
# Restore from backup
podman-compose exec -T db psql -U yt yt_simple < backup_20250101.sql

# Or from host
psql -h localhost -U yt -d yt_simple < backup_20250101.sql
```

## Updates and Rollbacks

### Update to New Version

```bash
# Pull new image
podman pull ghcr.io/youruser/yt-feed-aggregator:v2.0.0

# Stop current container
podman stop yt-feed-aggregator

# Tag current image as backup
podman tag yt-feed-aggregator:latest yt-feed-aggregator:backup

# Start with new version
IMAGE_NAME=ghcr.io/youruser/yt-feed-aggregator:v2.0.0 ./ops/podman_run.sh

# Run migrations if needed
podman exec yt-feed-aggregator alembic upgrade head
```

### Rollback

```bash
# Stop current container
podman stop yt-feed-aggregator && podman rm yt-feed-aggregator

# Start previous version
podman run -d \
  --name yt-feed-aggregator \
  -p 8080:8080 \
  --env-file=/srv/yt-feed-aggregator/.env \
  --restart=always \
  yt-feed-aggregator:backup

# Rollback migrations if needed
podman exec yt-feed-aggregator alembic downgrade -1
```

## Support

For issues and questions:
- Check logs: `podman logs yt-feed-aggregator`
- Review health: `curl http://localhost:8080/healthz`
- GitHub Issues: [your-repo-url]

## License

[Your License Here]
