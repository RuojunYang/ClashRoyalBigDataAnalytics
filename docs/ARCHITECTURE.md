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
  alembic/versions/   # DB migrations (001 → 006)
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
| `005` | `005_card_gameplay_profiles.py` | `card_gameplay_profiles` (initial; included roles, superseded by `006`) |
| `006` | `006_simplify_profiles_add_played_variant.py` | Drop `card_threat_roles` / `role_code`; add `battle_deck_cards.played_variant` |

### Phase 2b — Card core profiles & battle variants (`005`, `006`)

| Table / column | Purpose |
|----------------|---------|
| `card_gameplay_profiles` | Per-card, per-variant curated metadata (`is_core`, `related_card_id`, `notes`) |
| `battle_deck_cards.played_variant` | Which form was played in that deck slot: `base` / `hero` / `evo_1` / `evo_2` |

**`is_core` is independent of `cards.card_type`.** Any type can be core — e.g. Goblin Barrel
(`spell`) is core; Ice Golem (`troop`) is not core.

- L1 `cards.card_type` — official API fact: `troop` / `building` / `spell` (unchanged)
- L2 `card_gameplay_profiles.variant` — `base` / `hero` / `evo_1` / … per-form core flag
- L3 `battle_deck_cards.played_variant` — inferred at ingest from deck slot + card facts

**Variant inference** (battlelog sync, `app/services/card_variant.py`):

- Slots in `DECK_EVO_SLOTS` (default `0,2`) + `cards.has_evolution` → `evo_N`
- Slot `DECK_HERO_SLOT` (default `1`) + `cards.has_hero` → `hero`
- Otherwise → `base`
- Optional API `evolutionLevel` on deck card objects overrides evo level when present

Seed data: [`backend/app/data/card_profile_seed.py`](backend/app/data/card_profile_seed.py)

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

### Card core profiles (curated)

- Do **not** add `is_core` to `cards` — use `card_gameplay_profiles` instead
- `is_core` answers: "In this variant, is this card a deck win condition / primary threat?"
- **Not limited to troops** — spells (Goblin Barrel), buildings (Tombstone hero form), etc.
- Maintained manually in seed data; not inferred from API sync
- Role taxonomy (`card_threat_roles`) was removed — too granular for manual curation at this stage

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
| GET | `/api/cards` | List cards (filters: `card_type`, `has_evolution`, `elixir_cost`, `is_core`, `variant`) |
| GET | `/api/cards/{id}` | Single card |
| GET | `/api/cards/{id}/profiles` | Card + all gameplay profiles (`is_core` per variant) |
| GET | `/api/cards/{id}/changelog` | Card change history |
| GET | `/api/players` | Tracked players (`tracked_only=true` default) |
| GET | `/api/leaderboard/latest` | Latest PoL snapshot with entries |
| GET | `/api/data/tables` | List exportable DB tables (for pandas) |
| GET | `/api/data/{table}` | Export table rows as JSON array or CSV |

### Admin sync (requires `X-Admin-API-Key`)

| Method | Path | Query params |
|--------|------|--------------|
| POST | `/api/admin/sync/cards` | — |
| POST | `/api/admin/sync/leaderboard` | `top_n` (optional) |
| POST | `/api/admin/sync/battlelog` | `batch_size`, `battles_per_player`, `opponent_expansion_rounds` |

Interactive docs: `http://localhost:8000/docs`

### Pandas export (`/api/data`)

Read any DB table directly into a DataFrame:

```python
import pandas as pd

BASE = "http://localhost:8000"

# JSON array (default) — one row per record
cards = pd.read_json(f"{BASE}/api/data/cards")
battles = pd.read_json(f"{BASE}/api/data/battles", params={"limit": 50000})

# CSV
players = pd.read_csv(f"{BASE}/api/data/players?format=csv")

# Filters + pagination metadata
deck = pd.read_json(f"{BASE}/api/data/battle_deck_cards", params={"card_id": 26000000, "meta": True})
df = pd.DataFrame(deck["rows"])
```

Query params:

| Param | Default | Meaning |
|-------|---------|---------|
| `format` | `json` | `json` or `csv` |
| `limit` | `10000` | Max rows (up to `100000`) |
| `offset` | `0` | Skip rows for pagination |
| `meta` | `false` | When `format=json`, wrap with `{table, count, rows, ...}` |
| `include_total` | `false` | Include `total_count` (extra COUNT query) |

Supported filters vary by table — see `GET /api/data/tables` for column and filter lists.
Common examples: `snapshot_id` on `leaderboard_entries`, `player_tag` / `card_id` on `battle_deck_cards`.


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
| `DECK_EVO_SLOTS` | `0,2` | Deck slots that map to evolution form when `has_evolution` |
| `DECK_HERO_SLOT` | `1` | Deck slot that maps to hero form when `has_hero` |
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
python -m pytest          # 33 tests
python -m pytest -v tests/test_phase2_sync.py   # leaderboard / battlelog logic
python -m pytest -v tests/test_card_variant.py  # played_variant slot inference
```

Tests use in-memory SQLite; production uses PostgreSQL.

---

## Phase roadmap

| Phase | Status | Contents |
|-------|--------|----------|
| 1 | Done | Card sync, changelog, daily cron, read API |
| 2 | Done | PoL leaderboard, battlelog ingest, player tracking, opponent expansion |
| 2b | In progress | Card core profiles, `played_variant` on deck cards; deck stats API planned |
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
| `cursor/card-core-profiles-0e90` | #4 | Card core profiles + played_variant inference |

---

## Conventions for new code

- Put sync logic in `app/services/`, not in route handlers
- API JSON mapping in dedicated `*_mapper.py` files
- Schema changes require Alembic migration in `alembic/versions/`
- Add tests under `backend/tests/`
- Match existing async SQLAlchemy patterns (`AsyncSession`, `select()`)
- Keep diffs minimal; do not over-engineer
