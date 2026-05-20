"""Terminal formatter — beautiful console output for screenshots."""

import logging
from datetime import datetime
from typing import List, Dict, Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich import box
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.syntax import Syntax
from rich.rule import Rule
from rich.align import Align

from .fetcher import FetchResult
from .summarizer import NewsSummarizer

logger = logging.getLogger(__name__)


class TerminalFormatter:
    """Beautiful terminal output for screenshots and runtime logs."""

    def __init__(self, verbose: bool = True):
        self.console = Console(color_system="truecolor", width=100)
        self.verbose = verbose
        self._log_buffer: List[str] = []

    def print_banner(self):
        """Agent-IntelHub startup banner."""
        banner = Text("""
    ╔══════════════════════════════════════════════════════════╗
    ║              █████╗  ██╗ ███╗   ██╗████████╗             ║
    ║             ██╔══██╗ ██║ ████╗  ██║╚══██╔══╝             ║
    ║             ███████║ ██║ ██╔██╗ ██║   ██║                ║
    ║             ██╔══██║ ██║ ██║╚██╗██║   ██║                ║
    ║             ██║  ██║ ██║ ██║ ╚████║   ██║                ║
    ║             ╚═╝  ╚═╝ ╚═╝ ╚═╝  ╚═══╝   ╚═╝                ║
    ║                                                          ║
    ║          🤖  AI-Powered Intelligence Hub                 ║
    ║          📡  Multi-source · LLM-driven · Real-time        ║
    ╚══════════════════════════════════════════════════════════╝
        """, style="bold cyan")
        self.console.print(banner)
        self.console.print(f"    启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", style="dim white")
        self.console.print(f"    推理引擎: DeepSeek Chat (DeepSeek V4)", style="dim white")
        self.console.print()

    def print_workflow_start(self):
        """Print the start of a workflow run."""
        self.console.print(Rule(style="dim"))
        self.console.print()
        title = Text(" 🚀 工作流启动 ", style="bold white on blue")
        self.console.print(Align.center(title))
        self.console.print()

    def print_workflow_step(self, step: int, total: int, name: str, status: str = ""):
        """Print a workflow step."""
        step_text = Text()
        step_text.append(f"  ├─ [{step}/{total}] ", style="bold cyan")
        step_text.append(name, style="white")
        if status:
            step_text.append(f" {status}", style="green")
        self.console.print(step_text)

    def print_workflow_done(self, step: int, total: int, name: str, detail: str = "✅"):
        """Print a completed workflow step."""
        step_text = Text()
        step_text.append(f"  ├─ [{step}/{total}] ", style="bold cyan")
        step_text.append(name, style="white")
        step_text.append(f"  {detail}", style="green")
        self.console.print(step_text)

    def print_fetch_results(self, results: List[FetchResult]):
        """Print fetch results in a nice table."""
        table = Table(
            title="📡 信息源抓取报告",
            title_style="bold cyan",
            box=box.ROUNDED,
            border_style="blue",
        )
        table.add_column("类别", style="cyan", width=14)
        table.add_column("来源", style="white")
        table.add_column("条数", justify="right", width=6)
        table.add_column("耗时", justify="right", width=8)
        table.add_column("状态", width=8)

        for result in results:
            source_count = len(result.items)
            errors = result.errors
            status = "✅" if not errors else f"⚠️  {len(errors)} err"
            
            # Highlight Xiaomi category
            label_style = "bold red" if result.category == "xiaomi" else "white"
            
            sources = list(set(item.source_name for item in result.items))
            sources_str = ", ".join(sources[:3])
            if len(sources) > 3:
                sources_str += f" +{len(sources)-3}"

            table.add_row(
                f"[{label_style}]{result.category_label}[/]",
                sources_str,
                str(source_count),
                f"{result.elapsed_ms}ms",
                status,
            )

        self.console.print()
        self.console.print(table)
        self.console.print()

    def print_llm_reasoning(self, summaries: List[dict]):
        """Print LLM reasoning traces (important for screenshot credibility)."""
        self.console.print(Rule(style="dim"))
        self.console.print()
        self.console.print(Align.center(Text(" 🧠 LLM 长链推理过程 ", style="bold white on magenta")))

        total_tokens = sum(s.get("tokens_used", 0) for s in summaries)

        for s in summaries:
            label = s["category_label"]
            tokens = s.get("tokens_used", 0)
            
            panel = Panel(
                Text(f"📝 {label}\n\n{s['summary']}", style="white"),
                title=f"[bold magenta]推理消耗: {tokens} tokens[/]",
                border_style="magenta",
                box=box.HEAVY,
                padding=(1, 2),
            )
            self.console.print(panel)
            self.console.print()

        # Token total highlight
        if total_tokens > 0:
            total_text = Text()
            total_text.append(f"\n  💰 Token 总消耗: ", style="bold yellow")
            total_text.append(f"{total_tokens:,}", style="bold red")
            total_text.append(f" tokens", style="bold yellow")
            self.console.print(Align.center(total_text))
            self.console.print()

    def print_delivery(self, channel: str, status: str, content_preview: str = ""):
        """Print delivery status."""
        icon = "📤" if "✅" in status else "⚠️"
        text = Text()
        text.append(f"\n  {icon} 推送至 {channel}: ", style="bold cyan")
        text.append(status, style="bold green" if "✅" in status else "yellow")
        self.console.print(text)
        if content_preview:
            self.console.print(f"     └─ {content_preview[:80]}", style="dim white")

    def print_workflow_end(self, elapsed: float, total_tokens: int, item_count: int):
        """Print workflow completion summary."""
        self.console.print()
        self.console.print(Rule(style="dim"))
        self.console.print()
        
        summary = Table(box=box.DOUBLE_EDGE, border_style="green")
        summary.add_column("指标", style="bold green", width=18)
        summary.add_column("数值", style="white")
        
        summary.add_row("⏱ 总运行耗时", f"{elapsed:.1f}s")
        summary.add_row("📄 处理新闻数", f"{item_count} 条")
        summary.add_row("💰 Token 总消耗", f"{total_tokens:,} tokens")
        summary.add_row("🤖 推理引擎", "DeepSeek Chat V4")
        summary.add_row("⏰ 完成时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        
        self.console.print(Align.center(summary))
        self.console.print()

    def print_error(self, msg: str):
        """Print an error message."""
        self.console.print(f"  ✗ [bold red]Error:[/] {msg}")

    def print_step_header(self, num: int, label: str):
        """Print a step header during workflow."""
        self.console.print(f"\n  [Step {num}/4] [bold cyan]{label}[/]")
