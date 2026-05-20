#!/usr/bin/env python3
"""
Agent-IntelHub: AI-Powered Intelligence Aggregation & Daily Briefing System.

Main entry point. Orchestrates:
  1. Multi-source news fetching (RSS + Web)
  2. LLM-powered summarization (DeepSeek API)
  3. Beautiful terminal output (for screenshots)
  4. Telegram/QQ push notification

Usage:
    python main.py                    # Run once (full workflow)
    python main.py --dry-run          # Fetch + print only, no push
    python main.py --config custom.yaml
"""

import os
import sys
import time
import logging
import argparse
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.fetcher import NewsFetcher
from src.summarizer import NewsSummarizer
from src.formatter import TerminalFormatter
from src.notifier import TelegramNotifier, QQNotifier

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("agent-intelhub")


# ---------------------------------------------------------------------------
# Configuration loader
# ---------------------------------------------------------------------------
def load_config(config_path: str = "config.yaml") -> dict:
    """Load YAML config and resolve environment variable references."""
    path = Path(config_path)
    if not path.exists():
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()

    # Resolve ${VAR:-default} patterns
    import re

    def _resolve_env(match):
        expr = match.group(1)
        if ":-" in expr:
            var, default = expr.split(":-", 1)
            return os.environ.get(var, default)
        return os.environ.get(expr, "")

    resolved = re.sub(r"\$\{([^}]+)\}", _resolve_env, raw)
    config = yaml.safe_load(resolved)
    return config


# ---------------------------------------------------------------------------
# Main Orchestrator
# ---------------------------------------------------------------------------
class IntelHubAgent:
    """Main orchestrator for the intelligence aggregation pipeline."""

    def __init__(self, config_path: str = "config.yaml", dry_run: bool = False):
        self.config = load_config(config_path)
        self.dry_run = dry_run
        self.formatter = TerminalFormatter(
            verbose=self.config.get("runtime", {}).get("verbose_screenshots", True)
        )

        # Initialize modules
        proxy_cfg = self.config.get("proxy", {})
        self.fetcher = NewsFetcher(self.config, proxy=proxy_cfg)
        self.summarizer = NewsSummarizer(self.config)
        self.telegram = TelegramNotifier(self.config)
        self.qq = QQNotifier(self.config)

    def run(self):
        """Execute the full pipeline."""
        start_time = time.time()

        # ── BANNER ──
        self.formatter.print_banner()
        self.formatter.print_workflow_start()

        # ════════════════════════════════════════════
        # STEP 1: Fetch news from all sources
        # ════════════════════════════════════════════
        self.formatter.print_step_header(1, "多源情报抓取")
        logger.info("🔍 Starting multi-source news fetch...")

        sources_cfg = self.config.get("sources", {})
        fetch_results = self.fetcher.fetch_all(sources_cfg)

        total_items = sum(len(r.items) for r in fetch_results)
        self.formatter.print_fetch_results(fetch_results)
        logger.info(f"📊 Total: {total_items} articles from {len(fetch_results)} categories")

        if total_items == 0:
            self.formatter.print_error("No articles fetched from any source.")
            return

        # ════════════════════════════════════════════
        # STEP 2: LLM Summarization
        # ════════════════════════════════════════════
        max_batch = self.config.get("runtime", {}).get("max_summary_batch", 15)
        self.formatter.print_step_header(2, "LLM 智能推理与摘要")
        logger.info(f"🧠 Starting LLM summarization (max {max_batch} per category)...")

        summaries = self.summarizer.summarize(fetch_results, max_batch=max_batch)
        total_tokens = self.summarizer.count_tokens_in_summaries(summaries)

        self.formatter.print_llm_reasoning(summaries)
        logger.info(f"💰 Total tokens consumed: {total_tokens:,}")

        # ════════════════════════════════════════════
        # STEP 3: Push Notification
        # ════════════════════════════════════════════
        if not self.dry_run:
            self.formatter.print_step_header(3, "多端推送")
            logger.info("📤 Pushing summaries...")

            # Telegram
            tg_result = self.telegram.send_summary_report(summaries, total_tokens)
            logger.info(f"  Telegram: {tg_result['status']}")
            self.formatter.print_delivery(
                "Telegram",
                f"✅ 推送成功" if tg_result["status"] == "success" else f"⚠️ {tg_result.get('reason', tg_result.get('error', 'unknown'))}",
            )

            # QQ (via OpenClaw cron — handled externally)
            self.formatter.print_delivery(
                "QQ (OpenClaw)",
                "⏸️ 由 OpenClaw cron 调度推送",
            )
        else:
            self.formatter.print_step_header(3, "推送 (Dry-Run 模式 — 跳过)")
            logger.info("⏭️ Dry-run mode: skipping push notifications")

        # ════════════════════════════════════════════
        # STEP 4: Completion
        # ════════════════════════════════════════════
        elapsed = time.time() - start_time
        self.formatter.print_step_header(4, "工作流完成")
        self.formatter.print_workflow_end(elapsed, total_tokens, total_items)
        logger.info(f"✅ Workflow complete in {elapsed:.1f}s ({total_tokens:,} tokens)")

        # Return metrics for cron scheduling
        return {
            "status": "success",
            "elapsed_s": round(elapsed, 1),
            "items": total_items,
            "tokens": total_tokens,
        }


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Agent-IntelHub: AI-powered news intelligence & daily briefing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                          # Full workflow
  python main.py --dry-run                # Fetch + analyze, no push
  python main.py --config myconfig.yaml   # Custom config
        """,
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to YAML config file (default: config.yaml)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip push notifications (fetch + analyze only)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="Agent-IntelHub v1.0.0",
    )

    args = parser.parse_args()

    # Load .env file
    load_dotenv()

    # Run
    agent = IntelHubAgent(config_path=args.config, dry_run=args.dry_run)
    result = agent.run()
    
    return result


if __name__ == "__main__":
    main()
