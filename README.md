# Global Intelligence v11

`batuchek68-ux/global-intelligence-v11` is the main repository for the International Engineering Trade Cloud OS.

It keeps the v11 cloud architecture as the source of truth:

- FastAPI API gateway in `backend/api`.
- Multi-agent orchestration in `backend/core`.
- SaaS service layer in `backend/services`.
- Tenant and runtime safety in `backend/security`.
- Search, research, trade, media, approval, notification, and cloud workflows under `backend/`.
- Desktop, local decision console, and customer portal under `apps/`.

## Run API Locally

```powershell
cd "C:\Users\Surface\Documents\New project\global-intelligence-v11"
python -m pip install -r requirements.txt
python -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000/v1/health
```

## Core API

```text
GET  /v1/health
POST /v1/query
POST /v1/search
POST /v1/projects/intake
POST /v1/projects/analyze
GET  /v1/reports/headquarters
GET  /v1/reports/owner-inbox
GET  /v1/cloud/status
POST /v1/cloud/check
POST /v1/cloud/run
GET  /v1/license/status
POST /v1/license/refresh
POST /v1/approvals/decision
POST /v1/integrations/n8n/trigger/{workflow_id}
```

## Safety Boundary

The system may prepare analysis, drafts, project follow-up plans, search reports, video scripts, and approval requests.

It must not automatically sign contracts, approve payments, quote final prices, promise delivery dates, publish public media, or send formal customer commitments. High-risk matters go to human approval first.

## Secrets

Do not commit tokens, webhooks, license keys, or `.env` files.

Runtime variables are set in PowerShell or GitHub Actions Secrets:

```powershell
$env:GITHUB_TOKEN = "your runtime token"
$env:GITHUB_REPOSITORY = "batuchek68-ux/global-intelligence-v11"
$env:BING_SEARCH_KEY = "optional Bing key"
```

Strict enterprise licensing:

```powershell
$env:CLOUD_OS_REQUIRE_LICENSE = "1"
$env:CLOUD_OS_LICENSE_ENDPOINT = "https://your-license-center.example.com/api/license/check"
$env:CLOUD_OS_ENTERPRISE_ID = "enterprise-code"
$env:CLOUD_OS_LICENSE_TOKEN = "runtime-token"
```

## Desktop Apps

- `apps/decision-hub`: local decision console.
- `apps/desktop-cloud-os`: Windows desktop shell and packaging.
- `apps/trade-platform`: customer-facing portal and intake prototype.

## Cloud Workflows

GitHub Actions call scripts in `backend/workflows`:

- `international_trade_ops.yml`
- `cloud_acceptance.yml`
- `codex_autonomous_repair.yml`
- `watchdog.yml`
- `owner_decision.yml`

All cloud evidence is written under `backend/reports` and `backend/memory`.
