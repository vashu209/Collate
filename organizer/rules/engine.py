"""Deterministic rule-based classifier evaluating FileRecords against RulesConfig."""

from pathlib import Path
from typing import List, Optional, Tuple

from organizer.ai.base import Classifier
from organizer.config.schema import ConditionConfig, RuleConfig, RulesConfig
from organizer.rules.models import FileRecord, Proposal, RuleMatch


class RuleBasedClassifier(Classifier):
    """Deterministic, rule-based file classifier.
    
    Evaluates file metadata against configured rules using extension,
    keyword in filename, and path content matching.
    Satisfies the same Classifier ABC interface as future AI classifiers.
    """

    def __init__(self, config: RulesConfig):
        self.config = config
        self.organize_root = Path(config.organize_root).expanduser().resolve()

    def _matches_condition(
        self, condition: ConditionConfig, record: FileRecord
    ) -> Tuple[bool, Optional[str]]:
        """Evaluate whether a file record matches a condition.
        
        All string matching is case-insensitive.
        
        Returns:
            Tuple of (is_matched, matched_value)
        """
        cond_type = condition.type.lower()

        if cond_type == "extension":
            rec_ext = record.extension.lower()
            for val in condition.values:
                # Normalize values by removing leading dots and lowercasing
                norm_val = val.lower().lstrip(".")
                if rec_ext == norm_val:
                    return True, val

        elif cond_type == "keyword_in_name":
            rec_name = record.filename.lower()
            for val in condition.values:
                if val.lower() in rec_name:
                    return True, val

        elif cond_type == "path_contains":
            rec_path = record.path.lower()
            for val in condition.values:
                if val.lower() in rec_path:
                    return True, val

        return False, None

    def _evaluate_rule(self, rule: RuleConfig, record: FileRecord) -> Optional[RuleMatch]:
        """Evaluate all conditions in a rule against a file record.
        
        If multiple conditions match within the same rule, pick the condition
        with the highest confidence.
        """
        best_match: Optional[Tuple[float, str, str]] = None  # (confidence, cond_type, matched_val)

        for cond in rule.match_any:
            matched, val = self._matches_condition(cond, record)
            if matched and val is not None:
                if best_match is None or cond.confidence > best_match[0]:
                    best_match = (cond.confidence, cond.type, val)

        if best_match is not None:
            confidence, cond_type, matched_val = best_match
            rationale = (
                f"Matched rule '{rule.name}' (priority {rule.priority}) "
                f"via {cond_type}='{matched_val}' with confidence {confidence:.2f}"
            )
            return RuleMatch(
                category=rule.name,
                destination=rule.destination,
                priority=rule.priority,
                confidence=confidence,
                matched_condition_type=cond_type,
                matched_value=matched_val,
                rationale=rationale,
            )

        return None

    def classify(self, record: FileRecord) -> Proposal:
        """Classify a file record into an organization Proposal.
        
        When multiple categories match, the highest-priority category wins.
        Ties in priority are resolved by highest confidence score.
        
        Args:
            record: FileRecord with extracted metadata.
            
        Returns:
            Proposal containing proposed category, destination, confidence, and rationale.
        """
        matches: List[RuleMatch] = []

        for rule in self.config.rules.values():
            match = self._evaluate_rule(rule, record)
            if match is not None:
                matches.append(match)

        # Sort matches by priority descending, then confidence descending
        matches.sort(key=lambda m: (m.priority, m.confidence), reverse=True)

        min_conf = self.config.defaults.min_confidence_for_proposal

        if matches and matches[0].confidence >= min_conf:
            best = matches[0]
            dest_dir = self.organize_root / best.destination
            proposed_dest = str(dest_dir / record.filename)

            return Proposal(
                file_id=record.id,
                source_path=record.path,
                proposed_category=best.category,
                proposed_destination=proposed_dest,
                confidence=best.confidence,
                rationale=best.rationale,
                status="pending",
            )

        # Fallback to default unmatched category
        dest_dir = self.organize_root / self.config.defaults.unmatched_destination
        proposed_dest = str(dest_dir / record.filename)
        fallback_rationale = (
            f"No matching rule satisfied minimum confidence threshold ({min_conf}); "
            f"assigned fallback '{self.config.defaults.unmatched_category}'"
        )

        return Proposal(
            file_id=record.id,
            source_path=record.path,
            proposed_category=self.config.defaults.unmatched_category,
            proposed_destination=proposed_dest,
            confidence=0.0,
            rationale=fallback_rationale,
            status="pending",
        )


# Alias RuleEngine to RuleBasedClassifier for compatibility
RuleEngine = RuleBasedClassifier
