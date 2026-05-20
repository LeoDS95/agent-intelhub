"""Notifier — push formatted reports to Telegram (and QQ via OpenClaw hook)."""

import logging
import json
from typing import List, Optional

import requests

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Send formatted messages to Telegram Bot API."""

    def __init__(self, config: dict):
        push_cfg = config.get("push", {}).get("telegram", {})
        self.bot_token = push_cfg.get("bot_token", "")
        self.chat_id = push_cfg.get("chat_id", "")
        self.enabled = push_cfg.get("enabled", False) and bool(self.bot_token) and bool(self.chat_id)
        self.api_base = f"https://api.telegram.org/bot{self.bot_token}"

        # Apply proxy to Telegram requests if configured
        proxy_cfg = config.get("proxy", {})
        self.proxies = None
        if proxy_cfg.get("enabled", True):
            http_proxy = proxy_cfg.get("http", "") or proxy_cfg.get("https", "")
            https_proxy = proxy_cfg.get("https", "") or proxy_cfg.get("http", "")
            if http_proxy or https_proxy:
                self.proxies = {
                    "http": http_proxy or https_proxy,
                    "https": https_proxy or http_proxy,
                }

    def send_summary_report(self, summaries: List[dict], total_tokens: int) -> dict:
        """Send a well-formatted summary report to Telegram."""
        if not self.enabled:
            return {"status": "skipped", "reason": "Telegram notifier disabled or not configured"}

        message = self._build_report(summaries, total_tokens)
        
        try:
            resp = requests.post(
                f"{self.api_base}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                proxies=self.proxies,
                timeout=15,
            )
            resp.raise_for_status()
            result = resp.json()
            logger.info(f"  ✅ Telegram 推送成功 (message_id: {result.get('result', {}).get('message_id', '?')})")
            return {"status": "success", "data": result}
        except Exception as e:
            logger.warning(f"  ⚠️ Telegram 推送失败: {e}")
            return {"status": "failed", "error": str(e)}

    def _build_report(self, summaries: List[dict], total_tokens: int) -> str:
        """Build a Telegram HTML message from summaries."""
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        lines = [f"<b>📡 Agent-IntelHub 日报</b>\n🕐 {now}\n{'-' * 30}\n"]

        for s in summaries:
            label = s["category_label"]
            summary_text = s.get("summary", "")
            items = s.get("items", [])

            # Category header
            cat_emoji = "🔴" if s["category"] == "xiaomi" else "📌"
            lines.append(f"\n<b>{cat_emoji} {label}</b>")

            # Summary content
            lines.append(summary_text[:800])  # Truncate for Telegram

            # Source links
            if items:
                links = []
                for item in items[:3]:
                    title = item.get("title", "")
                    url = item.get("url", "")
                    if url:
                        links.append(f'• <a href="{url}">{title[:40]}</a>')
                    else:
                        links.append(f"• {title[:40]}")
                lines.append("\n" + "\n".join(links))

        # Footer
        lines.append(f"\n{'-' * 30}")
        lines.append(f"🤖 <i>Agent-IntelHub · 消耗 {total_tokens:,} tokens · DeepSeek V4</i>")

        return "\n".join(lines)


class QQNotifier:
    """Placeholder for QQ push via OpenClaw message tools.
    
    In production, this is handled by OpenClaw's cron announce feature
    or the qqbot-channel skill for direct QQ channel posting.
    """

    def __init__(self, config: dict):
        self.enabled = False  # QQ push handled via OpenClaw cron

    def send(self, message: str) -> dict:
        return {"status": "skipped", "note": "QQ push handled via OpenClaw cron"}
