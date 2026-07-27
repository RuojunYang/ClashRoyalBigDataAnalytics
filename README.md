# ClashRoyalBigDataAnalytics

皇室战争大数据分析项目 — 从 [Clash Royale 官方 API](https://developer.clashroyale.com) 同步卡牌、全球 Path of Legend 排行榜与对战数据到 PostgreSQL，用于后续 deck / 胜率等分析。

**详细架构、数据模型、设计决策见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。**

---

## 功能概览

| Phase | 状态 | 内容 |
|-------|------|------|
| 1 | ✅ | 卡牌元数据同步、变更历史、定时同步 |
| 2 | ✅ | 全球 PoL 排行榜、玩家跟踪、battlelog 入库 |
| 2b | ⏳ | 定时 sync、battles 查询 API、deck 统计 |
| 3 | ⏳ | 前端 |

---

## 快速启动

### Docker 一键启动

```bash
cd backend
cp .env.example .env
# 编辑 .env，填入 CLASH_ROYALE_API_KEY

docker compose up --build
```

- API: http://localhost:8000
- 文档: http://localhost:8000/docs
- 健康检查: `GET /health`

### 本地开发（推荐：Docker 只跑数据库）

**Linux / macOS:**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

docker compose up -d db
cp .env.example .env
# 编辑 .env

alembic upgrade head
uvicorn app.main:app --reload
```

**Windows PowerShell:**

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

docker compose up -d db
copy .env.example .env
# 编辑 .env

python -m alembic upgrade head
uvicorn app.main:app --reload
```

> 本地 `.env` 中 `DATABASE_URL` 应使用 `localhost`，不要用 `db`（`db` 仅在 Docker 容器内有效）。

---

## 同步数据

Admin 接口需要请求头 `X-Admin-API-Key`（值与 `.env` 中 `ADMIN_API_KEY` 一致，默认 `change_me_admin_key`）。

**Linux / macOS (curl):**

```bash
# 1. 同步卡牌
curl -X POST http://localhost:8000/api/admin/sync/cards \
  -H "X-Admin-API-Key: change_me_admin_key"

# 2. 同步全球 PoL 排行榜（默认 top 100，可用 top_n 覆盖）
curl -X POST "http://localhost:8000/api/admin/sync/leaderboard?top_n=100" \
  -H "X-Admin-API-Key: change_me_admin_key"

# 3. 同步 tracked 玩家的 battlelog
curl -X POST http://localhost:8000/api/admin/sync/battlelog \
  -H "X-Admin-API-Key: change_me_admin_key"
```

**Windows PowerShell（请用 `curl.exe`）:**

```powershell
curl.exe -X POST "http://localhost:8000/api/admin/sync/cards" -H "X-Admin-API-Key: change_me_admin_key"
curl.exe -X POST "http://localhost:8000/api/admin/sync/leaderboard?top_n=10" -H "X-Admin-API-Key: change_me_admin_key"
curl.exe -X POST "http://localhost:8000/api/admin/sync/battlelog" -H "X-Admin-API-Key: change_me_admin_key"
curl.exe -X POST "http://localhost:8000/api/admin/sync/battlelog?battles_per_player=10&opponent_expansion_rounds=0" -H "X-Admin-API-Key: change_me_admin_key"
```

---

## 查询数据

| 接口 | 说明 |
|------|------|
| `GET /api/cards` | 卡牌列表 |
| `GET /api/cards/{id}` | 单张卡牌 |
| `GET /api/players` | 当前 tracked 玩家 |
| `GET /api/players?tracked_only=false` | 含掉榜玩家 |
| `GET /api/leaderboard/latest` | 最新排行榜快照 |

对战数据已入库（`battles` 等表），**查询 API 尚未实现**，可暂时用 SQL 查看。

---

## 环境变量

完整列表见 `backend/.env.example`。常用项：

| 变量 | 说明 | 默认 |
|------|------|------|
| `DATABASE_URL` | PostgreSQL 连接串 | `localhost:5432` |
| `CLASH_ROYALE_API_KEY` | 官方 API Key | — |
| `ADMIN_API_KEY` | Admin 同步鉴权 | `change_me_admin_key` |
| `LEADERBOARD_TOP_N` | 跟踪 top N 玩家 | `100` |
| `LEADERBOARD_PAGE_LIMIT` | 排行榜 API 每页条数 | `100` |
| `UNTRACK_AFTER_MISSES` | 连续几次不在榜后 untrack | `3` |
| `BATTLES_PER_PLAYER` | 每人每次 sync 入库最近几场 ranked 对局 | `25` |
| `OPPONENT_EXPANSION_ROUNDS` | 对手扩展 BFS 轮数（0=仅种子玩家） | `2` |
| `SYNC_RANKED_BATTLES_ONLY` | 只入库 PoL / Ranked1v1 | `true` |
| `SYNC_ON_STARTUP` | 启动时同步卡牌 | `false` |
| `CARD_SYNC_CRON_HOUR` | 每日卡牌同步（UTC 小时） | `3` |

---

## 运行测试

```bash
cd backend
pip install -r requirements.txt
python -m pytest
```

---

## 常见问题

| 现象 | 处理 |
|------|------|
| `500 Internal Server Error` 同步失败 | 检查 API Key、IP 白名单；**VPN 会导致 403** |
| `401 Invalid admin API key` | 请求头与 `.env` `ADMIN_API_KEY` 不一致 |
| `alembic` 命令找不到 | 激活 venv，或用 `python -m alembic upgrade head` |
| `git pull` 连不上 GitHub | 开 VPN 或给 git 配置代理 |
| Docker Hub 拉镜像失败 | 用混合模式：仅 `docker compose up -d db` + 本地 Python |

更多细节（数据模型、API 清单、设计决策）→ **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**

---

## 项目结构

```
backend/
  app/api/          # HTTP 路由
  app/services/     # 同步逻辑 + 官方 API 客户端
  app/db/models/    # 数据库模型
  alembic/          # 数据库迁移
  tests/
docs/
  ARCHITECTURE.md   # 架构与设计文档（AI / 新人请先读）
```
