"""CLI command: reverse logged operations and restore files to original locations."""

from typing import Optional
import typer
from rich.console import Console
from rich.table import Table

from organizer.operations.rollback import RollbackManager
from organizer.storage.repository import Repository

console = Console()


def rollback(
    last: Optional[int] = typer.Option(None, "--last", "-n", help="Roll back the most recent N operations"),
    operation_id: Optional[int] = typer.Option(None, "--operation-id", "-id", help="Roll back a specific operation by ID"),
    all_ops: bool = typer.Option(False, "--all", help="Roll back ALL completed operations"),
    db: str = typer.Option("data/organizer.db", "--db", help="Path to SQLite database file"),
) -> None:
    """Reverse logged operations, moving files back to their original location. Marks each operation rolled_back."""
    if last is None and operation_id is None and not all_ops:
        console.print("[bold red]Error:[/] You must specify one of [yellow]--last N[/], [yellow]--operation-id ID[/], or [yellow]--all[/].")
        raise typer.Exit(code=1)

    repo = Repository(db)
    manager = RollbackManager(repo)

    results = manager.rollback_batch(
        last_n=last,
        operation_id=operation_id,
        all_completed=all_ops,
    )

    if not results:
        console.print("[yellow]No matching completed operations found to roll back.[/]")
        return

    table = Table(title=f"Rollback Results ({len(results)} operations)", show_lines=True)
    table.add_column("Op ID", justify="right", style="dim")
    table.add_column("Original Source", style="cyan", overflow="fold")
    table.add_column("Status", justify="center")
    table.add_column("Details", style="dim", overflow="fold")

    success_count = 0
    fail_count = 0

    for res in results:
        status_styled = "[bold green]RESTORED[/]" if res.success else "[bold red]FAILED[/]"
        if res.success:
            success_count += 1
        else:
            fail_count += 1

        table.add_row(
            str(res.operation.id or "-"),
            res.operation.source_path,
            status_styled,
            res.message,
        )

    console.print(table)
    console.print(
        f"[bold]Rollback completed:[/] [green]{success_count} restored[/], [red]{fail_count} failed[/]."
    )
