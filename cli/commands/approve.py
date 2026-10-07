"""CLI command: review, approve, edit, or reject pending organization proposals."""

from pathlib import Path
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt

from organizer.feedback.recorder import FeedbackRecorder
from organizer.operations.mover import FileMover
from organizer.storage.repository import Repository

console = Console()


def approve(
    all_proposals: bool = typer.Option(
        False, "--all", help="Approve and execute all pending proposals without prompting"
    ),
    interactive: bool = typer.Option(
        False, "--interactive", help="Prompt for each proposal (default when --all is omitted)"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview proposed moves without modifying files or database"
    ),
    db: str = typer.Option("data/organizer.db", "--db", help="Path to SQLite database file"),
) -> None:
    """Walk pending proposals. Interactive by default: accept / reject / edit destination.
    
    On accept, execute move immediately and log operation. On reject, record feedback.
    --dry-run previews without writing or moving anything.
    """
    if all_proposals and interactive:
        console.print("[red]Error: Cannot use both --all and --interactive.[/]")
        raise typer.Exit(1)

    repo = Repository(db)
    pending = repo.get_pending_proposals()

    if not pending:
        console.print("[green]No pending proposals found to review.[/]")
        return

    # Dry-run preview mode
    if dry_run:
        console.print(f"[bold yellow]DRY-RUN PREVIEW:[/] {len(pending)} pending proposal(s)")
        table = Table(title="Pending Move Proposals (Preview Only)", show_lines=True)
        table.add_column("ID", justify="right", style="dim")
        table.add_column("Source", style="cyan", overflow="fold")
        table.add_column("Category", style="magenta")
        table.add_column("Proposed Destination", style="green", overflow="fold")
        table.add_column("Conf", justify="right", style="yellow")
        table.add_column("Rationale", style="dim", overflow="fold")

        for p in pending:
            table.add_row(
                str(p.id or "-"),
                p.source_path,
                p.proposed_category,
                p.proposed_destination,
                f"{p.confidence:.2f}",
                p.rationale,
            )

        console.print(table)
        console.print("[bold yellow]Dry-run complete. No files moved, no database changes committed.[/]")
        return

    mover = FileMover(repo)
    recorder = FeedbackRecorder(repo)

    # Approve all mode
    if all_proposals:
        console.print(f"[bold cyan]Auto-approving {len(pending)} proposal(s)...[/]")
        success_count = 0
        fail_count = 0

        for p in pending:
            success, op, err = mover.execute_move(p)
            if success:
                recorder.record_decision(p, action="approved")
                success_count += 1
                console.print(f"[green][OK] Moved:[/] {Path(p.source_path).name} -> {p.proposed_destination}")
            else:
                fail_count += 1
                console.print(f"[red][FAIL] Failed to move:[/] {p.source_path} ({err})")

        console.print(
            f"[bold]Batch execution finished:[/] [green]{success_count} succeeded[/], [red]{fail_count} failed[/]."
        )
        return

    # Interactive mode (default when --all is False)
    console.print(f"[bold cyan]Reviewing {len(pending)} pending proposal(s) interactively...[/]\n")

    executed_count = 0
    rejected_count = 0

    for idx, p in enumerate(pending, start=1):
        content = (
            f"[bold]Source:[/] {p.source_path}\n"
            f"[bold]Proposed Category:[/] [magenta]{p.proposed_category}[/]\n"
            f"[bold]Proposed Destination:[/] [green]{p.proposed_destination}[/]\n"
            f"[bold]Confidence:[/] [yellow]{p.confidence:.2f}[/]\n"
            f"[bold]Rationale:[/] {p.rationale}"
        )
        console.print(Panel(content, title=f"Proposal {idx} of {len(pending)} (ID #{p.id})", expand=False))

        choice = Prompt.ask(
            "Action",
            choices=["y", "n", "e", "q"],
            default="y",
            show_choices=True,
        ).lower().strip()

        if choice == "y":
            success, op, err = mover.execute_move(p)
            if success:
                recorder.record_decision(p, action="approved")
                executed_count += 1
                console.print(f"[green][OK] Successfully moved to:[/] {op.destination_path if op else p.proposed_destination}\n")
            else:
                console.print(f"[red][FAIL] Move failed:[/] {err}\n")

        elif choice == "n":
            if not p.id:
                return
            repo.update_proposal_status(p.id, "rejected")
            recorder.record_decision(p, action="rejected")
            rejected_count += 1
            console.print("[yellow]Proposal rejected (recorded in feedback).[/]\n")

        elif choice == "e":
            new_dest = Prompt.ask("Enter custom destination path", default=p.proposed_destination).strip()
            success, op, err = mover.execute_move(p, explicit_destination=new_dest)
            if success:
                recorder.record_decision(
                    p,
                    action="modified",
                    actual_destination=new_dest,
                )
                executed_count += 1
                console.print(f"[green][OK] Successfully moved to custom destination:[/] {new_dest}\n")
            else:
                console.print(f"[red][FAIL] Move failed:[/] {err}\n")

        elif choice == "q":
            console.print("[dim]Review session ended by user.[/]")
            break

    console.print(
        f"[bold]Session summary:[/] [green]{executed_count} executed[/], [yellow]{rejected_count} rejected[/]."
    )
