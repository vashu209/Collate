"""CLI command: display summary statistics of files, proposals, operations, and feedback."""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from organizer.storage.repository import Repository

console = Console()


def status(
    db: str = typer.Option("data/organizer.db", "--db", help="Path to SQLite database file"),
) -> None:
    """Show summary counts: files scanned, proposals pending/approved/rejected, operations completed/rolled back."""
    repo = Repository(db)
    summary = repo.get_status_summary()

    table = Table(title="Autonomous File Organizer - System Status", show_header=True)
    table.add_column("Category", style="cyan", no_wrap=True)
    table.add_column("Metric", style="white")
    table.add_column("Count", justify="right", style="green")

    table.add_row("Scanned Files", "Total Files in Catalog", str(summary["total_files_scanned"]))
    table.add_section()
    table.add_row("Proposals", "Pending Review", str(summary["proposals_pending"]))
    table.add_row("Proposals", "Approved", str(summary["proposals_approved"]))
    table.add_row("Proposals", "Rejected", str(summary["proposals_rejected"]))
    table.add_row("Proposals", "Executed Moves", str(summary["proposals_executed"]))
    table.add_section()
    table.add_row("Operations", "Completed", str(summary["operations_completed"]))
    table.add_row("Operations", "Rolled Back", str(summary["operations_rolled_back"]))
    table.add_row("Operations", "Failed", str(summary["operations_failed"]))
    table.add_section()
    table.add_row("Feedback Log", "User Corrections / Decisions", str(summary["feedback_records"]))

    console.print(table)
