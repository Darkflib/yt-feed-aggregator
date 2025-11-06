# 🧭 yt-simple

[![CI/CD Pipeline](https://github.com/darkflib/yt-feed-aggregator/workflows/CI/CD%20Pipeline/badge.svg)](https://github.com/darkflib/yt-feed-aggregator/actions/workflows/ci.yml)
[![Release](https://github.com/darkflib/yt-feed-aggregator/workflows/Release/badge.svg)](https://github.com/darkflib/yt-feed-aggregator/actions/workflows/release.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Container](https://ghcr-badge.egpl.dev/darkflib/yt-feed-aggregator/latest_tag?color=%2344cc11&ignore=latest&label=container&trim=)](https://github.com/darkflib/yt-feed-aggregator/pkgs/container/yt-feed-aggregator)

**Purpose:**
yt-simple is a small web utility that removes the noise from YouTube's recommendation feed.
It logs into your Google account, fetches your **subscriptions**, retrieves their **RSS feeds**, and presents a clean, paginated, **dark-mode** interface showing only the newest videos — no Shorts, no recommendations, no clutter.

---

## 🚀 Features (MVP)

| Type                      | Description                                                      |
| ------------------------- | ---------------------------------------------------------------- |
| 🔐 **Google Login**       | OAuth 2.0 via Google (YouTube read-only scope).                  |
| 📺 **Subscription Fetch** | Uses YouTube Data API to list channels you follow.               |
| 📰 **Feed Aggregation**   | Pulls and caches each channel’s RSS feed (30–43 min TTL).        |
| 🧮 **Unified Timeline**   | Merges all videos, sorted chronologically, excluding Shorts.     |
| ⚡ **Pagination**          | Cursor-based paging for infinite scrolling or next/prev buttons. |
| 🌑 **Clean UI**           | SPA with grid/list toggle, channel sidebar, dark mode default.   |
| 🧠 **Cache-Aware**        | Redis caching for RSS and oEmbed data.                           |
| 🐳 **Containerized**      | Single image build for Podman or Docker.                         |

---

## 🏗 Architecture Overview

```
                        ┌────────────────────┐
                        │ Google OAuth 2.0   │
                        │ + YouTube Data API │
                        └─────────┬──────────┘
                                  │ access token
                         ┌────────▼────────┐
                         │   FastAPI API   │
                         │────────────────│
                         │ Auth, Feeds,   │
                         │ Cache, DB      │
                         └──────┬─────────┘
                                │ REST/JSON
                    ┌───────────▼────────────┐
                    │        SPA (React)     │
                    │  Feed, Grid/List, UX   │
                    └────────────────────────┘

     ┌────────────┐   ┌────────────┐   ┌─────────────┐
     │ PostgreSQL │←→│ SQLAlchemy  │←→│ User/Channel │
     └────────────┘   └────────────┘   └─────────────┘
             ▲
             │
     ┌────────────┐
     │   Redis    │  (RSS + oEmbed cache)
     └────────────┘
```

---

## 🧩 Repository Structure

```
app/
 ├── api/             # FastAPI routers
 ├── auth/            # Google OAuth logic
 ├── config.py        # Global settings
 ├── db/              # SQLAlchemy models + session
 ├── feed/            # Aggregation + pagination
 ├── rss/             # RSS fetching + caching
 ├── youtube/         # YouTube Data API wrapper
 └── main.py          # FastAPI entrypoint
frontend/
 ├── src/             # React + Tailwind SPA
 └── vite.config.ts
tests/
 └── ...              # pytest + vitest suites
Containerfile
.github/workflows/
.env.example
```

---

## ⚙️ Stack Summary

| Layer     | Technology                                             |
| --------- | ------------------------------------------------------ |
| Backend   | Python 3.13 + FastAPI + SQLAlchemy 2.x + Redis asyncio |
| Frontend  | React + Vite + Tailwind (dark-first)                   |
| Auth      | Google OAuth 2 (Authlib)                               |
| Cache     | Redis 7                                                |
| Database  | SQLite (dev) / Postgres 16 (prod)                      |
| Container | Podman or Docker, multi-stage build                    |
| CI/CD     | GitHub Actions → GHCR publish                          |

---

## 🧰 Quick Start (Local Dev)

### 1️⃣ Prerequisites

* Python ≥ 3.13
* Node ≥ 20
* Redis ≥ 7
* (Optional) PostgreSQL for full persistence

### 2️⃣ Environment setup

```bash
cp .env.example .env
# edit with your Google OAuth creds
```

Minimal `.env` example:

```
YT_APP_SECRET_KEY=supersecret
YT_TOKEN_ENC_KEY=changeme
YT_GOOGLE_CLIENT_ID=123.apps.googleusercontent.com
YT_GOOGLE_CLIENT_SECRET=abcdef
YT_GOOGLE_REDIRECT_URI=http://localhost:8080/auth/callback
YT_DATABASE_URL=sqlite+aiosqlite:///./dev.db
YT_REDIS_URL=redis://localhost:6379/0
YT_FEED_TTL_SECONDS=1800
YT_FEED_TTL_SPLAY_MAX=780
```

### 3️⃣ Run Redis

```bash
podman run -d --name redis -p 6379:6379 redis:7
```

### 4️⃣ Launch backend

```bash
uvicorn app.main:app --reload --port 8080
```

### 5️⃣ Launch frontend

```bash
cd frontend
npm ci
npm run dev
```

Frontend defaults to `http://localhost:5173`, backend to `http://localhost:8080`.

---

## 🧪 Testing

```bash
pytest -q
npm test
```

Integration tests use a mock YouTube API and in-memory Redis.
Use `pytest --disable-warnings -v` for detailed coverage.

---

## 🐋 Deployment

### Build + run container

```bash
podman build -t yt-simple .
podman run -d -p 8080:8080 \
  --env-file=.env \
  --name yt-simple \
  yt-simple
```

### Health check

```
curl http://localhost:8080/healthz
# → {"ok": true}
```

### Behind Nginx (snippet)

```nginx
location / {
  proxy_pass http://127.0.0.1:8080;
  proxy_set_header Host $host;
  proxy_set_header X-Forwarded-Proto $scheme;
}
```

---

## 🔄 CI/CD Flow

The project includes a comprehensive CI/CD pipeline via GitHub Actions:

### Pipeline Stages

1. **Lint & Type Check**
   - Python: `ruff` (linting), `mypy` (type checking)
   - Frontend: `ESLint`, `TypeScript` type checking

2. **Test**
   - Backend: `pytest` with coverage reporting
   - Tested against Python 3.12 and 3.13
   - Uses Redis and PostgreSQL service containers

3. **Build**
   - Frontend: Vite build validation
   - Container: Multi-platform (amd64, arm64) build

4. **Security**
   - CodeQL SAST scanning
   - Container vulnerability scanning with Trivy
   - SBOM generation for releases

5. **Publish**
   - Pushes to GitHub Container Registry (GHCR)
   - Tags: SHA, branch name, version, and `latest`
   - Image: `ghcr.io/darkflib/yt-feed-aggregator:latest`

### Automated Releases

Version tags (`v*.*.*`) trigger the release workflow:
- Builds and pushes versioned container images
- Generates changelog from git history or CHANGELOG.md
- Creates GitHub release with SBOM artifacts
- Multi-platform container images (amd64, arm64)

### Dependency Management

Dependabot automatically:
- Updates Python dependencies weekly
- Updates npm packages weekly
- Updates GitHub Actions weekly
- Groups related updates for easier review

For more details, see [CI.md](CI.md).

---

## 🧠 Design Notes

* **Caching:**
  Feeds cached for 30–43 min (randomized splay) to desynchronize refreshes.
  oEmbed cached 24 h.
* **Shorts filter:**
  Exclude URLs containing `/shorts/` and any clip < 90 s.
* **Pagination:**
  Cursor-based (timestamp + video_id).
* **Security:**
  AES-GCM encryption for refresh tokens; secure cookies; minimal scopes (`youtube.readonly`).
* **Extensibility:**
  Database-agnostic (SQLite→Postgres); reusable RSS cache; modular routers.

---

## 🧭 Development Roadmap

| Phase | Feature                                |
| ----- | -------------------------------------- |
| ✅ MVP | Subscriptions → Feeds → Paginated UI   |
| 🔜 v2 | Mark-as-watched, Channel search/filter |
| 🔜 v3 | Progressive Web App (offline mode)     |
| 🔜 v4 | Optional notifications or web push     |

---

## 🧾 License & Credits

MIT © 2025 – yt-simple contributors.
Inspired by minimal feed-readers and the desire to *just watch what you subscribed to*.

