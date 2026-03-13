from rich.console import Console
from rich.rule import Rule

# Standard console for output
console = Console()
# Error console that writes to stderr
err_console = Console(stderr=True)


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
