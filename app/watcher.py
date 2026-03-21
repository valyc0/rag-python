from __future__ import annotations

import asyncio
import threading
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from app.logging_config import get_logger
from app.service import RagService

logger = get_logger(__name__)


class _DocumentEventHandler(FileSystemEventHandler):
    def __init__(self, loop: asyncio.AbstractEventLoop, service: RagService, debounce_seconds: float) -> None:
        self.loop = loop
        self.service = service
        self.debounce_seconds = debounce_seconds
        self._timer: threading.Timer | None = None

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        if self._timer:
            self._timer.cancel()
        self._timer = threading.Timer(self.debounce_seconds, self._trigger_rescan)
        self._timer.start()

    def _trigger_rescan(self) -> None:
        logger.info("Filesystem change detected, rescanning documents")
        asyncio.run_coroutine_threadsafe(self.service.rescan_documents(), self.loop)


class DocumentWatcher:
    def __init__(self, service: RagService, documents_path: str, debounce_seconds: float) -> None:
        self.service = service
        self.documents_path = Path(documents_path)
        self.debounce_seconds = debounce_seconds
        self.observer = Observer()

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        self.documents_path.mkdir(parents=True, exist_ok=True)
        handler = _DocumentEventHandler(loop, self.service, self.debounce_seconds)
        self.observer.schedule(handler, str(self.documents_path), recursive=True)
        self.observer.start()
        logger.info("Started filesystem watcher on %s", self.documents_path)

    def stop(self) -> None:
        self.observer.stop()
        self.observer.join(timeout=5)
