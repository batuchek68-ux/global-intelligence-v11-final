# GitHub 上线运行手册

这份手册用于把 `international-trade-ai` 作为一个真正能在 GitHub 上运行的云端操作系统上线，而不是停留在方案文档。

## 本地位置

当前工程目录：

```text
C:\Users\Surface\Documents\智慧情报分析平台\02_源代码\international-trade-ai
```

发布包位置：

```text
C:\Users\Surface\Documents\智慧情报分析平台\02_源代码\international-trade-ai\dist\international-trade-ai.zip
```

## 上线步骤

1. 在 GitHub 新建一个仓库。
2. 把 `international-trade-ai.zip` 解压后的内容放到仓库根目录。
3. 确认仓库根目录能看到 `.github/workflows/`、`workflows/`、`core/`、`projects/`、`memory/`、`reports/`。
4. 打开仓库 `Settings -> Actions -> General`，允许 GitHub Actions 运行。
5. 如果仓库使用更严格权限，确认 workflow token 至少允许 `contents: write` 和 `issues: write`。
6. 进入 `Actions`，手动运行 `International Trade AI Ops`。
7. 手动运行 `GitHub Cloud Acceptance`，确认 `reports/cloud_acceptance.md` 显示 `PASS`。

## 可选 Secrets

没有 Secrets 时，系统仍会以离线模式跑完整流程。

```text
OPENAI_API_KEY
BING_SEARCH_KEY
WECHAT_WEBHOOK_URL
```

## 云端工作流

`International Trade AI Ops` 是每日主循环：

- 运行 `workflows/preflight_check.py` 检查总部结构。
- 运行 `python -m unittest discover -s tests`。
- 运行 `workflows/daily_job.py` 扫描 `projects/active/`。
- 生成科研简报、视频脚本、重大事项 outbox、总部报告和执行日志。
- 运行 `workflows/persist_state.py` 把 `memory/`、`reports/`、`comm/outbox/`、`research/briefs/`、`media/drafts/` 提交回仓库。

`Owner Decision Handler` 是重大事项回复入口：

- 你在 GitHub Issue 评论 `/approve ...`、`/reject ...` 或 `/revise ...`。
- 系统写入 `memory/decisions/` 和 `memory/continuations/`。
- 系统更新 `comm/outbox/`，评论回执，并关闭已处理 Issue。

`24h Codex Watchdog` 是健康检查：

- 每 6 小时检查 `memory/last_run.json` 是否新鲜。
- 检查是否有等待老板决策的重大事项。
- 写入 `reports/watchdog_status.md`。
- 通过 `workflows/persist_state.py` 把 watchdog 状态提交回 GitHub。

`GitHub Cloud Acceptance` 是上线验收：

- 在云端运行预检、测试、每日主循环和 watchdog。
- 运行 `workflows/cloud_acceptance.py` 检查总部报告、老板收件箱、watchdog、执行日志、重大事项边界和 workflow 配置。
- 写入 `reports/cloud_acceptance.md` 和 `reports/cloud_acceptance.json`。
- 把验收证据提交回 GitHub，并上传为 Actions artifact。

本机没有 `git` 或 GitHub CLI 时，可以用 GitHub REST API 触发云端验收：

先做只读连接体检：

```powershell
$env:GITHUB_TOKEN = "你的 GitHub token"
$env:GITHUB_REPOSITORY = "owner/repository"
python workflows\cloud_connection_check.py
```

结果会写入：

```text
reports/cloud_connection_check.json
```

再触发云端验收：

```powershell
$env:GITHUB_TOKEN = "你的 GitHub token"
$env:GITHUB_REPOSITORY = "owner/repository"
python workflows\trigger_cloud_acceptance.py --ref main
```

这个脚本会触发 `.github/workflows/cloud_acceptance.yml`，轮询 Actions run，并把远程结果写入：

```text
reports/cloud_acceptance_remote.json
```

如果仓库还没有代码，也可以用 REST API 上传当前工程并触发云端验收：

```powershell
$env:GITHUB_TOKEN = "你的 GitHub token"
$env:GITHUB_REPOSITORY = "owner/repository"
python workflows\upload_and_trigger_cloud.py --branch main --confirm-upload
```

结果会写入：

```text
reports/cloud_upload_and_acceptance.json
```

如果目标 GitHub 仓库还不存在，可以先创建仓库、再上传并触发验收：

```powershell
$env:GITHUB_TOKEN = "你的 GitHub token"
$env:GITHUB_REPOSITORY = "owner/repository"
python workflows\create_repo_upload_and_trigger.py --create-repo --confirm-upload
```

完整结果会写入：

```text
reports/cloud_create_upload_and_acceptance.json
```

## 验收标准

第一次云端运行后，检查这些文件或页面：

```text
reports/headquarters_status.md
reports/owner_inbox.md
reports/watchdog_status.md
reports/cloud_acceptance.md
reports/cloud_acceptance.json
memory/last_run.json
memory/cases/*.json
memory/execution_logs/*.json
research/briefs/*.md
media/drafts/*.md
comm/outbox/*.json
```

合格状态：

- `reports/headquarters_status.md` 显示扫描项目数、重大事项数、已解决重大事项数和 execution status。
- `reports/owner_inbox.md` 只列出需要你决定的重大事项；没有待办时显示 no owner decisions required。
- `memory/execution_logs/*.json` 记录每个项目是 `autonomous_executed`、`waiting_for_owner` 或 `continued_after_owner_decision`。
- Actions Summary 先显示 owner inbox，再显示总部报告。
- 重大事项 Issue 能接受 `/approve`、`/reject`、`/revise`，并写回 decision/continuation 记录。
- `24h Codex Watchdog` 手动运行后，`reports/watchdog_status.md` 被更新并提交回仓库。
- `GitHub Cloud Acceptance` 手动运行后，`reports/cloud_acceptance.md` 显示 `PASS`，并列出所有云端总部检查项。

## 日常使用

新增真实项目时，复制：

```text
projects/templates/project_intake.md
```

到：

```text
projects/active/YOUR_PROJECT.md
```

然后填写国家、交易对象、金额、当前沟通、风险、下一步决策。低风险可逆事项由 Codex 自动执行；合同、付款、承诺、合规、对外发布等重大事项会进入 GitHub Issue 队列等待你拍板。
