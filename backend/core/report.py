from __future__ import annotations

from core.models import now_iso


def build_headquarters_report(summary: dict) -> str:
    waiting_cases = []
    resolved_cases = []
    autonomous_cases = []

    for case in summary.get("cases", []):
        classification = case.get("classification", {})
        if case.get("owner_decision"):
            resolved_cases.append(case)
        elif classification.get("is_major_matter"):
            waiting_cases.append(case)
        else:
            autonomous_cases.append(case)

    return "\n".join(
        [
            "# GitHub Cloud AI Headquarters Status",
            "",
            f"Generated: {now_iso()}",
            "",
            "## Command Model",
            "",
            "- GitHub: cloud AI headquarters",
            "- Codex: 24h autonomous executive",
            "- Owner: decides only major matters",
            "",
            "## Summary",
            "",
            f"- Projects scanned: {summary.get('project_count', 0)}",
            f"- Cases created: {summary.get('case_count', 0)}",
            f"- Major matters: {summary.get('major_matter_count', 0)}",
            f"- Resolved major matters: {summary.get('resolved_major_matter_count', 0)}",
            f"- Waiting for owner: {len(waiting_cases)}",
            f"- Autonomous cases: {len(autonomous_cases)}",
            "",
            "## Waiting For Owner Decision",
            "",
            render_case_list(waiting_cases, waiting=True),
            "",
            "## Continuing After Owner Decision",
            "",
            render_case_list(resolved_cases, resolved=True),
            "",
            "## Codex Autonomous Execution",
            "",
            render_case_list(autonomous_cases),
            "",
        ]
    )


def build_owner_inbox(summary: dict) -> str:
    waiting_cases = [
        case
        for case in summary.get("cases", [])
        if case.get("classification", {}).get("is_major_matter") and not case.get("owner_decision")
    ]
    lines = [
        "# Owner Inbox",
        "",
        f"Generated: {now_iso()}",
        "",
        "You only need to decide major matters listed here.",
        "",
    ]
    if not waiting_cases:
        lines.extend(
            [
                "## No Owner Decisions Required",
                "",
                "Codex has no unresolved major matters. Low-risk work continues autonomously.",
                "",
            ]
        )
        return "\n".join(lines)

    lines.extend(["## Waiting For Your Decision", ""])
    for case in waiting_cases:
        project = case.get("project", {})
        judgment = case.get("judgment", {})
        title = project.get("title", "Untitled Project")
        lines.extend(
            [
                f"### {title}",
                "",
                f"- Country: {project.get('country', 'Unknown')}",
                f"- Counterparty: {project.get('counterparty', 'Unknown')}",
                f"- Risk: {judgment.get('level', 'unknown')} ({judgment.get('score', 0)}/100)",
                f"- Triggers: {', '.join(judgment.get('triggers', [])) or 'none'}",
                f"- Recommendation: {judgment.get('recommendation', 'Review required')}",
                "",
                "Reply in the GitHub Issue with one of:",
                "",
                "```text",
                "/approve proceed with this plan",
                "/reject reason for rejection",
                "/revise conditions for continuing",
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def render_case_list(cases: list[dict], waiting: bool = False, resolved: bool = False) -> str:
    if not cases:
        return "None."
    blocks = []
    for case in cases:
        project = case.get("project", {})
        judgment = case.get("judgment", {})
        actions = case.get("actions", [])
        execution = case.get("execution", {})
        lines = [
            f"### {project.get('title', 'Untitled Project')}",
            "",
            f"- Country: {project.get('country', 'Unknown')}",
            f"- Counterparty: {project.get('counterparty', 'Unknown')}",
            f"- Risk: {judgment.get('level', 'unknown')} ({judgment.get('score', 0)}/100)",
            f"- Triggers: {', '.join(judgment.get('triggers', [])) or 'none'}",
        ]
        if execution:
            lines.append(f"- Execution status: {execution.get('status')}")
        if case.get("business_flow_path"):
            lines.append(f"- Real work flow: `{case.get('business_flow_path')}`")
        if waiting:
            lines.append(f"- Decision needed: {judgment.get('recommendation', 'Review required')}")
            lines.append("- Reply: `/approve ...`, `/reject ...`, or `/revise ...`")
        if resolved:
            lines.append(f"- Owner decision: {case.get('owner_decision')}")
            lines.append("- Codex status: continuing according to owner decision")
        if actions:
            lines.append("- Next Codex action: " + actions[-1])
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)
