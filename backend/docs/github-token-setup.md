# GitHub Token Setup

This project needs a GitHub token only for cloud connection, upload, and Actions dispatch. Do not commit the token to this repository.

## Required Values

```text
GITHUB_TOKEN or GH_TOKEN
GITHUB_REPOSITORY
```

`GITHUB_REPOSITORY` must use this format:

```text
real GitHub login/repository name
```

Example:

```text
real-github-login/international-trade-ai
```

Do not copy placeholder text such as `owner/repository`, `yourname/...`, or Chinese example words.

As a non-secret alternative, copy `cloud.local.example.json` to `cloud.local.json` and set:

```json
{
  "repository": "real-github-login/international-trade-ai",
  "branch": "main"
}
```

`cloud.local.json` is ignored by git and must not contain the token.

As a PowerShell environment template, copy:

```powershell
Copy-Item .\cloud.env.example.ps1 .\cloud.env.ps1
```

Edit only the repository line in `cloud.env.ps1`, then load it:

```powershell
. .\cloud.env.ps1
```

`cloud.env.ps1` is ignored by git. Prefer entering the token interactively or setting it only in the current shell.

## Fine-Grained Token

Recommended permissions for a fine-grained personal access token:

```text
Repository access: selected repository, or all repositories if the repository does not exist yet
Contents: Read and write
Actions: Read and write
Issues: Read and write
Metadata: Read
```

If `run-cloud-test.cmd -CreateRepo` will create a new repository, the token must also be allowed to create repositories for the account or organization. For an existing repository, use `run-cloud-test.cmd -Upload`.

## Classic Token

Minimum practical classic token scopes:

```text
repo
workflow
```

Use the shortest expiration that still fits the cloud test window.

## Run Without Saving The Token

Interactive setup prompts for the repository and token, keeps the token in the current PowerShell process, and does not write it to disk:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\setup-cloud-test.ps1
```

To save only the repository name for later runs:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\setup-cloud-test.ps1 -SaveRepository
```

This writes `cloud.local.json`, which is ignored by git. It still does not save the token.

## Run With Environment Variables

For this workspace, the repository is already saved in `cloud.local.json`, so the shortest path is:

```powershell
.\run-cloud-test.cmd -Upload
```

When prompted for `GitHub token`, paste the full token and press Enter. The token is not saved to disk.

You can also set the token manually before running:

```powershell
$env:GITHUB_TOKEN = "your GitHub token"
.\run-cloud-test.cmd -Upload
```

## Success Evidence

Cloud testing is not complete until these remote evidence items exist:

```text
reports/cloud_run.json has ok: true and stage: accepted
reports/cloud_acceptance_remote.json has ok: true and conclusion: success
GitHub Actions run URL is present
remote reports/cloud_acceptance.md says PASS
```
