"""Schema and validation dataclasses for rules configuration."""

from dataclasses import dataclass, field
from typing import Dict, List


VALID_CONDITION_TYPES = {"extension", "keyword_in_name", "path_contains"}


class ConfigValidationError(Exception):
    """Raised when rules configuration fails validation."""
    pass


@dataclass
class ConditionConfig:
    """Configuration for an individual rule match condition."""
    type: str
    values: List[str]
    confidence: float

    def __post_init__(self):
        if self.type not in VALID_CONDITION_TYPES:
            raise ConfigValidationError(
                f"Invalid condition type '{self.type}'. Must be one of: {sorted(VALID_CONDITION_TYPES)}"
            )
        if not (0.0 <= self.confidence <= 1.0):
            raise ConfigValidationError(
                f"Confidence score must be between 0.0 and 1.0, got: {self.confidence}"
            )
        if not isinstance(self.values, list) or not self.values:
            raise ConfigValidationError(
                f"Condition values must be a non-empty list of strings, got: {self.values}"
            )
        # Normalize values to strings
        self.values = [str(v).strip() for v in self.values if str(v).strip()]


@dataclass
class RuleConfig:
    """Configuration for a category rule."""
    name: str
    priority: int
    destination: str
    match_any: List[ConditionConfig] = field(default_factory=list)

    def __post_init__(self):
        if not isinstance(self.priority, int):
            try:
                self.priority = int(self.priority)
            except (ValueError, TypeError):
                raise ConfigValidationError(
                    f"Rule '{self.name}' priority must be an integer, got: {self.priority}"
                )
        if not self.destination or not str(self.destination).strip():
            raise ConfigValidationError(f"Rule '{self.name}' must specify a valid destination folder.")


@dataclass
class DefaultsConfig:
    """Default fallback values when no rules match."""
    unmatched_category: str = "uncategorized"
    unmatched_destination: str = "_Uncategorized"
    min_confidence_for_proposal: float = 0.5

    def __post_init__(self):
        if not (0.0 <= self.min_confidence_for_proposal <= 1.0):
            raise ConfigValidationError(
                f"min_confidence_for_proposal must be between 0.0 and 1.0, got: {self.min_confidence_for_proposal}"
            )


@dataclass
class RulesConfig:
    """Root configuration object loaded from YAML."""
    version: int = 1
    organize_root: str = "~/Organized"
    rules: Dict[str, RuleConfig] = field(default_factory=dict)
    defaults: DefaultsConfig = field(default_factory=DefaultsConfig)
