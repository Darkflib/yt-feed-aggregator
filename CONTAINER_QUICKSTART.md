# Container Quick Start Guide

Quick reference for building and running the YouTube Feed Aggregator in containers.

## Build the Container

```bash
# With Podman (recommended)
podman build -t yt-feed-aggregator:latest -f Containerfile .

# With Docker
docker build -t yt-feed-aggregator:latest -f Containerfile .
```

## Local Development (Docker Compose)

```bash
# Start all services (API, PostgreSQL, Redis)
podman-compose up -d

# Or with Docker
docker-compose up -d

# Run database migrations
podman-compose exec api alembic upgrade head

# View logs
podman-compose logs -f api

# Stop all services
podman-compose down
```

**Access the app**: http://localhost:8080

## Production Deployment

### Quick Deploy

```bash
# 1. Create production .env file
cp .env.example /srv/yt-feed-aggregator/.env
# Edit /srv/yt-feed-aggregator/.env with production values

# 2. Run deployment script
./ops/podman_run.sh
```

### Manual Deploy

```bash
# Build image
podman build -t yt-feed-aggregator:latest -f Containerfile .

# Run container
podman run -d \
  --name yt-feed-aggregator \
  -p 8080:8080 \
  --env-file=/srv/yt-feed-aggregator/.env \
  --restart=always \
  yt-feed-aggregator:latest

# Run migrations
podman exec yt-feed-aggregator alembic upgrade head
```

## Health Checks

```bash
# Check container health
curl http://localhost:8080/healthz

# Expected response
{"ok": true}

# View container status
podman ps -f name=yt-feed-aggregator

# View logs
podman logs -f yt-feed-aggregator
```

## Common Commands

```bash
# Stop container
podman stop yt-feed-aggregator

# Start container
podman start yt-feed-aggregator

# Restart container
podman restart yt-feed-aggregator

# Remove container
podman rm -f yt-feed-aggregator

# View container logs
podman logs -f yt-feed-aggregator

# Execute command in container
podman exec yt-feed-aggregator <command>

# Run migrations
podman exec yt-feed-aggregator alembic upgrade head
```

## Environment Variables

Required environment variables in `.env`:

```bash
# Security (generate with: python -c "import secrets; print(secrets.token_urlsafe(32))")
YT_APP_SECRET_KEY=your-secret-key
YT_TOKEN_ENC_KEY=your-encryption-key

# Google OAuth (from Google Cloud Console)
YT_GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
YT_GOOGLE_CLIENT_SECRET=your-secret
YT_GOOGLE_REDIRECT_URI=https://yourdomain.com/auth/callback

# Database (PostgreSQL for production)
YT_DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname

# Redis
YT_REDIS_URL=redis://localhost:6379/0

# CORS
YT_FRONTEND_ORIGIN=https://yourdomain.com
```

## Troubleshooting

### Container won't start
```bash
# Check logs for errors
podman logs yt-feed-aggregator

# Verify environment variables
podman exec yt-feed-aggregator env | grep YT_
```

### Database connection failed
```bash
# Test database connectivity
podman exec yt-feed-aggregator python -c "from sqlalchemy import create_engine; print('OK')"

# Check database URL in env
podman exec yt-feed-aggregator env | grep DATABASE_URL
```

### Health check failing
```bash
# Test health endpoint
curl -v http://localhost:8080/healthz

# Check if app is running
podman exec yt-feed-aggregator ps aux | grep uvicorn
```

## Full Documentation

See `/workspace/ops/README.md` for complete deployment documentation including:
- Nginx reverse proxy setup
- SSL/TLS configuration
- Database migrations
- Performance tuning
- Backup and recovery
- Monitoring

## Architecture

The container uses a multi-stage build:

1. **Stage 1 (frontend)**: Builds React frontend with Node.js 20
2. **Stage 2 (backend)**:
   - Python 3.13 slim base
   - Installs dependencies with `uv`
   - Copies backend code and built frontend
   - Exposes port 8080
   - Includes health checks

The final image includes:
- FastAPI backend
- Built React frontend (served from `/static`)
- Alembic migrations
- Health check endpoint at `/healthz`
