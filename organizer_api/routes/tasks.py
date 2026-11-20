"""Async scan, propose, and system utility task endpoints."""

import subprocess
import sys
import os
import tkinter as tk
from tkinter import filedialog
import threading
from concurrent.futures import Future
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException

from organizer.storage.repository import Repository
from organizer_api.dependencies import get_repo
from organizer_api.models import ProposeRequest, ScanRequest, TaskStatusResponse
from organizer_api.task_manager import task_manager

router = APIRouter(tags=["tasks"])

class BrowseResponse(BaseModel):
    path: str | None = None


@router.post("/scan", response_model=TaskStatusResponse)
def trigger_scan(
    body: ScanRequest,
    repo: Repository = Depends(get_repo),
) -> TaskStatusResponse:
    """Trigger background directory scan without blocking."""
    task = task_manager.start_scan(path=body.path, recursive=body.recursive, repo=repo)
    return TaskStatusResponse(
        task_id=task.task_id,
        task_type=task.task_type,
        status=task.status,
        progress=task.progress,
        message=task.message,
    )


@router.post("/propose", response_model=TaskStatusResponse)
def trigger_propose(
    body: ProposeRequest,
    repo: Repository = Depends(get_repo),
) -> TaskStatusResponse:
    """Trigger background proposal generation without blocking."""
    task = task_manager.start_propose(
        model=body.model,
        min_confidence=body.min_confidence,
        organize_root=body.organize_root,
        no_fallback=body.no_fallback,
        repo=repo,
    )
    return TaskStatusResponse(
        task_id=task.task_id,
        task_type=task.task_type,
        status=task.status,
        progress=task.progress,
        message=task.message,
    )


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
def get_task_status(task_id: str) -> TaskStatusResponse:
    """Poll task status and progress."""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return TaskStatusResponse(
        task_id=task.task_id,
        task_type=task.task_type,
        status=task.status,
        progress=task.progress,
        message=task.message,
        result=task.result,
        error=task.error,
    )

@router.post("/browse-folder", response_model=BrowseResponse)
def browse_folder():
    """Opens a native OS folder picker and returns the selected absolute path."""
    try:
        # We use time.sleep(0.2) to force Windows to render the window ON TOP of the browser
        code = (
            "import tkinter as tk;"
            "from tkinter import filedialog;"
            "import time;"
            "time.sleep(0.2);"
            "root = tk.Tk();"
            "root.withdraw();"
            "root.attributes('-topmost', True);"
            "root.update();"
            "p = filedialog.askdirectory(title='Select Folder to Organize', mustexist=True);"
            "print(p)"
        )
        
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True
        )
        
        path = result.stdout.strip()
        if path:
            return BrowseResponse(path=path.replace("\\", "/"))
        return BrowseResponse(path=None)
    except Exception as e:
        print(f"Browse failed: {e}")
        return BrowseResponse(path=None)