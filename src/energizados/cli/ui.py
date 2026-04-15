from typing import Optional

from rich.console import Console
from rich.logging import RichHandler
from rich.rule import Rule

# Standard console for output
console = Console()
# Error console that writes to stderr
err_console = Console(stderr=True)

# Global reference to RichHandler for level management
rich_handler: Optional[RichHandler] = None


def set_rich_handler(handler: Optional[RichHandler]) -> None:
    """Store reference to the active RichHandler for level management."""
    global rich_handler
    rich_handler = handler


def print_success(msg: str):
    console.print(f"[bold green]✓[/] {msg}")


def print_error(msg: str):
    err_console.print(f"[bold red]✗[/] {msg}")


def print_info(msg: str):
    console.print(f"[bold cyan]⚡[/] {msg}")


def print_step(msg: str):
    console.print(f"[dim]→[/] {msg}")


def print_header(title: str):
    console.print(Rule(f"[bold]{title}[/]", style="cyan"))


def print_warning(msg: str):
    console.print(f"[bold yellow]⚠[/] {msg}")
