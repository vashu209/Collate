"""CLI command: list exact duplicates found via content hash (SHA-256)."""

from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table

from organizer.storage.repository import Repository

console = Console()


def duplicates(
    path: Optional[str] = typer.Argument(None, help="Optional directory path prefix to filter duplicates"),
    db: str = typer.Option("data/organizer.db", "--db", help="Path to SQLite database file"),
) -> None:
    """List exact duplicates found via content hash (SHA-256). Read-only."""
    repo = Repository(db)
    prefix = str(Path(path).expanduser().resolve()) if path else None
    duplicate_groups = repo.get_duplicates(path_prefix=prefix)

    if not duplicate_groups:
        console.print("[green]No duplicate files detected in scanned records.[/]")
        return

    total_dup_files = sum(len(group) for group in duplicate_groups.values())
    console.print(
        f"[bold yellow]Found {len(duplicate_groups)} duplicate group(s) across {total_dup_files} files.[/]\n"
    )

    table = Table(title="Exact Duplicates (SHA-256)", show_lines=True)
    table.add_column("Group", justify="right", style="dim")
    table.add_column("SHA-256 Hash", style="cyan", no_wrap=True)
    table.add_column("Count", justify="right", style="yellow")
    table.add_column("Duplicate File Paths", style="white", overflow="fold")

    for idx, (h, file_records) in enumerate(duplicate_groups.items(), start=1):
        paths_str = "\n".join(r.path for r in file_records)
        table.add_row(str(idx), h[:16] + "...", str(len(file_records)), paths_str)

    console.print(table)
