import logging
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import Base, OperationRun
from app.logging.daily_file import DailyFileHandler, setup_sync_file_logging
from app.services.operation_run_tracker import OperationRunTracker


@pytest.fixture
async def op_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_operation_run_tracker_lifecycle(op_session, tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.operation_run_tracker.settings.operation_progress_every_n", 1)
    monkeypatch.setattr("app.services.operation_run_tracker.settings.operation_progress_interval_seconds", 0)

    log_dir = tmp_path / "logs"
    sync_logger = logging.getLogger("app.sync")
    sync_logger.handlers.clear()
    handler = DailyFileHandler(log_dir)
    handler.setFormatter(logging.Formatter("%(message)s"))
    sync_logger.addHandler(handler)
    sync_logger.setLevel(logging.INFO)

    tracker = OperationRunTracker(
        op_session,
        "battlelog",
        {"battles_per_player": 25, "opponent_expansion_rounds": 1},
    )
    await tracker.start()
    await op_session.commit()

    await tracker.maybe_update_progress({"players_processed": 1, "battles_created": 5}, commit=True)
    await tracker.finish("success", {"battles_created": 10}, commit=True)

    run = await op_session.get(OperationRun, tracker.run_id)
    assert run is not None
    assert run.status == "success"
    assert run.params["battles_per_player"] == 25
    assert run.result["battles_created"] == 10
    assert run.progress is not None
    assert run.finished_at is not None

    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    log_file = log_dir / f"{day}log.txt"
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "[START]" in content
    assert "[PROGRESS]" in content
    assert "[END]" in content


@pytest.mark.asyncio
async def test_operation_run_tracker_fail_after_rollback(op_session):
    tracker = OperationRunTracker(op_session, "cards", {})
    await tracker.start()
    await op_session.commit()

    await op_session.rollback()
    await tracker.fail("boom", commit=True)

    run = await op_session.get(OperationRun, tracker.run_id)
    assert run is not None
    assert run.status == "failed"
    assert run.error_message == "boom"
