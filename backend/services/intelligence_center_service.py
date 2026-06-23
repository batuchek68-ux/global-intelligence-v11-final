from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from backend.services.audit_service import append_audit


BACKEND_ROOT = Path(__file__).resolve().parents[1]
MEMORY_DIR = BACKEND_ROOT / "memory" / "intelligence"
BRIEF_DIR = BACKEND_ROOT / "reports" / "intelligence_briefs"
VIDEO_DIR = BACKEND_ROOT / "reports" / "video_center"
KEYWORD_BANK = MEMORY_DIR / "keyword_bank.json"

INTELLIGENCE_TAXONOMY = {
    "project_pipeline": {
        "label": "Project pipeline",
        "signals": ["planned project", "under construction", "tender", "EPC", "project owner", "developer"],
    },
    "political_impact": {
        "label": "Political and policy impact",
        "signals": ["government policy", "election", "cabinet", "sanctions", "public hearing", "regulation"],
    },
    "investment_value": {
        "label": "High value and high return",
        "signals": ["investment project", "financing", "ROI", "PPP", "industrial park", "special economic zone"],
    },
    "growth_sector": {
        "label": "Growth sectors",
        "signals": ["renewable energy", "mining", "logistics", "AI", "data center", "infrastructure"],
    },
    "procurement_trade": {
        "label": "Procurement and trade",
        "signals": ["public tender", "procurement", "supplier", "customs", "tariff", "local partner"],
    },
    "risk_compliance": {
        "label": "Risk and compliance",
        "signals": ["sanctions", "export control", "payment risk", "contract dispute", "customs risk"],
    },
    "forums_social": {
        "label": "Forums, chats, and social attention",
        "signals": ["forum", "telegram", "reddit", "wechat", "qq group", "linkedin", "facebook"],
    },
    "video_intelligence": {
        "label": "Video intelligence and production",
        "signals": ["YouTube", "TikTok", "Douyin", "video channel", "short video", "case video"],
    },
    "research_library": {
        "label": "Research and library",
        "signals": ["paper", "dataset", "library", "think tank", "feasibility study", "EIA report"],
    },
}

COUNTRY_VIDEO_STYLE_CUES = {
    "kazakhstan": ["wide steppe opening", "industrial rail logistics", "bilingual Chinese/Russian captions", "government-project visual proof"],
    "uzbekistan": ["silk road trade angle", "industrial park visuals", "fast-moving market narration"],
    "russia": ["engineering depth", "heavy industry scenes", "Yandex and VK trend references"],
    "china": ["supply-chain speed", "factory proof", "Douyin rhythm", "WeChat Video Channel trust style"],
    "middle east": ["infrastructure ambition", "investment forum tone", "premium aerial and city visuals"],
    "africa": ["resource corridor", "port and road logistics", "local employment and development narrative"],
}

PLATFORMS = {
    "government": ["site:gov", "site:gov.kz", "site:gov.uz", "site:primeminister.kz", "site:invest.gov.kz"],
    "procurement": ["tender", "procurement", "EPC", "contract awarded", "public procurement"],
    "forums": ["site:reddit.com", "site:quora.com", "site:vc.ru", "forum", "discussion"],
    "chatrooms": ["site:t.me", "Telegram channel", "Discord", "QQ group", "WeChat group"],
    "social": ["site:linkedin.com", "site:x.com", "site:facebook.com", "site:vk.com", "site:toutiao.com"],
    "video": ["site:youtube.com", "site:tiktok.com", "site:douyin.com", "site:bilibili.com", "site:ixigua.com"],
    "academic": ["site:scholar.google.com", "site:semanticscholar.org", "site:researchgate.net", "feasibility study", "EIA"],
    "library": ["site:openlibrary.org", "site:worldcat.org", "report pdf", "white paper"],
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _stable_id(*parts: str) -> str:
    raw = "|".join(str(part).strip().lower() for part in parts if part)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _keyword_bank_path() -> Path:
    override = os.getenv("V11_KEYWORD_BANK_PATH")
    return Path(override) if override else KEYWORD_BANK


def _brief_dir() -> Path:
    override = os.getenv("V11_INTELLIGENCE_BRIEF_DIR")
    return Path(override) if override else BRIEF_DIR


def _video_dir() -> Path:
    override = os.getenv("V11_VIDEO_CENTER_DIR")
    return Path(override) if override else VIDEO_DIR


def _search_url(engine: str, query: str) -> str:
    encoded = quote_plus(query)
    if engine == "yandex":
        return f"https://yandex.com/search/?text={encoded}"
    if engine == "youtube":
        return f"https://www.youtube.com/results?search_query={encoded}"
    if engine == "tiktok":
        return f"https://www.tiktok.com/search?q={encoded}"
    if engine == "douyin":
        return f"https://www.douyin.com/search/{encoded}"
    return f"https://www.google.com/search?q={encoded}"


def _as_list(value: Any, fallback: list[str]) -> list[str]:
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        return items or fallback
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return fallback


def build_intelligence_search_system(
    topics: list[str] | str,
    countries: list[str] | str | None = None,
    industries: list[str] | str | None = None,
) -> dict[str, Any]:
    topic_list = _as_list(topics, ["international engineering trade"])
    country_list = _as_list(countries, ["Kazakhstan", "Central Asia"])
    industry_list = _as_list(industries, ["infrastructure", "mining", "logistics", "energy"])

    categories = []
    for key, spec in INTELLIGENCE_TAXONOMY.items():
        terms: list[str] = []
        queries: list[dict[str, Any]] = []
        for topic in topic_list:
            for country in country_list:
                for industry in industry_list[:4]:
                    for signal in spec["signals"][:6]:
                        term = f"{country} {industry} {topic} {signal}"
                        terms.append(term)
        for term in terms[:18]:
            for source_name, source_terms in PLATFORMS.items():
                source_query = f"{term} {source_terms[0]}"
                queries.append(
                    {
                        "source_group": source_name,
                        "query": source_query,
                        "urls": {
                            "google": _search_url("google", source_query),
                            "yandex": _search_url("yandex", source_query),
                        },
                    }
                )
        categories.append(
            {
                "id": key,
                "label": spec["label"],
                "search_terms": terms[:36],
                "queries": queries[:40],
                "tracking_frequency": "daily; high-risk political and tender signals should be checked more often",
                "score_focus": ["value", "growth", "return_potential", "political_impact", "attention", "project_relevance"],
            }
        )

    return {
        "ok": True,
        "created_at": _now_iso(),
        "topics": topic_list,
        "countries": country_list,
        "industries": industry_list,
        "categories": categories,
        "source_groups": PLATFORMS,
        "rules": [
            "Government, procurement, and official company sources outrank social media.",
            "Forums, chats, and social sites are attention signals, not final proof.",
            "Video trends may guide content style, but scripts remain drafts until human approval.",
            "Political and sanctions signals must be escalated before outreach or commitments.",
        ],
    }


def score_intelligence_item(item: dict[str, Any]) -> dict[str, Any]:
    text = " ".join(str(item.get(field, "")) for field in ("title", "summary", "snippet", "content")).lower()
    weights = {
        "value": ["billion", "million", "investment", "financing", "ppp", "industrial park"],
        "growth": ["growth", "expansion", "new market", "planned", "pipeline", "capacity"],
        "return_potential": ["roi", "high return", "margin", "concession", "long-term contract"],
        "political_impact": ["government", "policy", "minister", "sanction", "election", "regulation"],
        "attention": ["viral", "trending", "views", "forum", "telegram", "youtube", "tiktok", "douyin"],
        "project_relevance": ["tender", "epc", "contract", "construction", "developer", "project owner"],
    }
    scores = {}
    for name, keywords in weights.items():
        hits = [keyword for keyword in keywords if keyword in text]
        base = min(100, 35 + len(hits) * 15)
        scores[name] = {"score": base if hits else 25, "hits": hits}
    total = round(sum(value["score"] for value in scores.values()) / len(scores))
    if item.get("source_type") in {"government", "procurement", "official"}:
        total = min(100, total + 12)
    if item.get("source_type") in {"forum", "chat", "social", "video"}:
        total = min(100, total + 5)
    return {"overall_score": total, "dimensions": scores}


def classify_intelligence_items(items: list[dict[str, Any]]) -> dict[str, Any]:
    buckets = {
        "high_value": [],
        "high_growth": [],
        "high_return": [],
        "political_impact": [],
        "high_attention": [],
        "project_critical": [],
        "watchlist": [],
    }
    for item in items:
        scored = dict(item)
        scored["score"] = score_intelligence_item(item)
        dimensions = scored["score"]["dimensions"]
        if dimensions["value"]["score"] >= 50:
            buckets["high_value"].append(scored)
        if dimensions["growth"]["score"] >= 50:
            buckets["high_growth"].append(scored)
        if dimensions["return_potential"]["score"] >= 50:
            buckets["high_return"].append(scored)
        if dimensions["political_impact"]["score"] >= 50:
            buckets["political_impact"].append(scored)
        if dimensions["attention"]["score"] >= 50:
            buckets["high_attention"].append(scored)
        if dimensions["project_relevance"]["score"] >= 50:
            buckets["project_critical"].append(scored)
        if scored["score"]["overall_score"] >= 50:
            buckets["watchlist"].append(scored)
    for key in buckets:
        buckets[key] = sorted(buckets[key], key=lambda row: row["score"]["overall_score"], reverse=True)[:20]
    return {"ok": True, "created_at": _now_iso(), "buckets": buckets}


def read_keyword_bank(path: Path | None = None) -> dict[str, Any]:
    target = path or _keyword_bank_path()
    if not target.exists():
        return {"ok": True, "path": str(target), "data": {"keywords": [], "updated_at": None}}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = {"keywords": [], "updated_at": None}
    return {"ok": True, "path": str(target), "data": data}


def update_keyword_bank(system: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    target = path or _keyword_bank_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    existing = read_keyword_bank(target)["data"].get("keywords", [])
    by_key = {item["keyword"]: item for item in existing if isinstance(item, dict) and item.get("keyword")}
    for category in system.get("categories", []):
        for keyword in category.get("search_terms", [])[:18]:
            by_key[keyword] = {
                "keyword": keyword,
                "category": category["id"],
                "label": category["label"],
                "updated_at": _now_iso(),
            }
    data = {"updated_at": _now_iso(), "keywords": sorted(by_key.values(), key=lambda row: row["keyword"])[:600]}
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "path": str(target), "count": len(data["keywords"])}


def generate_intelligence_brief(
    topics: list[str] | str,
    countries: list[str] | str | None = None,
    industries: list[str] | str | None = None,
    items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    system = build_intelligence_search_system(topics, countries, industries)
    classified = classify_intelligence_items(items or [])
    update_keyword_bank(system)
    brief_dir = _brief_dir()
    brief_dir.mkdir(parents=True, exist_ok=True)
    path = brief_dir / f"{_today_key()}.md"
    lines = [
        f"# Daily Intelligence Brief - {_today_key()}",
        "",
        "DRAFT - internal intelligence, not approved for external sending",
        "",
        "## Focus",
        "",
        f"- Topics: {', '.join(system['topics'])}",
        f"- Countries: {', '.join(system['countries'])}",
        f"- Industries: {', '.join(system['industries'])}",
        "",
        "## Priority Categories",
        "",
    ]
    for category in system["categories"]:
        lines.append(f"- {category['label']}: {category['search_terms'][0] if category['search_terms'] else ''}")
    lines.extend(["", "## High Attention / High Value Watchlist", ""])
    watchlist = classified["buckets"]["watchlist"]
    if watchlist:
        for item in watchlist[:10]:
            lines.append(f"- {item.get('title', 'Untitled')} | score={item['score']['overall_score']} | {item.get('url', '')}")
    else:
        lines.append("- No evidence items attached yet. Use generated search URLs to collect sources.")
    lines.extend(
        [
            "",
            "## Operating Rules",
            "",
            "- Government and procurement evidence must confirm project facts.",
            "- Political, sanctions, contract, payment, and public outreach matters require human approval.",
            "- Forum/chat/social/video signals are used for attention and content direction, not as final proof.",
        ]
    )
    content = "\n".join(lines) + "\n"
    path.write_text(content, encoding="utf-8")
    append_audit(
        "INTELLIGENCE_BRIEF_GENERATED",
        "DONE",
        f"Generated daily intelligence brief for topics={','.join(system['topics'])}; external sending blocked.",
        confidence=90,
        risk="MEDIUM",
    )
    return {"ok": True, "path": str(path), "content": content, "search_system": system, "classified": classified}


def build_video_production_center(
    topics: list[str] | str,
    countries: list[str] | str | None = None,
    industries: list[str] | str | None = None,
) -> dict[str, Any]:
    topic_list = _as_list(topics, ["engineering trade project"])
    country_list = _as_list(countries, ["Kazakhstan"])
    industry_list = _as_list(industries, ["infrastructure"])
    video_keywords = []
    platform_searches = []
    for country in country_list:
        style_key = country.lower()
        style = COUNTRY_VIDEO_STYLE_CUES.get(style_key, COUNTRY_VIDEO_STYLE_CUES.get("middle east"))
        for topic in topic_list:
            for industry in industry_list:
                for intent in ["case study", "project progress", "factory proof", "investment brief", "risk explanation", "country style"]:
                    keyword = f"{country} {industry} {topic} {intent} short video"
                    video_keywords.append({"keyword": keyword, "style_cues": style})
                    platform_searches.extend(
                        [
                            {"platform": "YouTube", "keyword": keyword, "url": _search_url("youtube", keyword)},
                            {"platform": "TikTok", "keyword": keyword, "url": _search_url("tiktok", keyword)},
                            {"platform": "Douyin", "keyword": keyword, "url": _search_url("douyin", keyword)},
                            {"platform": "Google Video", "keyword": keyword, "url": _search_url("google", f"{keyword} video")},
                        ]
                    )
    script_templates = [
        {
            "name": "60-second project opportunity brief",
            "structure": ["hook with country/project fact", "official evidence screenshot", "market pain point", "solution path", "approval-safe call to discuss internally"],
        },
        {
            "name": "risk explanation video",
            "structure": ["risk event", "why it matters", "what to verify", "human approval boundary", "next research task"],
        },
        {
            "name": "country-style market explainer",
            "structure": ["local visual style", "trade corridor", "project pipeline", "partner profile", "draft-only close"],
        },
    ]
    video_dir = _video_dir()
    video_dir.mkdir(parents=True, exist_ok=True)
    path = video_dir / f"video_center_{_today_key()}.json"
    data = {
        "ok": True,
        "created_at": _now_iso(),
        "topics": topic_list,
        "countries": country_list,
        "industries": industry_list,
        "video_keywords": video_keywords[:80],
        "platform_searches": platform_searches[:120],
        "script_templates": script_templates,
        "rules": [
            "Video drafts are internal until human approval.",
            "Track leading videos to improve pacing, proof style, captions, and country-specific visual language.",
            "Do not copy third-party scripts, footage, trademarks, or misleading claims.",
        ],
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    append_audit(
        "VIDEO_PRODUCTION_CENTER_UPDATED",
        "DONE",
        f"Updated video keyword and production center for topics={','.join(topic_list)}.",
        confidence=90,
        risk="LOW",
    )
    return data | {"path": str(path)}
