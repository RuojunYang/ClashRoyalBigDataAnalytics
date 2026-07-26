# ClashRoyalBigDataAnalytics

皇室战争大数据分析项目。

## Phase 1: 卡牌元数据后端

从 [Clash Royale 官方 API](https://developer.clashroyale.com) 同步卡牌数据到 PostgreSQL，支持变更历史与定时同步。

### 快速启动

```bash
cd backend
cp .env.example .env
# 编辑 .env，填入 CLASH_ROYALE_API_KEY

docker compose up --build
```

服务启动后：

- API: http://localhost:8000
- 健康检查: `GET /health`
- 卡牌列表: `GET /api/cards`
- 手动同步: `POST /api/admin/sync/cards`（请求头 `X-Admin-API-Key`）

### 本地开发（不用 Docker 跑后端）

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

docker compose up -d db
cp .env.example .env

alembic upgrade head
uvicorn app.main:app --reload
```

### 运行测试

```bash
cd backend
pip install -r requirements.txt
pytest
```

### 环境变量

| 变量 | 说明 |
|------|------|
| `DATABASE_URL` | PostgreSQL 连接串 |
| `CLASH_ROYALE_API_KEY` | 官方 API Key |
| `ADMIN_API_KEY` | Admin 同步端点鉴权 |
| `SYNC_ON_STARTUP` | 启动时是否立即同步 |
| `CARD_SYNC_CRON_HOUR` | 每日自动同步（UTC 小时，Docker/服务器内按 UTC 执行） |

## Phase 2: 全球 PoL 排行榜 + 对战同步

从 `GET /locations/global/pathoflegend/players` 抓取 top N 玩家 tag，再拉取 battlelog 入库。

### 同步流程

```bash
# 1. 同步卡牌（若尚未执行）
curl -X POST http://localhost:8000/api/admin/sync/cards -H "X-Admin-API-Key: change_me_admin_key"

# 2. 同步全球 PoL 排行榜（默认 top 100，可改 top_n）
curl -X POST "http://localhost:8000/api/admin/sync/leaderboard?top_n=100" -H "X-Admin-API-Key: change_me_admin_key"

# 3. 同步 tracked 玩家 battlelog（默认全部；batch_size 可限制单次处理人数）
curl -X POST http://localhost:8000/api/admin/sync/battlelog -H "X-Admin-API-Key: change_me_admin_key"
```

### 查询端点

- `GET /api/players` — tracked 玩家列表
- `GET /api/players?tracked_only=false` — 含掉榜玩家
- `GET /api/leaderboard/latest` — 最新排行榜快照

### Phase 2 环境变量

| 变量 | 说明 |
|------|------|
| `LEADERBOARD_TOP_N` | 默认跟踪 top N 玩家（默认 100） |
| `LEADERBOARD_PAGE_LIMIT` | 每次 API 请求的 `limit` 参数（默认 100） |
| `UNTRACK_AFTER_MISSES` | 连续多少次 sync 不在榜后停止跟踪（默认 3；设为 1 等同立即 untrack） |
| `SYNC_RANKED_BATTLES_ONLY` | 只入库 pathOfLegend / Ranked1v1 对局 |
| `BATTLELOG_BATCH_SIZE` | 预留：定时任务批次大小 |
