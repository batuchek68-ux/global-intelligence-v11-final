#!/usr/bin/env python3
"""线上接入验收：跑一次 fetch_news + POST /v1/query，并校验合规字段。

用法（在完整仓库根目录执行）：
    python3 verify_live.py --repo /path/to/global-intelligence-v11-final \
        --query "Kazakhstan port construction customs payment" \
        --news-out data/raw_news_live.json \
        --api-url http://127.0.0.1:8000/v1/query \
        --run-api

只跑新闻采集（不碰 API）：
    python3 verify_live.py --repo /path/to/repo --run-news

出口 IP 被 GDELT 限流时，只跑 RSS 降级链路：
    python3 verify_live.py --repo /path/to/repo --run-news --skip-gdelt --query Kazakhstan

只跑 API（服务已在别处启动）：
    python3 verify_live.py --repo /path/to/repo --run-api --api-url http://host:8000/v1/query

前置条件：
    pip install -r requirements.txt 中已有的 requests / feedparser / fastapi / uvicorn
    API 需要 license core_allowed() 放行；若返回 403 先看 license_status。

注意：--run-news 会发起真实外部请求（GDELT API + config/sources.json 中 enabled 的 RSS）。
      所有请求都经过 RobotsGate；license=unknown-verify 的源默认 enabled=false，不会访问。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REQUIRED_PROVENANCE = {"source_tier", "fetch_url", "robots_decision", "fetched_at"}


def log(tag: str, msg: str) -> None:
    print(f"[{tag}] {msg}", flush=True)


def check_env(repo: Path) -> None:
    """在做任何网络动作前，把会失败的前置条件一次性查清。"""
    required = [
        repo / "src" / "fetch_news.py",
        repo / "src" / "acquisition" / "robots_gate.py",
        repo / "src" / "acquisition" / "resolver.py",
        repo / "config" / "sources.json",
        repo / "backend" / "core" / "agents.py",
        repo / "backend" / "core" / "orchestration.py",
        repo / "backend" / "core" / "judge_with_provenance.py",
    ]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        raise SystemExit("缺少必要文件:\n  " + "\n  ".join(missing))

    for mod in ("requests", "feedparser"):
        try:
            __import__(mod)
        except ImportError:
            raise SystemExit(f"缺少 Python 依赖 {mod}，请先 pip install -r requirements.txt")

    config = json.loads((repo / "config" / "sources.json").read_text(encoding="utf-8"))
    enabled = [f["id"] for f in config.get("feeds", []) if f.get("enabled")]
    log("ENV", f"repo={repo}")
    log("ENV", f"strategy={config.get('strategy')} enabled_feeds={enabled} gdelt={config.get('gdelt', {}).get('enabled')}")
    if config.get("strategy") == "compliance_first":
        log("WARN", "当前策略为 compliance_first：无合规结果时会抛 FallbackExhausted")


NEWS_RUNNER = r'''
import sys
sys.path.insert(0, "src")
import fetch_news as f

skip_gdelt = sys.argv[4] == "1"
gdelt_retries = int(sys.argv[5])

if skip_gdelt:
    # 不修改仓库代码：只在本进程把官方 API 层替换成空实现，走 RSS 降级链。
    class _NoGdelt:
        def __init__(self, *args, **kwargs):
            pass

        def search(self, *args, **kwargs):
            return []
    f.GdeltProvider = _NoGdelt
else:
    # 默认重试 8 次、累计退避可达 210s，容易把验收脚本拖到超时。
    # 这里仅在验收进程内收紧重试上限，不改变仓库默认行为。
    _original_search = f.GdeltProvider.search
    def _bounded_search(self, query, timespan="24h", language="english", retries=None):
        return _original_search(self, query, timespan, language,
                                gdelt_retries if retries is None else retries)
    f.GdeltProvider.search = _bounded_search

f.fetch_news(sys.argv[1], sys.argv[2], sys.argv[3])
'''


def run_news(repo: Path, query: str, timespan: str, out_path: str, timeout: int,
             skip_gdelt: bool, gdelt_retries: int) -> dict[str, Any]:
    """以子进程跑 fetch_news，避免主进程 sys.path / 模块缓存干扰。"""
    rel_out = str(Path(out_path)) if Path(out_path).is_absolute() else str(repo / out_path)
    cmd = [
        sys.executable, "-c", NEWS_RUNNER,
        query, timespan, rel_out, "1" if skip_gdelt else "0", str(gdelt_retries),
    ]
    mode = "RSS-only" if skip_gdelt else f"GDELT(retries={gdelt_retries})→RSS"
    log("NEWS", f"开始真实采集 mode={mode} query={query!r} timeout={timeout}s")
    started = time.monotonic()
    proc = subprocess.run(cmd, cwd=str(repo), capture_output=True, text=True, timeout=timeout)
    log("NEWS", f"退出码={proc.returncode} 耗时={time.monotonic() - started:.1f}s")
    if proc.stdout.strip():
        log("NEWS", proc.stdout.strip()[-500:])
    if proc.returncode != 0:
        raise RuntimeError(f"fetch_news 失败:\n{proc.stderr[-2000:]}")

    records = json.loads(Path(rel_out).read_text(encoding="utf-8"))
    if not records:
        log("WARN", "采集结果为 0 条 —— 检查 fallback_log / GDELT 限流 / 网络可达性")

    bad = [r for r in records if not REQUIRED_PROVENANCE <= set(r.get("_provenance") or {})]
    denied = [r for r in records if (r.get("_provenance") or {}).get("robots_decision") in ("deny", "unreachable")]
    tiers = sorted({(r.get("_provenance") or {}).get("source_tier", "?") for r in records})
    log("NEWS", f"records={len(records)} 缺溯源={len(bad)} robots拒绝={len(denied)} tiers={tiers}")
    if bad:
        log("FAIL", f"前 3 条缺溯源记录: {[r.get('title') for r in bad[:3]]}")
    # 0 条不是脚本错误：可能是 GDELT 限流 / 出口 IP 被代理阻断 / 关键词无结果。
    # 这类情况不判 FAIL，但要在 stdout 给出可执行的诊断提示。
    if not records:
        log("WARN", "诊断建议：核对 GDELT 是否 429（1 req/5s）、代理是否放行 feeds，"
                    "或用 --query 换更宽泛的关键词；见 config/sources.json 的 feeds[].enabled")
    return {
        "records": len(records),
        "missing_provenance": len(bad),
        "robots_denied": len(denied),
        "tiers": tiers,
        "out_path": rel_out,
        "ok": not bad and not denied,   # 0 条仍算通过，因为合规链路本身没违规
    }


def check_api_health(api_url: str, timeout: int) -> None:
    """POST 前先探活，避免把“服务没启动”误判成编排失败。"""
    health_url = api_url.rsplit("/", 1)[0] + "/health"
    try:
        with urllib.request.urlopen(health_url, timeout=min(timeout, 10)) as resp:
            health = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"API 健康检查失败（{health_url}）: {exc}；请先启动服务")
    log("API", f"health={health.get('status')} version={health.get('version')} "
               f"license_allowed={(health.get('license') or {}).get('allowed')}")


def run_api(api_url: str, query: str, org_id: str, user_id: str, timeout: int,
            evidence_path: str | None) -> dict[str, Any]:
    check_api_health(api_url, timeout)
    payload: dict[str, Any] = {
        "query": query,
        "org_id": org_id,
        "user_id": user_id,
        "metadata": {"country": "Kazakhstan"},
    }
    if evidence_path:
        payload["evidence"] = json.loads(Path(evidence_path).read_text(encoding="utf-8"))

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        api_url, data=body,
        headers={"Content-Type": "application/json", "User-Agent": "v11-acceptance-check/1.0"},
        method="POST",
    )
    log("API", f"POST {api_url} query={query!r}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:1000]
        raise RuntimeError(f"HTTP {exc.code}: {detail}")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"无法连接 API（服务是否已启动？）: {exc.reason}")

    orch = result.get("orchestration") or {}
    tasks = orch.get("tasks") or []
    collection = ((result.get("team_response") or {}).get("collection")
                  or (orch.get("result") or {}).get("collection") or {})
    ids = [t.get("id") for t in tasks]
    log("API", f"status={result.get('status')} task_count={orch.get('task_count')} tasks={ids}")
    log("API", f"collection.status={collection.get('status')} item_count={collection.get('item_count')} "
               f"robots_denied={collection.get('robots_denied')}")

    problems: list[str] = []
    if result.get("status") != "success":
        problems.append(f"status={result.get('status')}")
    if "task_3b" not in ids:
        problems.append("task_3b 未出现在任务图中 —— agents.py/orchestration.py 补丁可能未生效")
    if not collection:
        problems.append("结果中无 collection 字段 —— 检查 SynthesizerAgent 补丁")
    for problem in problems:
        log("FAIL", problem)
    return {
        "http_status": status,
        "status": result.get("status"),
        "task_ids": ids,
        "collection": collection,
        "ok": not problems,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--repo", default=str(Path(__file__).resolve().parent.parent),
                   help="完整仓库根目录（默认取脚本所在 scripts/ 的上一级）")
    p.add_argument("--run-news", action="store_true", help="真实运行 fetch_news")
    p.add_argument("--run-api", action="store_true", help="调用 POST /v1/query")
    p.add_argument("--query", default="Kazakhstan port construction customs payment")
    p.add_argument("--timespan", default="24h")
    p.add_argument("--news-out", default="data/raw_news_live.json")
    p.add_argument("--news-timeout", type=int, default=180)
    p.add_argument("--skip-gdelt", action="store_true",
                   help="跳过 GDELT（当出口 IP 被限流时，只跑 RSS 降级链路）")
    p.add_argument("--gdelt-retries", type=int, default=2,
                   help="验收时 GDELT 重试上限（默认 2；仓库默认 8 不受影响）")
    p.add_argument("--api-url", default="http://127.0.0.1:8000/v1/query")
    p.add_argument("--org-id", default="owner")
    p.add_argument("--user-id", default="local-user")
    p.add_argument("--api-timeout", type=int, default=120)
    p.add_argument("--evidence", default=None, help="可选：把该 JSON 作为 evidence  POST 给 API")
    p.add_argument("--report", default=None, help="可选：把结果写入 JSON 报告")
    args = p.parse_args()

    if not (args.run_news or args.run_api):
        p.print_help()
        raise SystemExit("请至少指定 --run-news 或 --run-api")

    repo = Path(args.repo).resolve()
    check_env(repo)
    report: dict[str, Any] = {"query": args.query, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")}

    if args.run_news:
        report["news"] = run_news(repo, args.query, args.timespan, args.news_out,
                                  args.news_timeout, args.skip_gdelt, args.gdelt_retries)
    if args.run_api:
        report["api"] = run_api(args.api_url, args.query, args.org_id, args.user_id,
                                args.api_timeout, args.evidence)

    ok = all(v.get("ok") for v in report.values() if isinstance(v, dict) and "ok" in v)
    report["overall_ok"] = ok
    log("RESULT", "PASS" if ok else "FAIL")
    if args.report:
        Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        log("RESULT", f"报告已写入 {args.report}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
