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
