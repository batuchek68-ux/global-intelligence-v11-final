# Decision Hub

一个本地运行的决策中枢第一版，覆盖四个阶段：

1. 接真实搜索：Bing、Semantic Scholar 学术搜索、Open Library 图书馆搜索。
2. 接 Codex 实际决策：项目和会议事项的方案评分、建议、请示判断。
3. 加“请示 -> 你回复 -> 学习”闭环：回复会写入本地 JSON 学习记录。
4. 预留微信、视频、多媒体扩展位：当前版本先不接入，避免第一版过重。

## 运行

在本目录执行：

```powershell
.\server.ps1
```

然后打开：

```text
http://127.0.0.1:8787/
```

如需更换端口：

```powershell
.\server.ps1 -Port 8790
```

## Bing 配置

Bing Web Search 需要 API Key。运行服务前设置：

```powershell
$env:BING_SEARCH_KEY = "你的 Bing Search API Key"
```

可选自定义 endpoint：

```powershell
$env:BING_SEARCH_ENDPOINT = "https://api.bing.microsoft.com/v7.0/search"
```

未设置 Bing Key 时，Bing 栏会提示缺少环境变量；学术和图书馆搜索仍可使用。

## 数据

本地数据保存在：

```text
data/store.json
```

包括：

- decisions：项目/会议决策记录
- approvals：待请示和已回复事项
- feedback：你的回复历史
- learning：批准模式、否决模式、复盘备注

## 后续扩展

- 微信：把 approvals 推送到企业微信/微信机器人，回复后回写 feedback。
- 视频：把会议录音转写成 context，再生成决策建议。
- 多媒体：把图片、PDF、PPT 提取成 evidence，进入同一套决策流程。
