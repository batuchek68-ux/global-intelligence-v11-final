from __future__ import annotations

from core.models import Project, RiskJudgment


def build_video_script(project: Project, judgment: RiskJudgment) -> str:
    return f"""# Multi-Platform Video Draft: {project.title}

DRAFT - Not approved for sending

## Positioning

International engineering trade update for decision-makers.

## Platforms

- Douyin
- Video Channel
- TikTok
- YouTube

## 90-Second Script

0-15s: We are tracking {project.title} in {project.country}. The current stage is {project.stage}.

15-35s: The latest communication shows: {project.latest_communication or "latest communication is not yet recorded"}.

35-55s: The main risk level is {judgment.level}, with a score of {judgment.score}/100. Key triggers: {", ".join(judgment.triggers) if judgment.triggers else "no major trigger yet"}.

55-75s: Recommended next move: {judgment.recommendation}

75-90s: Before external publishing or customer commitment, the team should confirm approval status and update the project memory.

## Review Gate

This draft is not approved for publishing until the approval ticket is resolved.
Do not publish to Douyin, Video Channel, TikTok, YouTube, WeChat, or any public channel without human approval.
"""
