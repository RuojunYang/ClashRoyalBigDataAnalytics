import json
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import OperationRun

sync_logger = logging.getLogger("app.sync")


class OperationRunTracker:
    def __init__(
        self,
        session: AsyncSession,
        operation: str,
        params: dict[str, Any],
        *,
        progress_every_n: int | None = None,
        progress_interval_seconds: float | None = None,
    ) -> None:
        self.session = session
        self.operation = operation
        self.params = params
        self.progress_every_n = progress_every_n or settings.operation_progress_every_n
        self.progress_interval_seconds = progress_interval_seconds or settings.operation_progress_interval_seconds
        self.run: OperationRun | None = None
        self._run_id: int | None = None
        self._started_at: datetime | None = None
        self._last_progress_at: datetime | None = None
        self._last_progress_n: int = 0

    async def start(self) -> OperationRun:
        self._started_at = datetime.now(UTC)
        self.run = OperationRun(
            operation=self.operation,
            status="running",
            params=self.params,
            progress={"last_updated_at": self._started_at.isoformat()},
        )
        self.session.add(self.run)
        await self.session.flush()
        self._run_id = self.run.id
        sync_logger.info(
            "[START] operation=%s run_id=%s params=%s",
            self.operation,
            self._run_id,
            json.dumps(self.params, ensure_ascii=False, default=str),
        )
        return self.run

    @property
    def run_id(self) -> int:
        if self._run_id is None:
            raise RuntimeError("OperationRunTracker.start() was not called")
        return self._run_id

    def _should_write_progress(self, progress: dict[str, Any], *, force: bool) -> bool:
        if force:
            return True
        now = datetime.now(UTC)
        counter = progress.get("players_processed") or progress.get("items_processed") or 0
        if isinstance(counter, int) and counter > 0 and counter % self.progress_every_n == 0:
            if counter != self._last_progress_n:
                return True
        if self._last_progress_at is None:
            return True
        elapsed = (now - self._last_progress_at).total_seconds()
        return elapsed >= self.progress_interval_seconds

    async def maybe_update_progress(
        self,
        progress: dict[str, Any],
        *,
        force: bool = False,
        commit: bool = False,
    ) -> bool:
        if self._run_id is None:
            return False
        if not self._should_write_progress(progress, force=force):
            return False

        now = datetime.now(UTC)
        progress = {**progress, "last_updated_at": now.isoformat()}
        run = await self.session.get(OperationRun, self._run_id)
        if run is None:
            return False
        run.progress = progress
        self.run = run
        self._last_progress_at = now
        self._last_progress_n = progress.get("players_processed") or progress.get("items_processed") or 0

        sync_logger.info(
            "[PROGRESS] operation=%s run_id=%s %s",
            self.operation,
            self._run_id,
            json.dumps(progress, ensure_ascii=False, default=str),
        )

        if commit:
            await self.session.commit()
            self.run = await self.session.get(OperationRun, self._run_id)

        return True

    async def fail(self, error_message: str, *, commit: bool = True) -> None:
        if self._run_id is None or self._started_at is None:
            return
        run_id = self._run_id
        finished_at = datetime.now(UTC)
        run = await self.session.get(OperationRun, run_id)
        if run is None:
            sync_logger.error(
                "[END] operation=%s run_id=%s status=failed (run row missing) error=%s",
                self.operation,
                run_id,
                error_message,
            )
            return
        run.status = "failed"
        run.finished_at = finished_at
        run.error_message = error_message
        duration_s = (finished_at - self._started_at).total_seconds()
        sync_logger.info(
            "[END] operation=%s run_id=%s status=failed duration_s=%.1f error=%s",
            self.operation,
            run_id,
            duration_s,
            error_message,
        )
        if commit:
            await self.session.commit()

    async def finish(
        self,
        status: str,
        result: dict[str, Any] | None = None,
        *,
        error_message: str | None = None,
        commit: bool = True,
    ) -> None:
        if self._run_id is None or self._started_at is None:
            return

        run_id = self._run_id
        run = await self.session.get(OperationRun, run_id)
        if run is None:
            return

        finished_at = datetime.now(UTC)
        run.status = status
        run.finished_at = finished_at
        run.result = result
        run.error_message = error_message
        self.run = run

        duration_s = (finished_at - self._started_at).total_seconds()
        sync_logger.info(
            "[END] operation=%s run_id=%s status=%s duration_s=%.1f result=%s%s",
            self.operation,
            run_id,
            status,
            duration_s,
            json.dumps(result or {}, ensure_ascii=False, default=str),
            f" error={error_message}" if error_message else "",
        )

        if commit:
            await self.session.commit()
