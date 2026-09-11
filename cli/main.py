"""Main Typer CLI entrypoint registering all organizer subcommands."""

import typer

from cli.commands.approve import approve
from cli.commands.duplicates import duplicates
from cli.commands.propose import propose
from cli.commands.rollback import rollback
from cli.commands.scan import scan
from cli.commands.status import status

app = typer.Typer(
    name="organizer",
    help="AI-Powered Intelligent File System Organizer (Phase 1: Rule-Based)",
    add_completion=False,
    no_args_is_help=True,
)

# Register subcommands
app.command(name="scan", help="Scan a directory and record file metadata in SQLite.")(scan)
app.command(name="propose", help="Generate organization proposals using rules engine.")(propose)
app.command(name="approve", help="Review, approve, or reject pending file move proposals.")(approve)
app.command(name="rollback", help="Reverse completed move operations and restore files.")(rollback)
app.command(name="duplicates", help="Find exact duplicate files based on content hash.")(duplicates)
app.command(name="status", help="Display overview counts for files, proposals, and operations.")(status)


if __name__ == "__main__":
    app()
