# GitHub Cloud AI Headquarters

This project turns GitHub into the operating headquarters:

- GitHub Actions runs the operating cycle on schedule or on demand.
- Artifacts store briefs, video drafts, outbox tickets, and memory.
- GitHub Issues can become the major-matter decision queue.
- Codex does the recurring work; the owner decides only when the policy says a matter is major.

## Operating Contract

| Role | Responsibility |
| --- | --- |
| GitHub | Cloud AI headquarters, scheduler, artifact store, issue queue |
| Codex | 24h autonomous executive that researches, drafts, judges, records, and escalates |
| Owner | Decides only major matters |

## What Codex Can Do Alone

- Read project files from `projects/active/`.
- Generate research intelligence briefs.
- Draft video scripts.
- Prepare WeChat or Enterprise WeChat approval messages.
- Record memory and operator logs.
- Record structured execution logs in `memory/execution_logs/`.
- Continue low-risk reversible work.

The sample project `projects/active/internal-brief-library.md` demonstrates this autonomous path.

## What Must Be Escalated

- Contract commitment, payment, guarantee, claim, arbitration, breach.
- Sanctions, export control, customs, compliance, political risk.
- Customer promise, external publishing, public video release.
- Risk level `medium` or `high`.
- Amount above the configured threshold.

The sample project `projects/active/demo-port-logistics.md` demonstrates this major-matter path.

## GitHub Setup

1. Create a GitHub repository.
2. Upload the contents of `international-trade-ai`.
3. Enable Actions.
4. Configure optional Secrets:
   - `OPENAI_API_KEY`
   - `BING_SEARCH_KEY`
   - `WECHAT_WEBHOOK_URL`
   - `ENTERPRISE_WECHAT_WEBHOOK_URL`
   - `FEISHU_WEBHOOK_URL` or `LARK_WEBHOOK_URL`
   - `ALERT_EMAIL_TO`
   - `SMTP_HOST`
   - `SMTP_PORT`
   - `SMTP_USERNAME`
   - `SMTP_PASSWORD`
   - `SMTP_FROM`
5. Run **International Trade AI Ops** manually from Actions.

To prepare a local upload package first, run:

```powershell
python workflows\prepare_release.py
```

Then upload `dist/international-trade-ai.zip` to the new repository.

Before each cloud run, `workflows/preflight_check.py` verifies the repository shape and fails fast if the GitHub headquarters is incomplete.
Then `workflows/ensure_labels.py` prepares the GitHub Issue queue labels: `major-matter`, `owner-decision`, and `autonomous`.

After each run, `workflows/persist_state.py` commits operating state back to the repository so the next scheduled cycle inherits memory, decisions, reports, outbox tickets, briefs, and drafts.

`workflows/publish_summary.py` writes `reports/headquarters_status.md` into the GitHub Actions Run Summary, so the owner can read headquarters status directly on the run page.
It also places `reports/owner_inbox.md` first, so unresolved major matters are visible before the full report.

## 24h Watchdog

`.github/workflows/watchdog.yml` runs every 6 hours and writes `reports/watchdog_status.md`. It checks whether the headquarters state is fresh and whether any major matter is waiting for the owner.

## Codex / AI Autonomous Repair

`.github/workflows/codex_autonomous_repair.yml` runs every 6 hours or on demand. It runs preflight, tests, daily operating cycle, watchdog, and cloud acceptance. It writes:

- `reports/autonomous_repair.json`
- `reports/autonomous_repair.md`

This workflow can diagnose and prepare repair evidence automatically. It cannot publish externally, sign, pay, or commit to customers without owner approval.

## Real Work Coverage

Each operating cycle writes `reports/business_flows/*.md` and `reports/business_flows/*.json`. These files cover:

- international trade and domestic project coordination
- WeChat / QQ Meeting agenda, minutes template, and follow-up list
- Douyin / Video Channel / TikTok / YouTube draft content pipeline
- approval boundaries for public publishing and customer commitments

When a major matter appears, the workflow writes:

- `comm/outbox/*.json`
- `memory/operator_logs/*.md`
- `memory/cases/*.json`

If workflow permissions allow `issues: write`, it also opens a GitHub Issue labeled `major-matter` and `owner-decision`.

If notification secrets are configured, the same major matter is also sent to Enterprise WeChat, Feishu/Lark, and email.

## Owner Reply Loop

The owner replies in GitHub Issue or WeChat with:

- `/approve optional notes`
- `/reject optional notes`
- `/revise conditions`

Codex then records the decision and continues from the new boundary.

## Comment Trigger

The `Owner Decision Handler` workflow listens to GitHub Issue comments. When a major-matter Issue receives one of these comments, the workflow runs `workflows/resolve_major_matter.py`:

- `/approve proceed with staged commitment`
- `/reject payment risk is too high`
- `/revise only commit after customs broker confirms timeline`

The result is stored in:

- `memory/decisions/*.json`
- `memory/continuations/*.md`
- updated `comm/outbox/*.json`

When running inside GitHub, Codex also comments back on the Issue with a decision receipt and the continuation path.
After the receipt, Codex closes the Issue with `state_reason: completed` so the owner inbox stays clean.

The next scheduled operating cycle reads resolved outbox tickets and continues according to the owner decision instead of opening another approval loop for the same matter.

## Headquarters Report

Every operating cycle writes `reports/headquarters_status.md`. This is the owner-facing status page:

- what is waiting for owner decision
- what Codex continued after owner approval
- what Codex handled autonomously
- the next Codex action for each project
