"""CLI command: approve pending organization proposals (alias to review)."""

from typing import Optional
import typer

from cli.commands.review import review


def approve(
    all_proposals: bool = typer.Option(
        False, "--all", help="Approve and execute all pending proposals without prompting"
    ),
    approve_category: Optional[str] = typer.Option(
        None, "--approve-category", help="Bulk approve all proposals matching a specific category"
    ),
    approve_range: Optional[str] = typer.Option(
        None, "--approve-range", help="Bulk approve a range of proposals by display ID (e.g. '1-15')"
    ),
    filter_category: Optional[str] = typer.Option(
        None, "--filter-category", help="Filter pending proposals by category"
    ),
    page_size: int = typer.Option(
        20, "--page-size", help="Number of proposals to display per page (default: 20)"
    ),
    interactive: bool = typer.Option(
        False, "--interactive", help="Prompt for each proposal (default when bulk flags omitted)"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview proposed moves without modifying files or database"
    ),
    db: str = typer.Option("data/organizer.db", "--db", help="Path to SQLite database file"),
) -> None:
    """Review and approve pending organization proposals."""
    review(
        all_proposals=all_proposals,
        approve_category=approve_category,
        approve_range=approve_range,
        filter_category=filter_category,
        page_size=page_size,
        interactive=interactive,
        dry_run=dry_run,
        db=db,
    )
