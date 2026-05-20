"""News fetcher: RSS feed parsing + web scraping."""

import time
import logging
import re
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, field

import feedparser
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class NewsItem:
    """A single news article."""
    title: str
    url: str
    summary: str = ""
    source_name: str = ""
    source_category: str = ""
    published: Optional[datetime] = None
    raw_content: str = ""


@dataclass
class FetchResult:
    """Result of fetching from one source category."""
    category: str
    category_label: str
    items: List[NewsItem] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    elapsed_ms: float = 0.0


class NewsFetcher:
    """Multi-source news fetcher with RSS and web scraping support."""

    def __init__(self, config: dict, proxy: Optional[dict] = None):
        self.config = config
        self.proxy = proxy or {}
        self.session = self._build_session()

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })
        if self.proxy.get("enabled", True):
            http_proxy = self.proxy.get("http", "") or self.proxy.get("https", "")
            https_proxy = self.proxy.get("https", "") or self.proxy.get("http", "")
            if http_proxy or https_proxy:
                session.proxies = {
                    "http": http_proxy or https_proxy,
                    "https": https_proxy or http_proxy,
                }
                logger.info(f"\U0001f504 Proxy enabled: {http_proxy or https_proxy}")
        return session

    def fetch_all(self, config_sources: dict) -> List[FetchResult]:
        """Fetch from all configured source categories."""
        results = []
        for category_key, category_cfg in config_sources.items():
            if not category_cfg.get("enabled", True):
                continue
            result = self._fetch_category(category_key, category_cfg)
            results.append(result)
        return results

    def _fetch_category(self, category_key: str, category_cfg: dict) -> FetchResult:
        label = category_cfg.get("name", category_key)
        max_items = category_cfg.get("items_per_run", 5)
        result = FetchResult(category=category_key, category_label=label)
        start = time.time()
        all_items = []

        for feed_cfg in category_cfg.get("feeds", []):
            feed_name = feed_cfg.get("name", "Unknown")
            feed_url = feed_cfg.get("url", "")
            feed_type = feed_cfg.get("type", "rss")
            try:
                if feed_type == "rss":
                    items = self._fetch_rss(feed_url, feed_name, category_key)
                elif feed_type == "hn_search":
                    items = self._fetch_hn_search(feed_url, feed_name, category_key)
                elif feed_type == "web":
                    items = self._fetch_web(feed_url, feed_name, category_key)
                else:
                    continue
                logger.info(f"  {feed_name}: {len(items)} items")
                all_items.extend(items)
            except Exception as e:
                err_msg = f"{feed_name}: {str(e)[:80]}"
                logger.warning(err_msg)
                result.errors.append(err_msg)

        seen_urls = set()
        for item in all_items:
            if item.url and item.url not in seen_urls:
                seen_urls.add(item.url)
                result.items.append(item)
                if len(result.items) >= max_items:
                    break

        result.elapsed_ms = round((time.time() - start) * 1000, 1)
        return result

    def _fetch_rss(self, url: str, source_name: str, category: str) -> List[NewsItem]:
        resp = self.session.get(url, timeout=30)
        resp.raise_for_status()
        try:
            text = resp.content.decode("utf-8")
        except UnicodeDecodeError:
            text = resp.content.decode("gbk", errors="replace")
        # Fix encoding for characters that cause API issues later
        text = text.encode("utf-8", errors="replace").decode("utf-8")

        feed = feedparser.parse(text)
        items = []
        for entry in feed.entries[:10]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "")
            summary = ""
            if hasattr(entry, "summary"):
                summary = BeautifulSoup(entry.summary, "html.parser").get_text(separator=" ", strip=True)
            elif hasattr(entry, "description"):
                summary = BeautifulSoup(entry.description, "html.parser").get_text(separator=" ", strip=True)
            published = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published = datetime(*entry.published_parsed[:6])
                except Exception:
                    pass
            if title:
                items.append(NewsItem(
                    title=title,
                    url=link,
                    summary=summary[:300],
                    source_name=source_name,
                    source_category=category,
                    published=published,
                    raw_content=summary,
                ))
        return items

    def _fetch_hn_search(self, query: str, source_name: str, category: str) -> List[NewsItem]:
        """Search Hacker News via Algolia API (always works, no rate limits for light usage)."""
        url = f"https://hn.algolia.com/api/v1/search?query={query}&tags=story&hitsPerPage=10"
        resp = self.session.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        items = []
        for hit in data.get("hits", []):
            title = hit.get("title", "").strip()
            link = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"
            points = hit.get("points", 0)
            author = hit.get("author", "")
            story_text = hit.get("story_text", "") or ""
            summary = f"[{points} points by {author}] {BeautifulSoup(story_text, 'html.parser').get_text(separator=' ', strip=True)[:200]}" if story_text else f"[{points} points by {author}]"
            if title:
                items.append(NewsItem(
                    title=title,
                    url=link,
                    summary=summary[:300],
                    source_name=f"HN/{query}",
                    source_category=category,
                    raw_content=summary,
                ))
        return items

    def _fetch_web(self, url: str, source_name: str, category: str) -> List[NewsItem]:
        resp = self.session.get(url, timeout=30)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding
        soup = BeautifulSoup(resp.text, "lxml")
        items = []
        for tag in soup.select("article, .post, .item, li, h2 a, h3 a, .title a")[:10]:
            link_tag = tag if tag.name == "a" else tag.find("a")
            if not link_tag:
                continue
            href = link_tag.get("href", "")
            title = link_tag.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            if href.startswith("/"):
                from urllib.parse import urljoin
                href = urljoin(url, href)
            items.append(NewsItem(
                title=title,
                url=href,
                source_name=source_name,
                source_category=category,
            ))
        return items
