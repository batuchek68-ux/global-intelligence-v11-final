# Trade Platform

`apps/trade-platform` is the customer-facing entry for the v11 system. It is used for international engineering trade presentation, inquiry intake, project explanation, and early customer communication.

## Local Preview

Open the static page directly:

```text
frontend/web/index.html
```

Or run the local preview service:

```powershell
.\run-web.ps1
```

Then open:

```text
http://127.0.0.1:8890/
```

## v11 Integration Boundary

This app must call `backend/api/main.py` through v11 APIs for project intake, search, reports, approval status, and audit records.

It must not bypass:

- v11 tenant isolation
- v11 license checks
- v11 risk gates
- human approval for external commitments
- `backend/memory/audit.log` append-only evidence

Customer replies, quotations, delivery promises, payment terms, contracts, video publishing, and public posts remain drafts until human approval.
