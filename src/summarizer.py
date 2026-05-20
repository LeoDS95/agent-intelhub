"""LLM-powered news summarizer — uses raw urllib to bypass Windows encoding bugs."""

import json
import logging
from typing import List, Optional
from urllib import request as urllib_request
from urllib.error import URLError

from .fetcher import NewsItem, FetchResult

logger = logging.getLogger(__name__)


class NewsSummarizer:
    """Summarize news articles using LLM (DeepSeek/SiliconFlow API)."""

    def __init__(self, config: dict):
        llm_cfg = config.get("llm", {})
        self.api_key = llm_cfg.get("api_key", "")
        self.api_base = llm_cfg.get("api_base", "https://api.deepseek.com/v1")
        self.model = llm_cfg.get("model", "deepseek-chat")
        self.max_tokens = llm_cfg.get("max_tokens", 1024)
        self.temperature = llm_cfg.get("temperature", 0.3)
        self.verbose = config.get("runtime", {}).get("verbose_screenshots", True)
        self.prompts_cfg = config.get("prompts", {})

    def summarize(self, results: List[FetchResult], max_batch: int = 15) -> List[dict]:
        summaries = []
        for result in results:
            if not result.items:
                summaries.append({
                    "category": result.category,
                    "category_label": result.category_label,
                    "summary": "\u6682\u65e0\u65b0\u5185\u5bb9",
                    "items": [],
                    "tokens_used": 0,
                })
                continue
            batch = result.items[:max_batch]
            if self.verbose:
                logger.info(f"  \u2514\u2500 LLM reasoning ({len(batch)} items, model: {self.model})...")
            category_summary, tokens = self._summarize_category(result.category_label, batch)
            summaries.append({
                "category": result.category,
                "category_label": result.category_label,
                "summary": category_summary,
                "items": [{"title": item.title, "url": item.url, "source": item.source_name} for item in batch],
                "tokens_used": tokens,
            })
        return summaries

    def _summarize_category(self, category_label: str, items: List[NewsItem]) -> tuple:
        content_lines = []
        for i, item in enumerate(items, 1):
            # Remove problematic unicode chars before building prompt
            safe_title = item.title.encode("ascii", errors="replace").decode("ascii")
            safe_summary = item.summary.encode("ascii", errors="replace").decode("ascii")[:200]
            content_lines.append(f"{i}. [{item.source_name}] {safe_title}\n   URL: {item.url}\n   Summary: {safe_summary}\n")
        content_text = "\n".join(content_lines)

        prompt_template = self.prompts_cfg.get("summarization",
            "Summarize the following {n} news items concisely in Chinese. Format: Title -> one-line summary.")
        prompt = prompt_template.format(n=len(items), content=content_text)

        try:
            return self._call_llm_api(prompt, category_label)
        except Exception as e:
            logger.warning(f"  LLM API failed: {e}")
            fallback = "\n".join(f"\u00ab{item.title}\u00bb ({item.source_name})" for item in items[:5])
            return f"[LLM API Error] {fallback}", 0

    def _call_llm_api(self, prompt: str, category: str) -> tuple:
        """Call LLM API using raw urllib (no requests/httpx dependencies)."""
        url = f"{self.api_base.rstrip('/')}/chat/completions"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a professional intelligence analyst."},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }

        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")

        req = urllib_request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib_request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except URLError as e:
            # Try to read error body
            if hasattr(e, 'read') and callable(e.read):
                error_body = e.read().decode('utf-8', errors='replace')
                logger.warning(f"  API error response: {error_body[:200]}")
            raise

        summary = data["choices"][0]["message"]["content"].strip()
        usage = data.get("usage", {})
        tokens_used = usage.get("total_tokens", usage.get("completion_tokens", 0))

        return summary, tokens_used

    def count_tokens_in_summaries(self, summaries: List[dict]) -> int:
        return sum(s.get("tokens_used", 0) for s in summaries)
