# Architecture

> **For AI / new contributors:** Read this file first, then `README.md` and `backend/.env.example`.
> Entry points: `backend/app/main.py` (routes), `backend/app/services/` (sync logic),
> `backend/app/db/models/` (schema), `backend/alembic/versions/` (migrations).

## Project goal

Collect Clash Royale ranked (Path of Legend) data from the [official API](https://developer.clashroyale.com),
store it in PostgreSQL, and enable future analytics (deck usage, win rates, meta trends).

**Current scope:** backend-only. No frontend yet.

---

## Tech stack

| Layer | Choice |
|-------|--------|
| API | FastAPI |
| ORM | SQLAlchemy 2.x (async) |
| Database | PostgreSQL 16 |
| Migrations | Alembic |
| HTTP client | httpx |
| Scheduler | APScheduler (card sync only, daily UTC) |
| Tests | pytest + pytest-asyncio + aiosqlite (in-memory) |

Python 3.12+. All application code lives under `backend/`.

---

## Repository layout

```
backend/
  app/
    api/              # HTTP routers (cards, players, admin)
    services/         # Business logic + ClashRoyaleClient
      clash_api.py    # Official API client (retry on 429)
      card_sync.py
      leaderboard_sync.py
      battlelog_sync.py
      *_mapper.py     # API JSON → DB field mapping
    db/models/        # SQLAlchemy models
    schemas/          # Pydantic response models
    config.py         # Settings from .env
    main.py           # FastAPI app + lifespan
    scheduler.py      # Daily card sync cron
  alembic/versions/   # DB migrations (001 → 004)
  tests/
  docker-compose.yml  # Postgres + optional backend container
  .env.example
```

---

## Data flow

```
Official API                    PostgreSQL tables
─────────────────────────────────────────────────────────
GET /cards                  →   cards, card_changelog, sync_runs
GET /locations/global/
    pathoflegend/players    →   players, leaderboard_snapshots,
                                leaderboard_entries
GET /players/{tag}/battlelog →  battles, battle_participants,
                                battle_deck_cards
```

### Sync order (manual)

1. **Cards** — needed first (`battle_deck_cards.card_id` FK → `cards.id`)
2. **Leaderboard** — upserts tracked players from global PoL top N
3. **Battlelog** — BFS from leaderboard seeds: each player's last N ranked battles,
   then optional opponent expansion rounds (see below)

Admin endpoints require header `X-Admin-API-Key` matching `.env` `ADMIN_API_KEY`.
Clash Royale API key is read from `.env` automatically; never pass it in HTTP requests.

### Battlelog expansion (BFS)

Configurable via `BATTLES_PER_PLAYER` and `OPPONENT_EXPANSION_ROUNDS`:

```
Round 0: top-N leaderboard seeds (is_tracked + leaderboard_seeded)
         → fetch each seed's last N ranked battles
Round 1: opponents from round-0 battles → fetch their last N battles
Round 2: opponents from round-1 battles → fetch their last N battles
...
```

- Seeds come from leaderboard sync (`leaderboard_seeded=true`, `is_tracked=true`)
- Discovered opponents are upserted to `players` with `leaderboard_seeded=false`
  (not subject to leaderboard untrack logic; not re-synced on future runs unless
  encountered again via expansion)
- Set `OPPONENT_EXPANSION_ROUNDS=0` to only sync seed players' battles

---

## Database schema

### Phase 1 — Cards (`001_initial_schema`)

| Table | Purpose |
|-------|---------|
| `cards` | Current card metadata (ignores API fields `rarity`, `max_level`) |
| `card_changelog` | Field-level change history per sync batch |
| `sync_runs` | Card sync run log (success/failure, counts) |

### Phase 2 — Leaderboard & battles (`002`, `003`)

| Table | Purpose |
|-------|---------|
| `players` | Player identity + tracking state (PK: `tag`) |
| `leaderboard_snapshots` | One row per leaderboard sync (historical) |
| `leaderboard_entries` | Rank/elo per player per snapshot |
| `battles` | Unique ranked battles (dedupe key: `battle_key`) |
| `battle_participants` | Team/opponent per battle |
| `battle_deck_cards` | 8-card deck per player per battle |

### Migrations

| Revision | File | Change |
|----------|------|--------|
| `001` | `001_initial_schema.py` | cards, card_changelog, sync_runs |
| `002` | `002_phase2_pol_battles.py` | players, leaderboard, battles |
| `003` | `003_player_off_leaderboard_count.py` | `players.off_leaderboard_count` |
| `004` | `004_player_leaderboard_seeded.py` | `players.leaderboard_seeded` |

---

## Key design decisions

### Player tracking (soft untrack)

- `players.is_tracked` — whether player is in the leaderboard tracking pool
- `players.leaderboard_seeded` — `true` for top-N players from leaderboard sync;
  only these are subject to off-board untrack logic
- `players.off_leaderboard_count` — consecutive syncs absent from top N
- On leaderboard: count resets to `0`, `is_tracked = true`, `leaderboard_seeded = true`
- Off leaderboard (seeded only): count `+1`; when count ≥ `UNTRACK_AFTER_MISSES`, `is_tracked = false`
- Expansion-discovered opponents: `leaderboard_seeded=false`, `is_tracked=false`
- **Never delete** player rows or historical battles when someone drops off the board
- Set `UNTRACK_AFTER_MISSES=1` to restore immediate untrack behavior

### Battlelog per-player limit & expansion

- `BATTLES_PER_PLAYER` — max ranked battles to ingest per player per sync (default 25)
- `OPPONENT_EXPANSION_ROUNDS` — extra BFS rounds to follow opponents (default 2)

### Leaderboard snapshots

Each `sync/leaderboard` creates a **new** snapshot + entries. Old snapshots are kept for
historical rank analysis. `GET /api/leaderboard/latest` returns the most recent one only.

### Battle deduplication

`battle_key = {battle_time}_{sorted_tag_a}_{sorted_tag_b}`. Re-syncing the same battlelog
increments `battles_skipped`, not duplicate rows.

### Ranked battle filter

When `SYNC_RANKED_BATTLES_ONLY=true` (default), only battles with:
- `type == "pathOfLegend"`, or
- `gameMode.name` containing `"Ranked1v1"`

are stored. See `backend/app/services/battle_mapper.py`.

### Card sync safety

If the API returns zero cards but active cards exist in DB, sync **refuses** to proceed
(to avoid mass-deactivation from a bad API response).

---

## Official Clash Royale API

Base URL: `https://api.clashroyale.com/v1`  
Auth: `Authorization: Bearer {CLASH_ROYALE_API_KEY}`

### Verified endpoints (in use)

| Endpoint | Used by |
|----------|---------|
| `GET /cards` | `CardSyncService` |
| `GET /locations/global/pathoflegend/players?limit=&after=` | `LeaderboardSyncService` |
| `GET /players/{tag}/battlelog` | `BattlelogSyncService` |

Player tags must be URL-encoded (`#` → `%23`). Implemented in `leaderboard_mapper.encode_player_tag`.

### Known broken / unused endpoints

Do **not** use these (verified broken or wrong data):

- `GET /locations/global/seasons/{seasonId}/rankings/players`
- seasonsV2-related ranking endpoints

### API constraints

- **IP whitelist** required on developer.clashroyale.com for each API key
- VPN changes egress IP → 403 → backend returns 500 (uncaught `ClashRoyaleAPIError`)
- Rate limit 429 → client retries with backoff (`clash_api.py`)

---

## HTTP API surface

### Public read

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/cards` | List cards (filters: `card_type`, `has_evolution`, `elixir_cost`) |
| GET | `/api/cards/{id}` | Single card |
| GET | `/api/cards/{id}/changelog` | Card change history |
| GET | `/api/players` | Tracked players (`tracked_only=true` default) |
| GET | `/api/leaderboard/latest` | Latest PoL snapshot with entries |

### Admin sync (requires `X-Admin-API-Key`)

| Method | Path | Query params |
|--------|------|--------------|
| POST | `/api/admin/sync/cards` | — |
| POST | `/api/admin/sync/leaderboard` | `top_n` (optional) |
| POST | `/api/admin/sync/battlelog` | `batch_size`, `battles_per_player`, `opponent_expansion_rounds` |

Interactive docs: `http://localhost:8000/docs`

### Not yet implemented

- `GET` endpoints for battles / deck statistics
- Scheduled leaderboard + battlelog sync (scheduler only runs card sync today)
- Frontend

---

## Configuration

All settings in `backend/.env` (see `.env.example`). Loaded by `app/config.py` via pydantic-settings.

| Variable | Default | Meaning |
|----------|---------|---------|
| `DATABASE_URL` | `postgresql+asyncpg://...@localhost:5432/...` | DB connection |
| `CLASH_ROYALE_API_KEY` | — | Official API key |
| `ADMIN_API_KEY` | `change_me_admin_key` | Admin endpoint auth |
| `LEADERBOARD_TOP_N` | `100` | Default top N players to track |
| `LEADERBOARD_PAGE_LIMIT` | `100` | Page size for leaderboard API pagination |
| `UNTRACK_AFTER_MISSES` | `3` | Syncs off-board before untrack |
| `BATTLES_PER_PLAYER` | `25` | Ranked battles per player per sync |
| `OPPONENT_EXPANSION_ROUNDS` | `2` | BFS rounds to follow opponents |
| `SYNC_RANKED_BATTLES_ONLY` | `true` | Filter battlelog battle types |
| `BATTLELOG_BATCH_SIZE` | `10` | Reserved for future scheduled batches |
| `SYNC_ON_STARTUP` | `false` | Run card sync on app start |
| `CARD_SYNC_CRON_HOUR` | `3` | Daily card sync hour (UTC) |

**Docker note:** `docker-compose.yml` overrides `DATABASE_URL` to use host `db` inside containers.
Local dev (venv + uvicorn) must use `localhost`.

---

## Local development modes

### A. Full Docker

```bash
cd backend && docker compose up --build
```

Runs Postgres + backend; migrations run on container start.

### B. Hybrid (recommended for Windows / China)

```bash
cd backend
docker compose up -d db          # Postgres only
python -m venv .venv && pip install -r requirements.txt
cp .env.example .env             # edit API key
alembic upgrade head
uvicorn app.main:app --reload
```

Avoid running both Docker `backend` and local `uvicorn` on port 8000.

---

## Testing

```bash
cd backend
python -m pytest          # 17 tests
python -m pytest -v tests/test_phase2_sync.py   # leaderboard / battlelog logic
```

Tests use in-memory SQLite; production uses PostgreSQL.

---

## Phase roadmap

| Phase | Status | Contents |
|-------|--------|----------|
| 1 | Done | Card sync, changelog, daily cron, read API |
| 2 | Done | PoL leaderboard, battlelog ingest, player tracking, opponent expansion |
| 2b | Planned | Scheduled leaderboard/battlelog sync, battles read API, deck stats |
| 3 | Planned | Frontend dashboards |

---

## Common pitfalls (Windows / China)

| Problem | Cause | Fix |
|---------|-------|-----|
| `500 Internal Server Error` on sync | VPN / IP not whitelisted | Disable VPN or add IP on developer.clashroyale.com |
| `401 Invalid admin API key` | Header ≠ `.env` `ADMIN_API_KEY` | Match values; restart uvicorn after `.env` change |
| `alembic` not found | venv not activated | `.\.venv\Scripts\Activate.ps1` or `python -m alembic` |
| `git pull` / `curl github.com` timeout | CLI not using proxy | Set git proxy or enable VPN TUN/global mode |
| PowerShell `curl` fails | Alias to `Invoke-WebRequest` | Use `curl.exe` with double quotes |

---

## Branches & PRs

| Branch | PR | Contents |
|--------|-----|----------|
| `cursor/card-sync-backend-0e90` | #1 | Phase 1 |
| `cursor/pol-leaderboard-phase2-0e90` | #2 | Phase 2 + off_leaderboard_count |

---

## Conventions for new code

- Put sync logic in `app/services/`, not in route handlers
- API JSON mapping in dedicated `*_mapper.py` files
- Schema changes require Alembic migration in `alembic/versions/`
- Add tests under `backend/tests/`
- Match existing async SQLAlchemy patterns (`AsyncSession`, `select()`)
- Keep diffs minimal; do not over-engineer
