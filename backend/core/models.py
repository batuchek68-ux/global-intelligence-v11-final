from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class Project:
    path: str
    title: str
    country: str = "Unknown"
    counterparty: str = "Unknown"
    amount: float = 0.0
    stage: str = "unknown"
    latest_communication: str = ""
    risks: list[str] = field(default_factory=list)
    next_decision: str = ""


@dataclass
class RiskJudgment:
    level: str
    score: int
    triggers: list[str]
    recommendation: str
    needs_approval: bool


@dataclass
class OperatingCase:
    project: Project
    judgment: RiskJudgment
    actions: list[str]
    brief_path: str
    video_path: str
    outbox_path: str | None
    created_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "created_at": self.created_at,
            "project": self.project.__dict__,
            "judgment": self.judgment.__dict__,
            "actions": self.actions,
            "brief_path": self.brief_path,
            "video_path": self.video_path,
            "outbox_path": self.outbox_path,
        }
