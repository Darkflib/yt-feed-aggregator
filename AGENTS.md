Final tech stack (MVP)

Backend: Python 3.12/13, FastAPI, Uvicorn, SQLAlchemy 2.x + Alembic, Pydantic v2, Authlib (Google OAuth), httpx, feedparser (or ElementTree + defusedxml), python-jose/itsdangerous (session), cryptography (token-at-rest).

DB: SQLAlchemy ORM w/ SQLite (dev) and Postgres (optional prod); single dialect via SQLAlchemy.

Cache: Redis (feeds + oEmbed + small auth caches).

Frontend: React + Vite + TypeScript + Tailwind (dark-first), Headless UI / Radix for simple components.

Container: Multi-stage build; run with Podman behind your reverse proxy.

CI/CD: GitHub Actions → build & test → push to GHCR → podman pull & restart.

Architecture overview

Auth layer: Google OAuth (Authorization Code + PKCE). Minimal scopes: openid email profile + https://www.googleapis.com/auth/youtube.readonly.

Data flow:

Fetch user subscriptions via YouTube Data API (server-side) and store channel IDs per user.

For each channel, fetch RSS feed → parse → cache (Redis) with TTL 30m + randomized splay 13m (configurable).

Merge all cached items across user’s channels → sort desc by publish date.

Filter out Shorts (heuristics below).

Return paginated JSON to SPA. SPA renders embeds (we can skip oEmbed initially and use canonical YouTube iframe; keep oEmbed as fallback/feature flag).

Data model (lean)

SQLAlchemy models:

User
id (uuid), google_sub (unique), email, display_name, avatar_url, refresh_token_enc, created_at, updated_at

UserChannel (subscriptions snapshot)
id, user_id (fk), channel_id, channel_title, channel_custom_url, added_at, active (bool)
We can refresh and soft-toggle active if a user unsubscribes.

(Optional later) VideoSeen
id, user_id, video_id, seen_at (for “mark as watched” in v2)

Redis keys (namespaced):

yt:feed:{channel_id} → list of items (JSON) + TTL 30–43m

yt:oembed:{video_id} → oEmbed JSON + TTL (e.g., 24h)

yt:subs:{user_id} → cached list of channel_ids + short TTL (e.g., 10m) to reduce API hits

API surface (MVP)

GET /auth/login → redirect to Google

GET /auth/callback → handle code, store refresh token, issue signed session cookie/JWT

POST /auth/logout

GET /api/me → identity summary

POST /api/subscriptions/refresh → pull subscriptions from YouTube Data API, upsert UserChannel

GET /api/subscriptions → list channels for side-filter

GET /api/feed
Query params: channel_id?, limit=24, cursor?
Behavior: merges (or single channel if provided), filters Shorts, sorts desc, returns cursor-based page

GET /healthz / GET /readyz

Pagination (cursor-based):
Cursor encodes (published_at, video_id) so paging is stable across merges. Example: cursor=1706212345:VIDEO123.

Shorts filtering (strict by default, configurable)

Omit entries if:

Link contains /shorts/

Or media:content duration present and < 90s

Or title matches obvious Shorts markers (optional)
Add a config flag INCLUDE_SHORTS=false to allow future toggling.

Caching & refresh strategy

Subscriptions: refreshed on demand or on user login if older than SUBS_REFRESH_MINUTES (e.g., 60m).

RSS: each channel_id refresh on cache miss or TTL expire; apply splay: base_ttl + rand(0, SPLAY_MAX).

oEmbed: optional for MVP; if used, cache 24h and fallback to canonical embed when rate-limited/timeouts occur.

Backoff: exponential backoff + jitter on HTTP 429/5xx; cap concurrency per request.

Security / privacy

Store refresh_token encrypted (AES-GCM) with a key from env (APP_KMS_KEY or generated secret).

Session cookie: HTTPOnly, SameSite=Lax, short-lived; server verifies against user row.

CORS: frontend origin only.

Minimal PII; no GA.

Config via Pydantic Settings; .env for local; env vars in prod.

Frontend UX (dark-first)

Layout: Left sidebar = channels (searchable), Main = feed grid/list toggle.

Controls: Grid/List toggle, per-page size selector (24/36), Channel filter (single/multi).

Cards: thumbnail → click to expand inline iframe, title, channel, published, “Open on YouTube”.

Empty states: No subs yet; loading; error with retry.

Accessibility: keyboard nav for pagination; reduced motion preference.

Dependency graph (DAG)

Config & Secrets

DB layer (SQLAlchemy models + Alembic)

Auth (Google OAuth) → needs (1)(2)

YouTube client (subscriptions) → needs (1)

RSS fetcher & parser → needs (1)

Cache layer (Redis client + TTL+splay util) → needs (1)

Feed aggregator (merge/sort/filter Shorts + pagination) → needs (2)(5)(6)

HTTP API (FastAPI routers) → needs (3)(4)(7)

SPA → needs (8) contract

Containerization & Reverse Proxy config → needs (8)(9)

CI/CD → builds (8)(9) and pushes image

Sub-projects (small, modular, reusable)

core-config

Deliverables: Pydantic settings, env loader, typed config object, logging config

Interface: get_settings()

db-layer

Deliverables: SQLAlchemy models, session factory, migrations (Alembic)

Interface: SessionLocal(), get_user_by_sub(), etc.

auth-google

Deliverables: OAuth routes, token exchange, refresh util, token storage (encrypt/decrypt)

Interface: require_user() dependency returning User

yt-client

Deliverables: Minimal wrapper for subscriptions.list with paging + tests

Interface: list_subscriptions(user) -> list[Channel]

rss-cache

Deliverables: Redis client, fetch_feed(channel_id) with TTL+splay; parser returning normalized FeedItem

Interface: get_channel_items(channel_id) -> list[FeedItem]

feed-aggregator

Deliverables: merge+sort across channels; Shorts filter; cursor pagination

Interface: get_feed(user_id, channel_ids?, limit, cursor) -> PageResult

api-routers

Deliverables: /api/* routes, response models, error handling

Interface: FastAPI APIRouter

frontend-spa

Deliverables: Vite app, auth flow, API client, pages/components, dark theme, grid/list toggle, channel sidebar, pagination

Interface: builds to /static

ops-container

Deliverables: Dockerfile/Containerfile (multi-stage), health checks, sample Podman run compose, reverse proxy snippet

ci-cd

Deliverables: GitHub Actions (lint/test/typecheck, build image, push GHCR), version tagging, SBOM (optional), basic SAST

Configuration (env)

APP_SECRET_KEY, TOKEN_ENC_KEY

GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI

YOUTUBE_API_KEY (only if needed; OAuth access token usually sufficient)

DATABASE_URL (sqlite:///… or postgres://…)

REDIS_URL

FEED_TTL_MIN=1800, FEED_TTL_SPLAY_MAX=780 (30m + up to 13m)

SUBS_REFRESH_MINUTES=60

INCLUDE_SHORTS=false

PAGE_SIZE_DEFAULT=24, PAGE_SIZE_MAX=60

FRONTEND_ORIGIN=https://…

Testing strategy

Unit: yt-client (quota-safe using vcrpy), rss parser, paginator, Shorts filter.

Integration: auth callback flow (mock Google), end-to-end API (sqlite+redis in Docker).

Frontend: component tests (Vitest), API mocks (msw), basic e2e (Playwright) for pagination + filtering.

CI/CD outline

Jobs: lint (ruff, mypy), test (pytest), build (Containerfile), push (GHCR).

Tags: :sha, :main, :vX.Y.Z.

Deployment: your Podman host pulls :main on push; systemd unit or a small script restarts the container if image digest changes.

---

# PRD 1 — `core-config`

**Purpose**
Typed configuration, env management, and logging. Single source of truth for settings used across services.

**Deliverables**

* `app/config.py` — `Settings` (Pydantic v2 `BaseSettings`)
* `app/logging.py` — structured logging (dev vs prod)
* `.env.example`
* Unit tests

**File scaffold**

```
app/
  __init__.py
  config.py
  logging.py
tests/
  test_config.py
.env.example
```

**Key requirements**

* Support: DB URL, Redis URL, Google OAuth creds, TTL+splay, paging, security keys, CORS origin.
* Defaults sane for local dev.
* Singleton access via `get_settings()`.

**Interfaces (sketch)**

```python
# app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, HttpUrl

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_prefix='YT_')

    app_secret_key: str
    token_enc_key: str

    google_client_id: str
    google_client_secret: str
    google_redirect_uri: HttpUrl

    database_url: str = "sqlite+aiosqlite:///./dev.db"
    redis_url: str = "redis://localhost:6379/0"

    feed_ttl_seconds: int = 1800
    feed_ttl_splay_max: int = 780
    subs_refresh_minutes: int = 60
    include_shorts: bool = False

    page_size_default: int = 24
    page_size_max: int = 60

    frontend_origin: str = "http://localhost:5173"
    env: str = Field(default="dev", pattern="^(dev|prod)$")

_settings: Settings | None = None
def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
```

```python
# app/logging.py
import logging, json, sys
from .config import get_settings

class JsonFormatter(logging.Formatter):
    def format(self, record):
        base = {
            "level": record.levelname,
            "msg": record.getMessage(),
            "logger": record.name,
        }
        if record.exc_info:
            base["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(base)

def setup_logging():
    settings = get_settings()
    handler = logging.StreamHandler(sys.stdout)
    if settings.env == "prod":
        handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
```

**Acceptance criteria**

* Loading without `.env` uses defaults; `.env` overrides work.
* Missing critical vars (`app_secret_key`, `token_enc_key`, Google creds) raise validation when endpoints require them.
* `setup_logging()` emits JSON in prod; pretty in dev.
* Tests cover defaulting and env override.

---

# PRD 2 — `db-layer`

**Purpose**
Persist users and their subscriptions. Provide async session factory and migrations.

**Deliverables**

* SQLAlchemy 2.x async models: `User`, `UserChannel`
* Alembic setup & initial migration
* CRUD utilities
* Unit tests

**File scaffold**

```
app/db/__init__.py
app/db/models.py
app/db/session.py
alembic.ini
alembic/env.py
alembic/versions/0001_init.py
tests/test_db_models.py
```

**Models (sketch)**

```python
# app/db/models.py
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, ForeignKey, DateTime, func
import uuid

class Base(DeclarativeBase): pass

def uid() -> str: return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    google_sub: Mapped[str] = mapped_column(String, unique=True, index=True)
    email: Mapped[str] = mapped_column(String, index=True)
    display_name: Mapped[str] = mapped_column(String)
    avatar_url: Mapped[str | None]
    refresh_token_enc: Mapped[bytes | None]
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    channels: Mapped[list["UserChannel"]] = relationship(back_populates="user", cascade="all, delete-orphan")

class UserChannel(Base):
    __tablename__ = "user_channels"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    channel_id: Mapped[str] = mapped_column(String, index=True)
    channel_title: Mapped[str]
    channel_custom_url: Mapped[str | None]
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    added_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="channels")
```

**Session & migrations**

```python
# app/db/session.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import get_settings

_engine = _sessionmaker = None

def get_engine():
    global _engine
    if _engine: return _engine
    url = get_settings().database_url
    # if sqlite sync URL, ensure async driver
    url = url.replace("sqlite:///", "sqlite+aiosqlite:///")
    _engine = create_async_engine(url, future=True)
    return _engine

def get_sessionmaker():
    global _sessionmaker
    if _sessionmaker: return _sessionmaker
    _sessionmaker = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _sessionmaker

async def get_session() -> AsyncSession:
    async with get_sessionmaker()() as s:
        yield s
```

**CRUD utilities (examples)**

```python
# app/db/crud.py
from sqlalchemy import select
from .models import User, UserChannel
from sqlalchemy.ext.asyncio import AsyncSession

async def get_user_by_sub(db: AsyncSession, sub: str) -> User | None:
    res = await db.execute(select(User).where(User.google_sub == sub))
    return res.scalar_one_or_none()

async def upsert_user_channel(db: AsyncSession, user_id: str, channel_id: str, title: str, custom_url: str | None):
    res = await db.execute(
        select(UserChannel).where(UserChannel.user_id == user_id, UserChannel.channel_id == channel_id)
    )
    row = res.scalar_one_or_none()
    if row:
        row.channel_title = title
        row.channel_custom_url = custom_url
        row.active = True
    else:
        row = UserChannel(user_id=user_id, channel_id=channel_id, channel_title=title, channel_custom_url=custom_url)
        db.add(row)
    await db.commit()
    return row
```

**Acceptance criteria**

* `alembic upgrade head` creates tables in SQLite; works for Postgres URL too.
* CRUD tests pass under pytest (sqlite+aiosqlite).
* Foreign key cascade verified (deleting user removes channels).

---

# PRD 3 — `auth-google`

**Purpose**
Google OAuth2 Authorization Code + PKCE, minimal scopes; secure session; token refresh & storage.

**Deliverables**

* FastAPI router: `/auth/login`, `/auth/callback`, `/auth/logout`
* Session cookie (HTTPOnly, SameSite=Lax)
* `require_user` dependency
* AES-GCM encryption for refresh token
* Tests (mock Google)

**File scaffold**

```
app/auth/__init__.py
app/auth/router.py
app/auth/security.py
tests/test_auth_flow.py
```

**Flow**

1. `GET /auth/login` → create state + PKCE, redirect to Google with scopes: `openid email profile` and `https://www.googleapis.com/auth/youtube.readonly`.
2. `GET /auth/callback` → verify state, exchange code → get tokens + `id_token` claims (`sub`, `email`, `name`, `picture`).
3. Encrypt `refresh_token` and store on `User` (create or update).
4. Issue signed session cookie (contains user id only).
5. `require_user` reads cookie, loads user, 401 if missing.

**Interfaces (sketch)**

```python
# app/auth/security.py
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os

def encrypt_refresh_token(key: bytes, plaintext: str) -> bytes:
    aes = AESGCM(key)
    nonce = os.urandom(12)
    return nonce + aes.encrypt(nonce, plaintext.encode(), None)

def decrypt_refresh_token(key: bytes, blob: bytes) -> str:
    aes = AESGCM(key)
    nonce, ct = blob[:12], blob[12:]
    return aes.decrypt(nonce, ct, None).decode()
```

```python
# app/auth/router.py (sketch)
from fastapi import APIRouter, Depends, Response, Request, HTTPException
from authlib.integrations.starlette_client import OAuth
from app.config import get_settings
from app.db.session import get_session
from app.db import crud
from jose import jwt, JWTError
import time

router = APIRouter(prefix="/auth", tags=["auth"])
SESSION_COOKIE = "yt_simple_sess"

def _oauth():
    s = get_settings()
    oauth = OAuth()
    oauth.register(
        name="google",
        client_id=s.google_client_id,
        client_secret=s.google_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile https://www.googleapis.com/auth/youtube.readonly"},
    )
    return oauth

@router.get("/login")
async def login(request: Request):
    return await _oauth().google.authorize_redirect(request, str(get_settings().google_redirect_uri))

@router.get("/callback")
async def callback(request: Request, response: Response, db=Depends(get_session)):
    token = await _oauth().google.authorize_access_token(request)
    userinfo = token["userinfo"]
    # upsert user, encrypt refresh_token if present
    # issue session cookie (signed JWT with user_id)
    # ...
    response.set_cookie(SESSION_COOKIE, "...", httponly=True, samesite="lax", secure=True)
    response.headers["Location"] = "/"
    return Response(status_code=302)

def require_user(...):
    # decode cookie → load user from DB → return user or 401
    ...
```

**Acceptance criteria**

* Full login roundtrip stores user and sets cookie.
* Logout clears cookie.
* Token encryption/decryption tested.
* 401 returned for protected endpoints without valid session.

---

# PRD 4 — `yt-client`

**Purpose**
Server-side retrieval of a user’s YouTube **subscriptions** via YouTube Data API v3 using their OAuth access token.

**Deliverables**

* Minimal YouTube client for `subscriptions.list`
* Pagination across pages
* Filter out “joined”/members-only where applicable
* Error handling & retries with jitter
* Unit tests (mocked)

**File scaffold**

```
app/youtube/__init__.py
app/youtube/client.py
tests/test_youtube_client.py
```

**Notes**

* Prefer using the **user’s access token** (not API key).
* Endpoint: `GET https://www.googleapis.com/youtube/v3/subscriptions?part=snippet&mine=true&maxResults=50&pageToken=...`
* From `snippet.resourceId.channelId`, `title` present; `customUrl` requires separate call (`channels.list?part=snippet&id=...`) — optional; we can skip or opportunistically fetch/cache.

**Interfaces (sketch)**

```python
# app/youtube/client.py
import httpx, asyncio, random, time
from typing import AsyncIterator

class YouTubeClient:
    BASE = "https://www.googleapis.com/youtube/v3"

    def __init__(self, access_token: str):
        self._headers = {"Authorization": f"Bearer {access_token}"}

    async def list_subscriptions(self) -> list[dict]:
        items: list[dict] = []
        token = None
        async with httpx.AsyncClient(timeout=15) as client:
            while True:
                params = {"part": "snippet", "mine": "true", "maxResults": 50}
                if token: params["pageToken"] = token
                r = await client.get(f"{self.BASE}/subscriptions", headers=self._headers, params=params)
                if r.status_code == 401:
                    raise PermissionError("Access token expired")
                r.raise_for_status()
                data = r.json()
                for it in data.get("items", []):
                    rid = it["snippet"]["resourceId"]
                    if rid.get("kind") == "youtube#channel":
                        items.append({
                            "channel_id": rid["channelId"],
                            "title": it["snippet"].get("title"),
                        })
                token = data.get("nextPageToken")
                if not token: break
                await asyncio.sleep(0.1 + random.random()*0.2)
        # de-dupe just in case
        seen = set()
        unique = []
        for it in items:
            if it["channel_id"] in seen: continue
            seen.add(it["channel_id"]); unique.append(it)
        return unique
```

**Acceptance criteria**

* Returns de-duplicated list of channel ids + titles.
* Properly follows pagination.
* On 401, the caller can trigger a token refresh.
* Unit tests cover multi-page and error paths.

---

# PRD 5 — `rss-cache`

**Purpose**
Fetch, parse, and cache each channel’s RSS feed using Redis. Normalise the XML into a consistent `FeedItem` structure, respecting TTL + splay.

**Deliverables**

* `app/rss/cache.py` — main fetch/cache module
* `app/rss/models.py` — typed Pydantic model for a feed item
* Unit tests (mocked HTTP + Redis)

**File scaffold**

```
app/rss/__init__.py
app/rss/cache.py
app/rss/models.py
tests/test_rss_cache.py
```

**Interfaces (sketch)**

```python
# app/rss/models.py
from pydantic import BaseModel, HttpUrl
from datetime import datetime

class FeedItem(BaseModel):
    video_id: str
    channel_id: str
    title: str
    link: HttpUrl
    published: datetime
```

```python
# app/rss/cache.py
import asyncio, random, httpx, xml.etree.ElementTree as ET, json
from redis.asyncio import Redis
from datetime import datetime, timezone
from app.config import get_settings
from .models import FeedItem

def _key(cid: str) -> str: return f"yt:feed:{cid}"

async def fetch_and_cache_feed(redis: Redis, channel_id: str) -> list[FeedItem]:
    s = get_settings()
    base_ttl, splay = s.feed_ttl_seconds, s.feed_ttl_splay_max
    ttl = base_ttl + random.randint(0, splay)
    key = _key(channel_id)
    if data := await redis.get(key):
        return [FeedItem(**x) for x in json.loads(data)]

    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(url)
        r.raise_for_status()
    xml = ET.fromstring(r.text)
    ns = {"yt": "http://www.youtube.com/xml/schemas/2015", "atom": "http://www.w3.org/2005/Atom"}
    items = []
    for entry in xml.findall("atom:entry", ns):
        vid = entry.find("yt:videoId", ns).text
        link = entry.find("atom:link", ns).attrib["href"]
        title = entry.find("atom:title", ns).text
        published = entry.find("atom:published", ns).text
        items.append(FeedItem(
            video_id=vid,
            channel_id=channel_id,
            title=title,
            link=link,
            published=datetime.fromisoformat(published.replace("Z","+00:00")),
        ))
    await redis.setex(key, ttl, json.dumps([i.model_dump() for i in items]))
    return items
```

**Acceptance criteria**

* Cache hit avoids refetch.
* TTL randomisation distributes expiry times.
* Invalid XML handled safely (returns empty list).
* Unit tests mock Redis and HTTPX.

---

# PRD 6 — `feed-aggregator`

**Purpose**
Merge cached feed items across user’s subscribed channels, filter out Shorts, sort, and paginate using cursor tokens.

**Deliverables**

* `app/feed/aggregator.py`
* Tests for merge logic, filtering, pagination.

**File scaffold**

```
app/feed/__init__.py
app/feed/aggregator.py
tests/test_feed_aggregator.py
```

**Interfaces (sketch)**

```python
# app/feed/aggregator.py
from app.rss.models import FeedItem
from typing import Sequence
from datetime import datetime
import base64, json

def is_short(item: FeedItem) -> bool:
    url = str(item.link)
    return "/shorts/" in url.lower()

def make_cursor(item: FeedItem) -> str:
    blob = json.dumps({"t": int(item.published.timestamp()), "v": item.video_id})
    return base64.urlsafe_b64encode(blob.encode()).decode()

def decode_cursor(cursor: str) -> tuple[int,str]:
    d = json.loads(base64.urlsafe_b64decode(cursor))
    return d["t"], d["v"]

def aggregate_feeds(feeds: Sequence[Sequence[FeedItem]], include_shorts=False, limit=24, cursor=None):
    items = [i for f in feeds for i in f]
    if not include_shorts:
        items = [i for i in items if not is_short(i)]
    items.sort(key=lambda i: i.published, reverse=True)
    if cursor:
        t,v = decode_cursor(cursor)
        items = [i for i in items if (i.published.timestamp(), i.video_id) < (t,v)]
    page = items[:limit]
    next_cursor = make_cursor(page[-1]) if len(items)>limit else None
    return {"items": page, "next_cursor": next_cursor}
```

**Acceptance criteria**

* Merged results globally sorted by published date desc.
* Shorts omitted unless flag set.
* Pagination deterministic across merges.
* Unit tests for edge cases (empty feeds, duplicates, cursor cutoff).

---

# PRD 7 — `api-routers`

**Purpose**
Expose backend API consumed by SPA. Handles auth, subscriptions refresh, feed listing, and health checks.

**Deliverables**

* `app/api/__init__.py`
* Routers: `me`, `subscriptions`, `feed`, `health`
* Unified error model
* OpenAPI tags

**File scaffold**

```
app/api/__init__.py
app/api/routes_me.py
app/api/routes_subscriptions.py
app/api/routes_feed.py
app/api/routes_health.py
tests/test_api_endpoints.py
```

**Interfaces (sketch)**

```python
# app/api/routes_feed.py
from fastapi import APIRouter, Depends, Query
from app.auth.router import require_user
from app.db.session import get_session
from app.db import crud
from app.rss.cache import fetch_and_cache_feed
from app.feed.aggregator import aggregate_feeds
from redis.asyncio import Redis

router = APIRouter(prefix="/api/feed", tags=["feed"])

@router.get("")
async def get_feed(
    limit: int = Query(24, le=60),
    cursor: str | None = None,
    channel_id: str | None = None,
    user=Depends(require_user),
    db=Depends(get_session),
    redis: Redis = Depends(...),
):
    channels = [channel_id] if channel_id else [c.channel_id for c in await crud.list_user_channels(db, user.id)]
    feeds = []
    for cid in channels:
        feeds.append(await fetch_and_cache_feed(redis, cid))
    result = aggregate_feeds(feeds, include_shorts=False, limit=limit, cursor=cursor)
    return {"items": [i.model_dump() for i in result["items"]], "next_cursor": result["next_cursor"]}
```

**Acceptance criteria**

* All routes documented via FastAPI `/docs`.
* `/api/feed` merges and paginates correctly.
* `/api/subscriptions` refresh works (mocked YouTube client).
* Auth required for protected routes.
* `/healthz` returns 200 JSON `{"ok":true}`.

---

# PRD 8 — `frontend-spa`

**Purpose**
Provide the web interface: dark, minimal, responsive, with channel list, grid/list toggle, and pagination.

**Deliverables**

* Vite + React + Tailwind SPA
* Pages: Login, Feed
* Components: `VideoCard`, `ChannelSidebar`, `Pagination`, `ViewToggle`
* API wrapper for backend calls
* Basic Vitest + Playwright tests

**Directory layout**

```
frontend/
  src/
    api/client.ts
    pages/Login.tsx
    pages/Feed.tsx
    components/
      VideoCard.tsx
      ChannelSidebar.tsx
      Pagination.tsx
      ViewToggle.tsx
  index.html
  vite.config.ts
  tailwind.config.js
tests/
  e2e/feed.spec.ts
```

**Component outline**

```tsx
// src/components/VideoCard.tsx
export default function VideoCard({ video }) {
  return (
    <div className="bg-neutral-900 rounded-2xl shadow p-2">
      <iframe
        className="w-full aspect-video rounded"
        src={`https://www.youtube.com/embed/${video.video_id}`}
        title={video.title}
        allowFullScreen
      />
      <div className="mt-2 text-sm">
        <h3 className="font-medium">{video.title}</h3>
        <p className="text-xs text-gray-400">{new Date(video.published).toLocaleString()}</p>
      </div>
    </div>
  );
}
```

**Feed page behaviour**

* On mount → `GET /api/feed` → show grid of `VideoCard`s.
* “Next” button appends or replaces page using `next_cursor`.
* Sidebar lists channels (`/api/subscriptions`); clicking filters feed.
* Dark theme default via Tailwind class `dark`.

**Acceptance criteria**

* Build with `npm run build` produces static files.
* Works locally against backend with CORS OK.
* Responsive at 320 px–1920 px widths.
* Playwright test logs in (mock cookie) → loads feed → paginates.

---

# PRD 9 — `ops-container`

**Purpose**
Provide reproducible containerized deployment for your Podman (or Docker-compatible) environment.
Bundle FastAPI backend + built frontend + static assets + healthcheck.

---

### **Deliverables**

* `Containerfile` / `Dockerfile` (multi-stage)
* Optional `compose.yaml` for dev
* `healthz` endpoint integration
* Example Podman run script + reverse-proxy snippet

---

### **File structure**

```
Containerfile
compose.yaml
ops/
  podman_run.sh
  nginx_snippet.conf
```

---

### **Multi-stage Containerfile**

```dockerfile
# Stage 1: build frontend
FROM node:20-bookworm AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# Stage 2: backend
FROM python:3.13-slim AS backend
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml requirements.txt* ./
RUN pip install --no-cache-dir -r requirements.txt

# copy source + built frontend
COPY app ./app
COPY --from=frontend /app/frontend/dist ./static

EXPOSE 8080
HEALTHCHECK CMD curl -f http://localhost:8080/healthz || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

---

### **Dev compose.yaml (optional)**

```yaml
version: "3.9"
services:
  api:
    build: .
    ports: ["8080:8080"]
    env_file: .env
    depends_on: [redis, db]
  redis:
    image: redis:7
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: yt
      POSTGRES_PASSWORD: yt
      POSTGRES_DB: yt_simple
```

---

### **Podman run script**

```bash
#!/usr/bin/env bash
podman pull ghcr.io/youruser/yt-simple:latest
podman stop yt-simple || true
podman rm yt-simple || true
podman run -d --name yt-simple \
  -p 8080:8080 \
  --env-file=/srv/yt-simple/.env \
  --restart=always \
  ghcr.io/youruser/yt-simple:latest
```

---

### **Nginx reverse-proxy snippet**

```nginx
location / {
    proxy_pass http://127.0.0.1:8080;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

---

### **Acceptance criteria**

* `podman build -t yt-simple .` → builds without error.
* Container starts, serves `/healthz` = 200 OK.
* Static files served at `/static` or root.
* Works behind HTTPS reverse proxy.
* Environment configurable via `.env` or Podman `--env-file`.

---

# PRD 10 — `ci-cd`

**Purpose**
Automate linting, tests, build, and image publishing via GitHub Actions → GHCR.
Ensure automatic Podman pull/restart via digest change.

---

### **Deliverables**

* `.github/workflows/build.yml`
* Optional deploy trigger script for Podman host

---

### **Workflow structure**

```yaml
name: Build & Publish

on:
  push:
    branches: [main]
  pull_request:

jobs:
  lint-test-build:
    runs-on: ubuntu-latest

    services:
      redis:
        image: redis:7
        ports: [6379:6379]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.13"

      - name: Install backend deps
        run: pip install -r requirements.txt

      - name: Lint & Typecheck
        run: |
          ruff check .
          mypy app

      - name: Run Tests
        run: pytest -q

      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: 20

      - name: Build frontend
        working-directory: frontend
        run: npm ci && npm run build

      - name: Build container
        run: |
          docker build -t ghcr.io/${{ github.repository }}:${{ github.sha }} .
          echo ${{ secrets.GITHUB_TOKEN }} | docker login ghcr.io -u ${{ github.actor }} --password-stdin
          docker push ghcr.io/${{ github.repository }}:${{ github.sha }}
          docker tag ghcr.io/${{ github.repository }}:${{ github.sha }} ghcr.io/${{ github.repository }}:latest
          docker push ghcr.io/${{ github.repository }}:latest
```

---

### **Optional: deploy watcher (on host)**

```bash
#!/usr/bin/env bash
IMG="ghcr.io/youruser/yt-simple:latest"
NEW_DIGEST=$(podman pull "$IMG" | awk '/Digest/ {print $2}')
CUR_DIGEST=$(podman inspect yt-simple --format '{{.ImageDigest}}' 2>/dev/null)
if [ "$NEW_DIGEST" != "$CUR_DIGEST" ]; then
  echo "New image detected, restarting..."
  ./podman_run.sh
fi
```

Schedule with cron or systemd timer.

---

### **Acceptance criteria**

* Workflow runs on each push to main or PR.
* Lint/type/test steps must pass for image build.
* GHCR image tagged with SHA + latest.
* Build < 10 min typical.
* Host pull script detects digest change and restarts container.

