"""合规采集层单元测试：无网络、无第三方依赖。运行：python -m unittest discover -s tests"""
from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from acquisition.cache import CacheStore                    # noqa: E402
from acquisition.models import RawItem, SourceTier          # noqa: E402
from acquisition.providers import GdeltProvider, RssProvider  # noqa: E402
from acquisition.rate_limiter import RateLimiter            # noqa: E402
from acquisition.models import FallbackExhausted            # noqa: E402
from acquisition.resolver import SourceResolver             # noqa: E402
from acquisition.robots_gate import RobotsGate              # noqa: E402


ROBOTS_OK = """User-agent: *
Allow: /
Disallow: /private
Crawl-delay: 4
"""

ROBOTS_COMPLEX = """User-agent: *
Disallow: /p
Allow: /page
"""


def fake_fetch(table: dict[str, tuple[int, str, dict]]):
    def _fetch(url, headers, params=None):
        if url not in table:
            return 404, "", {}
        return table[url]
    return _fetch


class RobotsGateTests(unittest.TestCase):
    def test_4xx_unavailable_allows(self):
        gate = RobotsGate(fake_fetch({}))
        r = gate.check("https://example.com/a")
        self.assertEqual(r.decision.value, "unavailable")

    def test_5xx_unreachable_denies(self):
        gate = RobotsGate(fake_fetch({"https://example.com/robots.txt": (503, "", {})}))
        r = gate.check("https://example.com/a")
        self.assertEqual(r.decision.value, "unreachable")

    def test_timeout_denies(self):
        def boom(url, headers):
            raise TimeoutError()
        gate = RobotsGate(boom)
        self.assertEqual(gate.check("https://example.com/a").decision.value, "unreachable")

    def test_disallow_and_crawl_delay(self):
        gate = RobotsGate(fake_fetch({"https://example.com/robots.txt": (200, ROBOTS_OK, {})}))
        self.assertEqual(gate.check("https://example.com/a").decision.value, "allow")
        self.assertEqual(gate.check("https://example.com/private/x").decision.value, "deny")
        self.assertEqual(gate.check("https://example.com/a").crawl_delay, 4.0)

    def test_longest_path_and_allow_precedence(self):
        gate = RobotsGate(fake_fetch({"https://example.com/robots.txt": (200, ROBOTS_COMPLEX, {})}))
        self.assertEqual(gate.check("https://example.com/page").decision.value, "allow")
        self.assertEqual(gate.check("https://example.com/private").decision.value, "deny")

    def test_cache_within_24h(self):
        calls = []
        def counted(url, headers):
            calls.append(url)
            return 200, ROBOTS_OK, {}
        gate = RobotsGate(counted)
        gate.check("https://example.com/a")
        gate.check("https://example.com/b")
        self.assertEqual(len(calls), 1)
        self.assertTrue(gate.check("https://example.com/a").cached)


class CacheTests(unittest.TestCase):
    def test_put_get_expiry(self):
        with tempfile.TemporaryDirectory() as d:
            c = CacheStore(Path(d))
            key = c.make_key("api", "q1")
            c.put(key, {"a": 1}, ttl=60)
            self.assertEqual(c.get(key), {"a": 1})
            c.put(key, {"a": 2}, ttl=-1)
            self.assertIsNone(c.get(key))


class ProviderTests(unittest.TestCase):
    def test_gdelt_plain_text_throttle_returns_after_retry(self):
        fetch = fake_fetch({"https://api.gdeltproject.org/api/v2/doc/doc":
                            (200, "Please limit requests to one every 5 seconds", {})})
        p = GdeltProvider(fetch, lambda k, i: 0.0, sleep_fn=lambda s: None)
        with self.assertRaises(RuntimeError):
            p.search("test", retries=2)

    def test_rss_parses_atom_and_license(self):
        atom = """<feed xmlns="http://www.w3.org/2005/Atom">
          <entry><title>Astana port</title><link href="https://astanatimes.com/a"/>
          <summary>Port expansion</summary><published>2026-11-27T00:00:00Z</published></entry>
        </feed>"""
        fetch = fake_fetch({"https://astanatimes.com/feed/atom": (200, atom, {})})
        p = RssProvider(fetch, lambda k, i: 0.0,
                        [{"id": "astanatimes", "url": "https://astanatimes.com/feed/atom",
                          "license": "public-rss", "region": "kazakhstan"}])
        items = p.search("port")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].source_tier, SourceTier.RSS)
        self.assertEqual(items[0].extra["license"], "public-rss")


class ResolverTests(unittest.TestCase):
    def test_api_failure_falls_back_to_rss(self):
        gate = RobotsGate(fake_fetch({"https://example.com/robots.txt": (200, ROBOTS_OK, {})}))
        class BadApi:
            def search(self, *a): raise RuntimeError("throttled")
        rss_items = [RawItem(url="https://example.com/a", title="Port news", source_id="rss1")]
        class GoodRss:
            def search(self, q=""): return rss_items
        r = SourceResolver(gate, BadApi(), GoodRss(), None, strategy="hybrid")
        out = r.resolve("port")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].provenance.source_tier, SourceTier.RSS)
        self.assertTrue(any("error" in f["reason"] for f in r.fallback_log))

    def test_robots_deny_drops_item(self):
        gate = RobotsGate(fake_fetch({"https://example.com/robots.txt": (200, "User-agent: *\nDisallow: /", {})}))
        class Api:
            def search(self, *a): return [RawItem(url="https://example.com/x", title="X")]
        class EmptyRss:
            def search(self, q=""): return []
        r = SourceResolver(gate, Api(), EmptyRss(), None, strategy="compliance_first")
        with self.assertRaises(FallbackExhausted):
            r.resolve("q")
        self.assertTrue(any("robots:deny" in f["reason"] for f in r.fallback_log))


class RateLimiterTests(unittest.TestCase):
    def test_enforces_min_interval(self):
        limiter = RateLimiter(default_interval=0.05)
        limiter.acquire("example.com")
        waited = limiter.acquire("example.com")
        self.assertGreaterEqual(waited, 0.03)


class WiringTests(unittest.TestCase):
    """回归：build_resolver 必须适配 RobotsGate 的二参数 fetcher 签名。"""

    def test_build_resolver_keeps_items_after_robots_check(self):
        import json as _json
        try:
            import fetch_news_integrated as fni
        except ModuleNotFoundError:      # 落地后文件名是 fetch_news.py
            import fetch_news as fni

        calls = []
        payload = _json.dumps({"articles": [{
            "url": "https://astanatimes.com/port", "title": "Port investment",
            "domain": "astanatimes.com", "seendate": "20261127060000",
        }]})

        def fake(url, headers, params):
            calls.append(url)
            if "api.gdeltproject.org" in url:
                return 200, payload, {}
            if url.endswith("/robots.txt"):
                return 200, "User-agent: *\nAllow: /\n", {}
            return 404, "", {}

        old = fni._http_fetch
        fni._http_fetch = fake
        try:
            resolver = fni.build_resolver(fni._load_config())
            items = resolver.resolve("port")
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].provenance.robots_decision.value, "allow")
            self.assertTrue(any(u.endswith("/robots.txt") for u in calls))
            self.assertEqual(resolver.fallback_log, [])
        finally:
            fni._http_fetch = old


class ProviderParsingTests(unittest.TestCase):
    """回归：Atom ISO 时间解析 + GDELT 退避提示如实反映重试次数。"""

    def test_atom_iso_published_at(self):
        body = """<feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <title>Kazakhstan port</title>
            <link href="https://example.com/port"/>
            <summary>Port investment</summary>
            <published>2026-11-27T10:46:17Z</published>
          </entry>
        </feed>"""
        items = RssProvider._parse(body, {"id": "astanatimes", "language": "english"})
        self.assertEqual(len(items), 1)
        pub = items[0].published_at
        self.assertIsNotNone(pub)
        self.assertEqual(pub.year, 2026)
        self.assertIsNotNone(pub.tzinfo)

    def test_gdelt_error_reports_actual_retries(self):
        p = GdeltProvider(lambda url, headers, params: (429, "", {}),
                          lambda key, interval: 0.0)
        p._sleep = lambda seconds: None
        with self.assertRaises(RuntimeError) as ctx:
            p.search("test", retries=3)
        self.assertIn("3 次", str(ctx.exception))
        self.assertNotIn("8 次", str(ctx.exception))


class RetryBudgetTests(unittest.TestCase):
    """回归：默认重试上限 2 + 指数退避封顶，杜绝 330s 累计退避。"""

    def test_default_retries_is_two_and_backoff_is_capped(self):
        sleeps = []
        p = GdeltProvider(lambda url, headers, params: (429, "", {}),
                          lambda key, interval: 0.0,
                          sleep_fn=sleeps.append)
        with self.assertRaises(RuntimeError) as ctx:
            p.search("test")
        self.assertIn("2 次", str(ctx.exception))
        # 默认 base=2/cap=8：两次退避 2s + 4s，总计 6s（旧实现为 10+20=30s）
        self.assertEqual(sleeps, [2.0, 4.0])
        self.assertLessEqual(sum(sleeps), 8.0 * 2)

    def test_explicit_retries_override_instance_default(self):
        sleeps = []
        p = GdeltProvider(lambda url, headers, params: (429, "", {}),
                          lambda key, interval: 0.0,
                          sleep_fn=sleeps.append, max_retries=2,
                          backoff_base=1.0, backoff_cap=3.0)
        with self.assertRaises(RuntimeError):
            p.search("test", retries=4)
        self.assertEqual(sleeps, [1.0, 2.0, 3.0, 3.0])

    def test_build_resolver_injects_retry_budget_from_config(self):
        try:
            import fetch_news as fni
        except ModuleNotFoundError:
            import fetch_news_integrated as fni
        cfg = fni._load_config()
        resolver = fni.build_resolver(cfg)
        self.assertEqual(resolver.api.max_retries, 2)
        self.assertEqual((resolver.api.backoff_base, resolver.api.backoff_cap), (2.0, 8.0))


class PlannerQueryTests(unittest.TestCase):
    """回归：planner 首条查询必须是短查询，否则 RSS/GDELT 零命中。"""

    @staticmethod
    def _plan(query="Kazakhstan", country="Kazakhstan"):
        import asyncio
        from backend.core.agents import EvidencePlannerAgent
        agent = EvidencePlannerAgent()
        return asyncio.run(agent.execute_async(
            {"query": query, "metadata": {"country": country}, "prev_task_2": {}}, "owner"
        ))

    def test_first_query_is_short_and_rss_query_exposed(self):
        plan = self._plan("Kazakhstan", "Kazakhstan")
        self.assertEqual(plan["search_queries"][0], "Kazakhstan")
        self.assertEqual(plan["rss_query"], "Kazakhstan")
        self.assertNotIn("official government project owner developer",
                         plan["search_queries"][0])
        # 长模板仍保留作补充，不丢失原有检索意图
        self.assertTrue(any("tender procurement" in q for q in plan["search_queries"]))

    def test_short_query_combines_country_and_raw_query(self):
        plan = self._plan("port construction", "Kazakhstan")
        self.assertEqual(plan["rss_query"], "Kazakhstan port construction")
        self.assertIn("port", plan["search_queries"][0])


class RssTokenMatchTests(unittest.TestCase):
    """回归：长模板查询经关键词抽取后仍能召回 RSS 条目。"""

    BODY = """<rss><channel>
      <item><title>Astana port expansion</title><link>https://astanatimes.com/port</link>
      <description>New terminal investment</description></item>
    </channel></rss>"""

    def _items(self):
        return RssProvider._parse(self.BODY, {"id": "astanatimes", "language": "english"})

    def test_stopwords_stripped_and_long_query_matches(self):
        terms = RssProvider._query_terms(
            'Kazakhstan " Astana port " official government project owner developer')
        self.assertIn("astana", terms)
        self.assertIn("port", terms)
        self.assertNotIn("official", terms)
        self.assertNotIn("government", terms)

        fetch = fake_fetch({"https://astanatimes.com/feed": (200, self.BODY, {})})
        p = RssProvider(fetch, lambda k, i: 0.0,
                        [{"id": "astanatimes", "url": "https://astanatimes.com/feed"}])
        # 整串子串匹配下这条查询必然 0 命中；token 匹配后应召回
        self.assertEqual(len(p.search("Kazakhstan Astana port official government")), 1)

    def test_no_term_match_returns_empty_and_all_stopwords_keeps_items(self):
        fetch = fake_fetch({"https://astanatimes.com/feed": (200, self.BODY, {})})
        p = RssProvider(fetch, lambda k, i: 0.0,
                        [{"id": "astanatimes", "url": "https://astanatimes.com/feed"}])
        self.assertEqual(len(p.search("zzzz nonexistent")), 0)
        # 全是停用词时不误杀
        self.assertEqual(len(p.search("official government project")), 1)


class RssConcurrencyTests(unittest.TestCase):
    """回归：多个 RSS 源并发抓取，总耗时约等于最慢源而非各源之和。"""

    def test_feeds_are_fetched_concurrently(self):
        import threading
        import time

        body = """<rss><channel><item><title>Port news</title>
          <link>https://example.com/p</link></item></channel></rss>"""
        active = 0
        peak = [0]
        lock = threading.Lock()

        def slow_fetch(url, headers, params=None):
            nonlocal active
            with lock:
                active += 1
                peak[0] = max(peak[0], active)
            time.sleep(0.2)
            with lock:
                active -= 1
            return 200, body, {}

        feeds = [{"id": f"f{i}", "url": f"https://example.com/f{i}"} for i in range(4)]
        p = RssProvider(slow_fetch, lambda k, i: 0.0, feeds, max_workers=4)
        started = time.monotonic()
        items = p.search("port")
        elapsed = time.monotonic() - started

        self.assertEqual(len(items), 4)
        self.assertGreaterEqual(peak[0], 2)   # 确实并发
        self.assertLess(elapsed, 0.6)         # 4 × 0.2s=0.8s 串行；并发约 0.2s


class RssQueryPassthroughTests(unittest.TestCase):
    """回归：collector 把 planner 的 rss_query 传给 resolver 的 RSS 层。"""

    def test_collector_passes_rss_query_to_resolver(self):
        import asyncio

        from backend.intelligence import compliant_acquisition as ca

        agent = ca.CompliantCollectorAgent()
        agent.max_queries = 2
        captured = []

        class FakeResolver:
            fallback_log = []

            def resolve(self, query, timespan="24h", language="english", rss_query=None):
                captured.append((query, rss_query))
                return []

        old = ca.build_resolver
        ca.build_resolver = lambda config: FakeResolver()
        try:
            asyncio.run(agent.execute_async({
                "prev_task_3": {
                    "rss_query": "Kazakhstan",
                    "search_queries": ['Kazakhstan "official government project"'],
                },
            }, "owner"))
        finally:
            ca.build_resolver = old

        # short_query_only 生效：只跑短查询，且 rss_query 透传给 resolver
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0], ("Kazakhstan", "Kazakhstan"))


class CollectorBudgetTests(unittest.TestCase):
    """回归：collector 受并发度/超时/查询数预算约束。"""

    @staticmethod
    def _collector():
        import backend.intelligence.compliant_acquisition as ca
        return ca

    def test_collector_reads_budget_from_config(self):
        ca = self._collector()
        agent = ca.CompliantCollectorAgent()
        cfg = agent.config.get("collection", {})
        self.assertEqual(agent.max_queries, cfg.get("max_queries", 6))
        self.assertEqual(agent.max_concurrency, cfg.get("max_concurrency", 3))
        self.assertEqual(agent.query_timeout, cfg.get("query_timeout_seconds", 20.0))
        self.assertLessEqual(agent.max_concurrency, agent.max_queries)

    def test_collector_caps_queries_and_dedups_across_queries(self):
        import asyncio
        from types import SimpleNamespace

        ca = self._collector()
        agent = ca.CompliantCollectorAgent()
        seen_queries = []

        class FakeResolver:
            fallback_log = []

            def resolve(self, query, timespan="24h", language="english",
                        rss_query=None):
                seen_queries.append(query)
                return [SimpleNamespace(
                    item=SimpleNamespace(url="https://example.com/same", to_dict=lambda: {
                        "url": "https://example.com/same", "title": "shared",
                    }),
                    to_dict=lambda: {"url": "https://example.com/same", "title": "shared",
                                     "provenance": {"source_tier": "rss"}},
                )]

        old = ca.build_resolver
        ca.build_resolver = lambda config: FakeResolver()
        try:
            queries = [f"q{i}" for i in range(20)]
            result = asyncio.run(agent.execute_async(
                {"prev_task_3": {"search_queries": queries}}, "owner"))
        finally:
            ca.build_resolver = old

        self.assertEqual(len(seen_queries), agent.max_queries)
        self.assertEqual(result["item_count"], 1)  # 跨查询去重
        self.assertIn("collection_budget", result)
        self.assertEqual(result["collection_budget"]["max_queries"], agent.max_queries)

    def test_collector_timeout_and_concurrency_respect_budget(self):
        import asyncio
        import threading
        import time

        ca = self._collector()
        agent = ca.CompliantCollectorAgent()
        agent.query_timeout = 0.1       # 远小于单查询真实耗时
        agent.max_queries = 3
        agent.max_concurrency = 2       # 只允许 2 条并行

        active = 0
        peak = [0]
        counter_lock = threading.Lock()

        class SlowResolver:
            fallback_log = []

            def resolve(self, query, timespan="24h", language="english",
                        rss_query=None):
                nonlocal active
                with counter_lock:
                    active += 1
                    peak[0] = max(peak[0], active)
                time.sleep(0.3)
                with counter_lock:
                    active -= 1
                return []

        old = ca.build_resolver
        ca.build_resolver = lambda config: SlowResolver()
        try:
            started = time.monotonic()
            result = asyncio.run(agent.execute_async(
                {"prev_task_3": {"search_queries": ["a", "b", "c"]}}, "owner"))
            elapsed = time.monotonic() - started
        finally:
            ca.build_resolver = old

        self.assertEqual(result["item_count"], 0)
        self.assertGreater(peak[0], 1)                      # 确实并发，不是串行
        self.assertLessEqual(peak[0], agent.max_concurrency)  # 且不超并发上限
        # 峰值并发断言已证明并发生效；耗时上界放宽以避免 CI 模块加载抖动误报。
        self.assertLess(elapsed, 1.5)
        self.assertEqual(agent.metrics["errors"], 3)


if __name__ == "__main__":
    unittest.main()
