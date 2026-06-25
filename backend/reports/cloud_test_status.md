# Cloud Test Status

- Status: BLOCKED
- Stage: `configuration`
- Local ready: `True`
- Cloud config ready: `False`

## Missing
- `GITHUB_TOKEN or GH_TOKEN`
- `GITHUB_REPOSITORY`

## Connection Check Details

Missing from connection check:
- `GITHUB_TOKEN or GH_TOKEN`
- `GITHUB_REPOSITORY or cloud.local.json repository`

Token handling: Token is read from environment or prompt only; do not save it to files.

Root commands:

```powershell
.\check-cloud-config-from-root.cmd
.\setup-cloud-test-from-root.cmd
.\run-cloud-test-from-root.cmd -Upload
```

## Next Commands

Use real values only. Do not copy placeholder text such as `owner/repository`, `yourname/...`, or Chinese example words.

From the organized project root:

```powershell
.\run-cloud-test-from-root.cmd -Upload
```

If no token is configured, the command prompts for `GitHub token` and does not save it to disk.

Optional checks:

```powershell
.\check-cloud-config-from-root.cmd
.\setup-cloud-test-from-root.cmd
```

From the source project directory:

Token setup details: `docs/github-token-setup.md`

```powershell
.\run-cloud-test.cmd -Upload
```

Interactive setup is still available:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\setup-cloud-test.ps1
```

## Completion Evidence Required
- reports/cloud_run.json has ok: true and stage: accepted
- reports/cloud_acceptance_remote.json has ok: true and conclusion: success
- GitHub Actions run URL is present
- remote reports/cloud_acceptance.md says PASS
