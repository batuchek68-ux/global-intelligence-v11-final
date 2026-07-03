"""v12 Continuous Learning Engine.

The Learning phase closes the Planner→Executor→Judge→Decision loop by
collecting execution feedback, measuring outcome quality, and updating
the system's knowledge base for continuous improvement.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class FeedbackType(Enum):
    EXPLICIT = "explicit"        # User-rated feedback
    IMPLICIT = "implicit"        # Inferred from actions
    OUTCOME = "outcome"          # Measured business result
    CORRECTION = "correction"    # Human override / fix


class LearningSignal(Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


@dataclass
class FeedbackRecord:
    id: str
    execution_id: str
    feedback_type: FeedbackType
    signal: LearningSignal
    score: float                # 0.0 to 1.0
    source: str                 # e.g. "user_rating", "outcome_measurement"
    context: dict[str, Any] = field(default_factory=dict)
    notes: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class LearningPattern:
    """A learned pattern extracted from feedback over time."""
    id: str
    domain: str                # e.g. "matching", "pricing", "content"
    pattern_type: str          # e.g. "success_factor", "failure_mode"
    description: str
    confidence: float          # 0.0 to 1.0
    evidence_count: int
    examples: list[dict[str, Any]] = field(default_factory=list)
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ContinuousLearningEngine:
    """v12 learning engine that closes the intelligent feedback loop.

    Collects feedback from all execution phases (Planner/Executor/Judge/Decision),
    extracts patterns, and updates the knowledge base so the system improves
    over time without manual retraining.

    Architecture:
        Feedback Ingestion → Pattern Extraction → Knowledge Update → Model Refinement
    """

    def __init__(self, storage_dir: str | Path = "backend/memory/learning"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.feedback_store: list[FeedbackRecord] = []
        self.patterns: dict[str, list[LearningPattern]] = {}
        self._load_existing()

    # ── Feedback Ingestion ──────────────────────────────────────────

    def ingest_feedback(
        self,
        execution_id: str,
        feedback_type: FeedbackType,
        signal: LearningSignal,
        score: float,
        source: str = "system",
        context: dict[str, Any] | None = None,
        notes: str = "",
    ) -> FeedbackRecord:
        """Record a feedback signal from any execution phase."""
        record = FeedbackRecord(
            id=f"fb_{execution_id}_{datetime.now(timezone.utc).timestamp()}",
            execution_id=execution_id,
            feedback_type=feedback_type,
            signal=signal,
            score=max(0.0, min(1.0, score)),
            source=source,
            context=context or {},
            notes=notes,
        )
        self.feedback_store.append(record)
        self._persist_feedback(record)
        logger.info(
            "Learning: ingested %s feedback for %s (score=%.2f)",
            signal.value, execution_id, score,
        )
        return record

    def ingest_outcome(
        self,
        execution_id: str,
        metric_name: str,
        actual_value: float,
        expected_value: float,
        domain: str = "general",
    ) -> FeedbackRecord:
        """Measure real business outcome against expected value."""
        ratio = actual_value / max(expected_value, 0.001)
        signal = LearningSignal.POSITIVE if ratio >= 0.8 else (
            LearningSignal.NEUTRAL if ratio >= 0.5 else LearningSignal.NEGATIVE
        )
        return self.ingest_feedback(
            execution_id=execution_id,
            feedback_type=FeedbackType.OUTCOME,
            signal=signal,
            score=min(ratio, 1.0),
            source="outcome_measurement",
            context={
                "domain": domain,
                "metric": metric_name,
                "actual": actual_value,
                "expected": expected_value,
                "ratio": round(ratio, 4),
            },
        )

    # ── Pattern Extraction ──────────────────────────────────────────

    def extract_patterns(self, domain: str | None = None) -> list[LearningPattern]:
        """Analyze feedback store and extract actionable patterns."""
        domains = [domain] if domain else self._discover_domains()
        new_patterns: list[LearningPattern] = []

        for dom in domains:
            domain_feedback = [
                f for f in self.feedback_store
                if f.context.get("domain", "general") == dom
            ]

            if len(domain_feedback) < 5:
                continue

            positive = [f for f in domain_feedback if f.signal == LearningSignal.POSITIVE]
            negative = [f for f in domain_feedback if f.signal == LearningSignal.NEGATIVE]

            if positive:
                pattern = LearningPattern(
                    id=f"pat_{dom}_success_{datetime.now(timezone.utc).timestamp()}",
                    domain=dom,
                    pattern_type="success_factor",
                    description=f"High-performing pattern in {dom}: avg score {self._avg_score(positive):.2f}",
                    confidence=min(len(positive) / max(len(domain_feedback), 1), 1.0),
                    evidence_count=len(positive),
                    examples=[f.context for f in positive[-3:]],
                )
                new_patterns.append(pattern)
                self.patterns.setdefault(dom, []).append(pattern)

            if negative:
                pattern = LearningPattern(
                    id=f"pat_{dom}_failure_{datetime.now(timezone.utc).timestamp()}",
                    domain=dom,
                    pattern_type="failure_mode",
                    description=f"Failure mode in {dom}: {len(negative)} cases, avg score {self._avg_score(negative):.2f}",
                    confidence=min(len(negative) / max(len(domain_feedback), 1), 1.0),
                    evidence_count=len(negative),
                    examples=[f.context for f in negative[-3:]],
                )
                new_patterns.append(pattern)
                self.patterns.setdefault(dom, []).append(pattern)

        self._persist_patterns()
        logger.info("Learning: extracted %d patterns across %d domains", len(new_patterns), len(domains))
        return new_patterns

    # ── Knowledge Update ────────────────────────────────────────────

    def get_improvement_suggestions(self, domain: str | None = None) -> list[dict[str, Any]]:
        """Generate actionable improvement suggestions based on learned patterns."""
        suggestions: list[dict[str, Any]] = []
        domains = [domain] if domain else list(self.patterns.keys())

        for dom in domains:
            patterns = self.patterns.get(dom, [])
            failures = [p for p in patterns if p.pattern_type == "failure_mode"]
            successes = [p for p in patterns if p.pattern_type == "success_factor"]

            if failures and len(failures) > 2:
                suggestions.append({
                    "domain": dom,
                    "priority": "high",
                    "type": "failure_remediation",
                    "suggestion": f"Address {len(failures)} failure patterns in {dom}",
                    "confidence": max(p.confidence for p in failures),
                    "affected_executions": sum(p.evidence_count for p in failures),
                })

            if successes:
                suggestions.append({
                    "domain": dom,
                    "priority": "medium",
                    "type": "success_amplification",
                    "suggestion": f"Amplify {len(successes)} success patterns in {dom}",
                    "confidence": max(p.confidence for p in successes),
                    "affected_executions": sum(p.evidence_count for p in successes),
                })

        return sorted(suggestions, key=lambda s: s["confidence"], reverse=True)

    def get_performance_summary(self) -> dict[str, Any]:
        """Generate a summary of system performance across all domains."""
        if not self.feedback_store:
            return {"status": "no_data", "message": "No feedback data collected yet."}

        total = len(self.feedback_store)
        positive = sum(1 for f in self.feedback_store if f.signal == LearningSignal.POSITIVE)
        negative = sum(1 for f in self.feedback_store if f.signal == LearningSignal.NEGATIVE)
        avg_score = self._avg_score(self.feedback_store)

        by_domain: dict[str, dict[str, Any]] = {}
        for f in self.feedback_store:
            dom = f.context.get("domain", "general")
            if dom not in by_domain:
                by_domain[dom] = {"total": 0, "positive": 0, "negative": 0, "scores": []}
            by_domain[dom]["total"] += 1
            if f.signal == LearningSignal.POSITIVE:
                by_domain[dom]["positive"] += 1
            elif f.signal == LearningSignal.NEGATIVE:
                by_domain[dom]["negative"] += 1
            by_domain[dom]["scores"].append(f.score)

        return {
            "status": "active",
            "total_feedback": total,
            "positive_rate": round(positive / max(total, 1), 3),
            "negative_rate": round(negative / max(total, 1), 3),
            "average_score": round(avg_score, 3),
            "by_domain": {
                dom: {
                    "total": d["total"],
                    "positive_rate": round(d["positive"] / max(d["total"], 1), 3),
                    "avg_score": round(sum(d["scores"]) / max(len(d["scores"]), 1), 3),
                }
                for dom, d in by_domain.items()
            },
        }

    # ── Internal Helpers ────────────────────────────────────────────

    def _discover_domains(self) -> list[str]:
        domains: set[str] = set()
        for f in self.feedback_store:
            domains.add(f.context.get("domain", "general"))
        return list(domains) if domains else ["general"]

    @staticmethod
    def _avg_score(records: list[FeedbackRecord]) -> float:
        if not records:
            return 0.0
        return sum(r.score for r in records) / len(records)

    def _persist_feedback(self, record: FeedbackRecord) -> None:
        path = self.storage_dir / "feedback.jsonl"
        try:
            with open(path, "a", encoding="utf-8") as fp:
                fp.write(json.dumps({
                    "id": record.id,
                    "execution_id": record.execution_id,
                    "feedback_type": record.feedback_type.value,
                    "signal": record.signal.value,
                    "score": record.score,
                    "source": record.source,
                    "context": record.context,
                    "notes": record.notes,
                    "created_at": record.created_at.isoformat(),
                }, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.warning("Failed to persist feedback: %s", exc)

    def _load_existing(self) -> None:
        path = self.storage_dir / "feedback.jsonl"
        if not path.exists():
            return
        try:
            with open(path, "r", encoding="utf-8") as fp:
                for line in fp:
                    if line.strip():
                        self.feedback_store.append(self._deserialize_feedback(line))
        except Exception as exc:
            logger.warning("Failed to load feedback history: %s", exc)

        patterns_path = self.storage_dir / "patterns.json"
        if patterns_path.exists():
            try:
                data = json.loads(patterns_path.read_text(encoding="utf-8"))
                self.patterns = {
                    dom: [LearningPattern(**p) for p in ps]
                    for dom, ps in data.items()
                }
            except Exception as exc:
                logger.warning("Failed to load patterns: %s", exc)

    @staticmethod
    def _deserialize_feedback(line: str) -> FeedbackRecord:
        data = json.loads(line)
        return FeedbackRecord(
            id=data["id"],
            execution_id=data["execution_id"],
            feedback_type=FeedbackType(data["feedback_type"]),
            signal=LearningSignal(data["signal"]),
            score=data["score"],
            source=data.get("source", "system"),
            context=data.get("context", {}),
            notes=data.get("notes", ""),
            created_at=datetime.fromisoformat(data["created_at"]),
        )

    def _persist_patterns(self) -> None:
        path = self.storage_dir / "patterns.json"
        try:
            data = {
                dom: [{
                    "id": p.id,
                    "domain": p.domain,
                    "pattern_type": p.pattern_type,
                    "description": p.description,
                    "confidence": p.confidence,
                    "evidence_count": p.evidence_count,
                    "examples": p.examples,
                    "last_updated": p.last_updated.isoformat(),
                } for p in ps]
                for dom, ps in self.patterns.items()
            }
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed to persist patterns: %s", exc)


# Singleton instance
_learning_engine: ContinuousLearningEngine | None = None


def get_learning_engine(storage_dir: str | None = None) -> ContinuousLearningEngine:
    global _learning_engine
    if _learning_engine is None:
        _learning_engine = ContinuousLearningEngine(storage_dir or "backend/memory/learning")
    return _learning_engine
