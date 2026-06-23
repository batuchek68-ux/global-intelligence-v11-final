# One Command Cloud Test

This file is the single entry point for connecting this project to GitHub cloud testing.

The goal is not a blueprint. The goal is to upload the current engineering workspace to GitHub, run GitHub Actions, and collect remote evidence from the `GitHub Cloud Acceptance` workflow.

## Project Location

```text
C:\Users\Surface\Documents\智慧情报分析平台\02_源代码\international-trade-ai
```

## One Command Path

Use this when the GitHub repository already exists and you want the script to upload the project and trigger cloud acceptance:

```powershell
cd C:\Users\Surface\Documents\智慧情报分析平台\02_源代码\international-trade-ai
.\run-cloud-test.cmd -Upload
```

The repository is already saved in `cloud.local.json` for this workspace. If no token is configured, the command asks for `GitHub token` securely and does not save it to disk.

If an old token is still set in the PowerShell session, force a fresh prompt:

```powershell
.\run-cloud-test.cmd -Upload -PromptToken
```

For an interactive prompt that does not save the token to disk:

```powershell
cd C:\Users\Surface\Documents\智慧情报分析平台\02_源代码\international-trade-ai
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\setup-cloud-test.ps1
```

To save only the non-secret repository name for next time:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\setup-cloud-test.ps1 -SaveRepository
```

You can store the non-secret repository name locally by copying:

```text
cloud.local.example.json
```

to:

```text
cloud.local.json
```

`cloud.local.json` is ignored by git and must not contain tokens.

Use this when the GitHub repository already exists but the current project still needs to be uploaded:

```powershell
cd C:\Users\Surface\Documents\智慧情报分析平台\02_源代码\international-trade-ai
$env:GITHUB_TOKEN = "your GitHub token"
$env:GITHUB_REPOSITORY = "real-github-login/international-trade-ai"
python workflows\cloud_run.py --upload --confirm-upload
```

Use this when the repository already contains the workflow and you only need to trigger the cloud acceptance run:

```powershell
cd C:\Users\Surface\Documents\智慧情报分析平台\02_源代码\international-trade-ai
$env:GITHUB_TOKEN = "your GitHub token"
$env:GITHUB_REPOSITORY = "real-github-login/international-trade-ai"
python workflows\cloud_run.py
```

## Evidence Files

The unified cloud run writes:

```text
reports/cloud_run.json
```

The lower-level steps also write:

```text
reports/cloud_connection_check.json
reports/cloud_acceptance_remote.json
reports/cloud_upload_and_acceptance.json
reports/cloud_create_upload_and_acceptance.json
```

Cloud testing is complete only when the remote GitHub Actions evidence shows:

```text
"ok": true
"stage": "accepted" or "completed"
"conclusion": "success"
```

and the remote Actions run generated:

```text
reports/cloud_acceptance.md
```

with `PASS`.

## Current Local Status

The local engineering package is ready to upload and run on GitHub Actions. If `reports/cloud_run.json` says `stage: configuration`, the machine still needs:

```text
GITHUB_TOKEN or GH_TOKEN
GITHUB_REPOSITORY
```

After those are set, rerun this for an existing repository:

```powershell
.\run-cloud-test.cmd -Upload
```
