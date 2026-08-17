import logging
from datetime import datetime, timezone
from logging import LogRecord
from pathlib import Path


class DailyFileHandler(logging.Handler):
    """Append logs to logs/YYYYMMDDlog.txt (UTC day boundary)."""

    def __init__(self, log_dir: str | Path) -> None:
        super().__init__()
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._current_day: str | None = None
        self._stream = None

    def _path_for_day(self, day: str) -> Path:
        return self.log_dir / f"{day}log.txt"

    def _ensure_stream(self) -> None:
        day = datetime.now(timezone.utc).strftime("%Y%m%d")
        if day == self._current_day and self._stream is not None:
            return
        if self._stream is not None:
            self._stream.close()
        self._current_day = day
        self._stream = open(self._path_for_day(day), "a", encoding="utf-8")

    def emit(self, record: LogRecord) -> None:
        try:
            self._ensure_stream()
            assert self._stream is not None
            msg = self.format(record)
            self._stream.write(msg + "\n")
            self._stream.flush()
        except Exception:
            self.handleError(record)

    def close(self) -> None:
        if self._stream is not None:
            self._stream.close()
            self._stream = None
        super().close()


def setup_sync_file_logging(log_dir: str | Path) -> logging.Logger:
    sync_logger = logging.getLogger("app.sync")
    if any(isinstance(h, DailyFileHandler) for h in sync_logger.handlers):
        return sync_logger

    handler = DailyFileHandler(log_dir)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s UTC [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logging.Formatter.converter = lambda *args: datetime.now(timezone.utc).timetuple()

    sync_logger.addHandler(handler)
    sync_logger.setLevel(logging.INFO)
    sync_logger.propagate = True
    return sync_logger
