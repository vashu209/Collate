"""In-memory async background task runner for non-blocking operations."""

import threading
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from organizer.config.loader import load_rules_config
from organizer.propose_service import run_propose
from organizer.scanning.scanner import scan_directory
from organizer.storage.repository import Repository
from organizer_api.config import settings


class Task:
    def __init__(self, task_id: str, task_type: str) -> None:
        self.task_id = task_id
        self.task_type = task_type
        self.status = "pending"  # "pending", "running", "completed", "failed"
        self.progress = 0
        self.message: Optional[str] = None
        self.result: Optional[Dict[str, Any]] = None
        self.error: Optional[str] = None


class TaskManager:
    def __init__(self) -> None:
        self._tasks: Dict[str, Task] = {}
        self._lock = threading.Lock()

    def get_task(self, task_id: str) -> Optional[Task]:
        with self._lock:
            return self._tasks.get(task_id)

    def start_scan(self, path: str, recursive: bool = True, repo: Optional[Repository] = None) -> Task:
        task_id = str(uuid.uuid4())
        task = Task(task_id, "scan")
        with self._lock:
            self._tasks[task_id] = task

        def _run_scan() -> None:
            task.status = "running"
            task.message = f"Starting scan on {path}..."
            active_repo = repo or Repository(settings.db_path)
            target = Path(path).expanduser().resolve()
            if not target.exists() or not target.is_dir():
                task.status = "failed"
                task.error = f"Target directory does not exist or is not a directory: {target}"
                return

            try:
                active_repo.record_scan_root(str(target))
                count = 0
                for record in scan_directory(target, recursive=recursive):
                    active_repo.upsert_file(record)
                    count += 1
                    task.progress = count
                    if count % 10 == 0:
                        task.message = f"Cataloged {count} files..."

                task.status = "completed"
                task.message = f"Completed scan: {count} files cataloged."
                task.result = {"files_scanned": count, "path": str(target)}
            except Exception as e:
                task.status = "failed"
                task.error = str(e)

        thread = threading.Thread(target=_run_scan, daemon=True)
        thread.start()
        return task

    def start_propose(
        self,
        model: str = "rules",
        min_confidence: Optional[float] = None,
        organize_root: Optional[str] = None,
        no_fallback: bool = False,
        repo: Optional[Repository] = None,
    ) -> Task:
        task_id = str(uuid.uuid4())
        task = Task(task_id, "propose")
        with self._lock:
            self._tasks[task_id] = task

        def _run_propose() -> None:
            task.status = "running"
            task.message = f"Running propose with model '{model}'..."
            active_repo = repo or Repository(settings.db_path)

            try:
                rules_cfg = load_rules_config(settings.rules_path)
                if min_confidence is not None:
                    rules_cfg.defaults.min_confidence_for_proposal = min_confidence

                res = run_propose(
                    active_repo,
                    rules_cfg,
                    model=model,
                    organize_root=organize_root,
                    no_fallback=no_fallback,
                )
                task.status = "completed"
                task.message = f"Propose finished: {res.proposals_saved} proposals generated."
                task.result = {
                    "backend": res.backend,
                    "proposals_saved": res.proposals_saved,
                    "category_counts": dict(res.category_counts),
                    "bootstrapped_examples": res.bootstrapped_examples,
                    "fell_back": res.fell_back,
                    "fallback_reason": res.fallback_reason,
                }
            except Exception as e:
                task.status = "failed"
                task.error = str(e)

        thread = threading.Thread(target=_run_propose, daemon=True)
        thread.start()
        return task


task_manager = TaskManager()
