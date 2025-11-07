# Data Export Feature

## Overview

The YouTube Feed Aggregator includes a comprehensive data export system that allows users to download all their personal data in a structured format. The system uses a worker-based architecture to handle export generation asynchronously.

## Architecture

```
┌─────────┐    Request    ┌─────────┐    Queue    ┌──────────┐
│  User   │──────────────>│   API   │────────────>│  Redis   │
└─────────┘               └─────────┘             └──────────┘
                                                         │
                                                         │ Pop Job
                                                         ▼
┌─────────┐    Email     ┌─────────┐    Generate  ┌──────────┐
│  User   │<─────────────│  Worker │<─────────────│  Worker  │
└─────────┘              └─────────┘              └──────────┘
     │                         │
     │ Download               │ Store
     ▼                        ▼
┌─────────┐              ┌──────────┐
│ Storage │<─────────────│ Storage  │
│ (Local/ │              │ Backend  │
│  GCS)   │              └──────────┘
└─────────┘
```

## Components

### 1. API Endpoints (`app/api/routes_account.py`)

#### POST /api/account/export
- Creates a new export job
- Rate limit: 3 requests/hour
- Stores job metadata in Redis
- Returns job_id for tracking

#### GET /api/account/export/status/{job_id}
- Check export job status
- Rate limit: 60 requests/minute
- Returns: pending, processing, completed, or failed

#### GET /api/account/export/download/{filename}
- Download completed export
- Rate limit: 30 requests/minute
- Authenticated - users can only download their own exports
- Uses X-Accel-Redirect for nginx (local storage)
- Generates signed URLs for GCS

### 2. Storage Backends (`app/storage.py`)

#### LocalStorageBackend
- Stores exports on local filesystem
- Default path: `./exports`
- Uses nginx X-Accel-Redirect for efficient serving
- Security: Path traversal protection

#### GCSStorageBackend
- Stores exports in Google Cloud Storage
- Generates signed URLs (1 hour validity)
- Optional: requires `google-cloud-storage` package

### 3. Export Worker (`app/export_worker.py`)

The worker runs continuously:
1. **Poll queue**: Monitors `yt:export:queue` (BRPOP with 5s timeout)
2. **Process job**: Fetch user data, create ZIP, upload to storage
3. **Send email**: Notify user when export is ready
4. **Cleanup**: Delete expired exports (runs hourly)

#### Export ZIP Contents
- `profile.json` - User profile data
- `subscriptions.json` - Channel subscriptions
- `watched_videos.json` - Watch history
- `README.txt` - Export information

### 4. Redis Data Structure

```
yt:export:queue → List (FIFO) of job IDs
yt:export:job:{job_id} → Hash with:
  - user_id
  - email
  - status (pending|processing|completed|failed)
  - created_at
  - completed_at (if completed)
  - storage_id (if completed)
  - download_url (if completed)
  - error (if failed)
```

## Configuration

### Environment Variables

```bash
# Storage Backend
YT_EXPORT_STORAGE_BACKEND=local  # or "gcs"
YT_EXPORT_LOCAL_PATH=./exports
YT_EXPORT_URL_BASE=http://localhost:8000
YT_EXPORT_TTL_HOURS=24

# Google Cloud Storage (if using GCS)
YT_GCS_BUCKET_NAME=your-bucket-name
YT_GCS_CREDENTIALS_FILE=/path/to/credentials.json
```

## Deployment

### Running with Docker Compose

```bash
# Start all services (web + worker + nginx)
docker-compose up -d

# View worker logs
docker-compose logs -f worker

# Scale workers
docker-compose up -d --scale worker=3
```

### Running Standalone

```bash
# Start worker
python -m app.export_worker

# Or with container
docker run your-image worker
```

### Nginx Configuration

For local storage with X-Accel-Redirect:

```nginx
location /internal/exports/ {
    internal;
    alias /path/to/exports/;
    add_header Content-Disposition "attachment";
}
```

The backend returns `X-Accel-Redirect: /internal/exports/filename.zip` and nginx serves the file directly, bypassing the application server for efficiency.

## Storage Backend Comparison

| Feature | Local | GCS |
|---------|-------|-----|
| Cost | Free | Pay per GB |
| Scalability | Limited by disk | Unlimited |
| Multi-region | No | Yes |
| Setup complexity | Simple | Requires GCP account |
| Best for | Single server, dev | Production, multi-server |

## Security Features

✅ **Authentication**: All endpoints require valid session
✅ **Authorization**: Users can only access their own exports
✅ **Rate limiting**: Prevents abuse (3 exports/hour)
✅ **Path traversal protection**: Validates filenames
✅ **Signed URLs**: GCS URLs expire after 1 hour
✅ **Automatic cleanup**: Deletes exports after TTL

## Monitoring

### Key Metrics to Track

- Queue length: `LLEN yt:export:queue`
- Job completion rate
- Storage disk usage (local) or GCS costs
- Worker process health
- Email delivery rate

### Logs

```bash
# Worker logs
docker-compose logs -f worker

# View failed jobs
redis-cli KEYS "yt:export:job:*" | xargs redis-cli HGETALL
```

## Troubleshooting

### Worker not processing jobs
```bash
# Check if worker is running
docker-compose ps worker

# Check Redis connection
redis-cli PING

# Check queue
redis-cli LLEN yt:export:queue
```

### Exports not accessible
- Local: Verify nginx X-Accel-Redirect configuration
- GCS: Check service account permissions
- Both: Verify `YT_EXPORT_URL_BASE` matches public URL

### Email not sending
- Check Mailgun configuration
- View worker logs for email errors
- Note: Export is still created even if email fails

## Future Enhancements

- [ ] Support for more storage backends (S3, Azure Blob)
- [ ] Progress tracking for large exports
- [ ] Incremental exports (only new data since last export)
- [ ] Custom export formats (CSV, SQL)
- [ ] Webhook notifications instead of email
- [ ] Admin dashboard for monitoring exports
