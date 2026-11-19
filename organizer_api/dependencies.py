"""Dependency injection helpers for FastAPI routes."""

from fastapi import Depends

from organizer.config.loader import load_rules_config
from organizer.config.schema import RulesConfig
from organizer.feedback.recorder import FeedbackRecorder
from organizer.operations.mover import FileMover
from organizer.operations.rollback import RollbackManager
from organizer.storage.repository import Repository
from organizer_api.config import settings


def get_repo() -> Repository:
    """Return an active Repository instance."""
    return Repository(settings.db_path)


def get_mover(repo: Repository = Depends(get_repo)) -> FileMover:
    """Return a FileMover instance."""
    return FileMover(repo)


def get_rollback_manager(repo: Repository = Depends(get_repo)) -> RollbackManager:
    """Return a RollbackManager instance."""
    return RollbackManager(repo)


def get_recorder(repo: Repository = Depends(get_repo)) -> FeedbackRecorder:
    """Return a FeedbackRecorder instance."""
    return FeedbackRecorder(repo)


def get_rules_config() -> RulesConfig:
    """Return loaded RulesConfig."""
    return load_rules_config(settings.rules_path)
