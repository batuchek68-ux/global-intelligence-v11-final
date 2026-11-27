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


if __name__ == "__main__":
    unittest.main()
