"""Loads and validates the YAML rules configuration file."""

from pathlib import Path
from typing import Any, Dict, Union
import yaml

from organizer.config.schema import (
    ConditionConfig,
    ConfigValidationError,
    DefaultsConfig,
    RuleConfig,
    RulesConfig,
)


def load_rules_config(config_path: Union[str, Path]) -> RulesConfig:
    """Load, parse, and validate rules configuration from a YAML file.
    
    Args:
        config_path: Path to the YAML configuration file.
        
    Returns:
        Validated RulesConfig instance.
        
    Raises:
        FileNotFoundError: If the file does not exist.
        ConfigValidationError: If the YAML structure or values are invalid.
    """
    path = Path(config_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigValidationError(f"Malformed YAML in {path}: {e}") from e

    if not isinstance(raw_data, dict):
        raise ConfigValidationError(f"Configuration root in {path} must be a mapping/dict.")

    version = raw_data.get("version", 1)
    organize_root = raw_data.get("organize_root", "~/Organized")

    # Parse defaults
    raw_defaults = raw_data.get("defaults", {})
    if not isinstance(raw_defaults, dict):
        raise ConfigValidationError("'defaults' section must be a mapping/dict.")

    defaults = DefaultsConfig(
        unmatched_category=raw_defaults.get("unmatched_category", "uncategorized"),
        unmatched_destination=raw_defaults.get("unmatched_destination", "_Uncategorized"),
        min_confidence_for_proposal=float(raw_defaults.get("min_confidence_for_proposal", 0.5)),
    )

    # Parse rules
    raw_rules = raw_data.get("rules", {})
    if not isinstance(raw_rules, dict):
        raise ConfigValidationError("'rules' section must be a mapping/dict.")

    rules: Dict[str, RuleConfig] = {}
    for rule_name, rule_body in raw_rules.items():
        if not isinstance(rule_body, dict):
            raise ConfigValidationError(f"Rule '{rule_name}' must be a mapping/dict.")

        priority = rule_body.get("priority")
        if priority is None:
            raise ConfigValidationError(f"Rule '{rule_name}' is missing required 'priority' field.")

        destination = rule_body.get("destination")
        if not destination:
            raise ConfigValidationError(f"Rule '{rule_name}' is missing required 'destination' field.")

        match_any_raw = rule_body.get("match_any", [])
        if not isinstance(match_any_raw, list):
            raise ConfigValidationError(f"Rule '{rule_name}' 'match_any' must be a list of conditions.")

        conditions: list[ConditionConfig] = []
        for idx, cond_raw in enumerate(match_any_raw):
            if not isinstance(cond_raw, dict):
                raise ConfigValidationError(
                    f"Condition #{idx + 1} in rule '{rule_name}' must be a mapping/dict."
                )

            cond_type = cond_raw.get("type")
            cond_values = cond_raw.get("values", [])
            cond_confidence = cond_raw.get("confidence")

            if cond_type is None or cond_confidence is None:
                raise ConfigValidationError(
                    f"Condition in rule '{rule_name}' must specify 'type', 'values', and 'confidence'."
                )

            conditions.append(
                ConditionConfig(
                    type=str(cond_type),
                    values=list(cond_values),
                    confidence=float(cond_confidence),
                )
            )

        rules[rule_name] = RuleConfig(
            name=rule_name,
            priority=int(priority),
            destination=str(destination),
            match_any=conditions,
        )

    return RulesConfig(
        version=int(version),
        organize_root=str(organize_root),
        rules=rules,
        defaults=defaults,
    )
