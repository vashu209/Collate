"""CLI command: scan directory and store file records with metadata in SQLite."""

from pathlib import Path
import typer
from rich.console import Console

from organizer.scanning.scanner import scan_directory
from organizer.storage.repository import Repository

console = Console()


def scan(
    path: str = typer.Argument(..., help="Path of the directory to scan"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", help="Whether to scan subdirectories recursively"),
    db: str = typer.Option("data/organizer.db", "--db", help="Path to SQLite database file"),
) -> None:
    """Walk <path>, extract metadata and SHA-256 checksums, and store file records in SQLite."""
    target_dir = Path(path).expanduser().resolve()
    if not target_dir.exists() or not target_dir.is_dir():
        console.print(f"[bold red]Error:[/] Target path does not exist or is not a directory: {target_dir}")
        raise typer.Exit(code=1)

    repo = Repository(db)
    console.print(f"[bold cyan]Scanning directory:[/] {target_dir}")
    console.print(f"Mode: {'Recursive' if recursive else 'Non-recursive'} | Database: {db}")

    scanned_count = 0
    with console.status("[bold green]Scanning filesystem and hashing contents...[/]") as status:
        for record in scan_directory(target_dir, recursive=recursive):
            repo.upsert_file(record)
            scanned_count += 1
            if scanned_count % 50 == 0:
                status.update(f"[bold green]Processed {scanned_count} files...[/]")

    console.print(f"[bold green]Scan complete![/] Successfully cataloged [bold]{scanned_count}[/] file(s).")
