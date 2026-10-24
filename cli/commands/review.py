"""CLI command: review, approve, edit, skip, or reject organization proposals."""

import math
from pathlib import Path
from typing import Dict, List, Optional, Set
import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from organizer.feedback.recorder import FeedbackRecorder
from organizer.operations.mover import FileMover
from organizer.rules.models import Proposal
from organizer.storage.repository import Repository

console = Console(safe_box=True)


def parse_range(range_str: str, max_val: int) -> List[int]:
    """Parse range string like '1-15', '5', '1,2,5' into 1-based indices.
    
    Args:
        range_str: User supplied range string.
        max_val: Upper bound on valid index.
        
    Returns:
        Sorted list of valid 1-based indices.
        
    Raises:
        ValueError: If range string is malformed or indices are out of range.
    """
    cleaned = range_str.replace(" ", "").strip()
    if not cleaned:
        raise ValueError("Range string cannot be empty.")

    indices: Set[int] = set()
    parts = cleaned.split(",")
    for part in parts:
        if not part:
            continue
        if "-" in part:
            bounds = part.split("-")
            if len(bounds) != 2:
                raise ValueError(f"Invalid range component: '{part}'")
            start, end = int(bounds[0]), int(bounds[1])
            if start > end:
                start, end = end, start
            for i in range(start, end + 1):
                if 1 <= i <= max_val:
                    indices.add(i)
                else:
                    raise ValueError(f"Index {i} is out of bounds (1 to {max_val}).")
        else:
            val = int(part)
            if 1 <= val <= max_val:
                indices.add(val)
            else:
                raise ValueError(f"Index {val} is out of bounds (1 to {max_val}).")

    if not indices:
        raise ValueError(f"No valid indices found in '{range_str}'.")

    return sorted(indices)


def execute_proposal_approval(
    mover: FileMover,
    recorder: FeedbackRecorder,
    proposal: Proposal,
    explicit_dest: Optional[str] = None,
) -> bool:
    """Helper to execute approval of a proposal."""
    success, op, err = mover.execute_move(proposal, explicit_destination=explicit_dest)
    if success:
        action = "modified" if explicit_dest else "approved"
        recorder.record_decision(
            proposal,
            action=action,
            actual_destination=explicit_dest or (op.destination_path if op else None),
        )
        return True
    return False


def review(
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
        False, "--interactive", help="Prompt for review (default when bulk flags omitted)"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview proposed moves without modifying files or database"
    ),
    db: str = typer.Option("data/organizer.db", "--db", help="Path to SQLite database file"),
) -> None:
    """Review, approve, edit, skip, or reject pending organization proposals."""
    repo = Repository(db)
    pending = repo.get_pending_proposals(category=filter_category)

    if not pending:
        if filter_category:
            console.print(f"[yellow]No pending proposals found for category '{filter_category}'.[/]")
        else:
            console.print("[green]No pending proposals found to review.[/]")
        return

    mover = FileMover(repo)
    recorder = FeedbackRecorder(repo)

    # -------------------------------------------------------------------------
    # Bulk Approval by Category
    # -------------------------------------------------------------------------
    if approve_category:
        target_cat = approve_category.strip().lower()
        matching = [p for p in pending if p.proposed_category.lower() == target_cat]

        if not matching:
            console.print(f"[yellow]No pending proposals matched category '{approve_category}'.[/]")
            return

        console.print(f"[bold cyan]Bulk approving {len(matching)} proposal(s) in category '{approve_category}'...[/]")
        success_count = 0
        fail_count = 0

        for p in matching:
            if execute_proposal_approval(mover, recorder, p):
                success_count += 1
                console.print(f"[green][OK] Moved:[/] {Path(p.source_path).name} -> {p.proposed_destination}")
            else:
                fail_count += 1
                console.print(f"[red][FAIL] Failed to move:[/] {p.source_path}")

        console.print(
            f"[bold]Category approval completed:[/] [green]{success_count} succeeded[/], [red]{fail_count} failed[/]."
        )
        return

    # -------------------------------------------------------------------------
    # Bulk Approval by Range
    # -------------------------------------------------------------------------
    if approve_range:
        try:
            target_indices = parse_range(approve_range, len(pending))
        except ValueError as e:
            console.print(f"[bold red]Range error:[/] {e}")
            raise typer.Exit(code=1)

        console.print(f"[bold cyan]Bulk approving {len(target_indices)} proposal(s) from range '{approve_range}'...[/]")
        success_count = 0
        fail_count = 0

        for idx in target_indices:
            p = pending[idx - 1]
            if execute_proposal_approval(mover, recorder, p):
                success_count += 1
                console.print(f"[green][OK] (#{idx}) Moved:[/] {Path(p.source_path).name} -> {p.proposed_destination}")
            else:
                fail_count += 1
                console.print(f"[red][FAIL] (#{idx}) Failed to move:[/] {p.source_path}")

        console.print(
            f"[bold]Range approval completed:[/] [green]{success_count} succeeded[/], [red]{fail_count} failed[/]."
        )
        return

    # -------------------------------------------------------------------------
    # Bulk Approval of All
    # -------------------------------------------------------------------------
    if all_proposals:
        console.print(f"[bold cyan]Auto-approving all {len(pending)} pending proposal(s)...[/]")
        success_count = 0
        fail_count = 0

        for p in pending:
            if execute_proposal_approval(mover, recorder, p):
                success_count += 1
                console.print(f"[green][OK] Moved:[/] {Path(p.source_path).name} -> {p.proposed_destination}")
            else:
                fail_count += 1
                console.print(f"[red][FAIL] Failed to move:[/] {p.source_path}")

        console.print(
            f"[bold]Batch execution finished:[/] [green]{success_count} succeeded[/], [red]{fail_count} failed[/]."
        )
        return

    # -------------------------------------------------------------------------
    # Dry-Run Preview Mode (Paginated)
    # -------------------------------------------------------------------------
    if dry_run:
        console.print(f"[bold yellow]DRY-RUN PREVIEW:[/] {len(pending)} pending proposal(s)")
        total_pages = max(1, math.ceil(len(pending) / page_size))

        for p_num in range(1, total_pages + 1):
            s_idx = (p_num - 1) * page_size
            e_idx = min(s_idx + page_size, len(pending))
            page_slice = pending[s_idx:e_idx]

            table = Table(
                title=f"Pending Move Proposals (Preview - Page {p_num} of {total_pages})",
                show_lines=True,
            )
            table.add_column("Display ID", justify="right", style="cyan", no_wrap=True)
            table.add_column("Source", style="white", overflow="fold")
            table.add_column("Category", style="magenta")
            table.add_column("Proposed Destination", style="green", overflow="fold")
            table.add_column("Conf", justify="right", style="yellow")
            table.add_column("Rationale", style="dim", overflow="fold")

            for disp_idx, p in enumerate(page_slice, start=s_idx + 1):
                table.add_row(
                    str(disp_idx),
                    p.source_path,
                    p.proposed_category,
                    p.proposed_destination,
                    f"{p.confidence:.2f}",
                    p.rationale,
                )

            console.print(table)

        console.print("[bold yellow]Dry-run complete. No files moved, no database changes committed.[/]")
        return

    # -------------------------------------------------------------------------
    # Interactive Paginated Review UI with Live DB Refresh & Back Navigation
    # -------------------------------------------------------------------------
    console.print(f"[bold cyan]Reviewing pending proposal(s) interactively...[/]")
    if filter_category:
        console.print(f"[dim]Category Filter:[/] [magenta]{filter_category}[/]")

    # Track session-specific statistics and skipped proposal IDs
    session_moved_count = 0
    session_rejected_count = 0
    session_skipped_ids: Set[int] = set()

    current_page = 1

    try:
        while True:
            # LIVE DATABASE FETCH: Every render loop pulls the latest state from SQLite
            pending = repo.get_pending_proposals(category=filter_category)
            total_items = len(pending)

            if total_items == 0:
                console.print("[bold green]No pending proposals remaining in database.[/]")
                break

            total_pages = max(1, math.ceil(total_items / page_size))
            if current_page > total_pages:
                current_page = total_pages
            if current_page < 1:
                current_page = 1

            start_idx = (current_page - 1) * page_size
            end_idx = min(start_idx + page_size, total_items)
            page_items = [(idx, pending[idx - 1]) for idx in range(start_idx + 1, end_idx + 1)]

            # Render current page table
            cat_badge = f" [Category: {filter_category}]" if filter_category else ""
            table = Table(
                title=f"Pending Move Proposals - Page {current_page} of {total_pages} (Items {start_idx + 1}-{end_idx} of {total_items}){cat_badge}",
                show_lines=True,
            )
            table.add_column("ID", justify="right", style="cyan", no_wrap=True)
            table.add_column("Status", justify="center", no_wrap=True)
            table.add_column("Source File", style="white", overflow="fold")
            table.add_column("Category", style="magenta")
            table.add_column("Proposed Destination", style="green", overflow="fold")
            table.add_column("Conf", justify="right", style="yellow")

            for disp_idx, p in page_items:
                if p.id in session_skipped_ids:
                    st_styled = "[dim]SKIPPED[/]"
                else:
                    st_styled = "[yellow]PENDING[/]"

                table.add_row(
                    str(disp_idx),
                    st_styled,
                    Path(p.source_path).name,
                    p.proposed_category,
                    p.proposed_destination,
                    f"{p.confidence:.2f}",
                )

            console.print(table)

            # Action bar prompt
            console.print(
                "[bold]Controls:[/] [cyan]y <id|range>[/] approve | [red]n <id|range>[/] reject | [yellow]e <id>[/] edit | [white]v <id>[/] view\n"
                "          [dim]s <id>[/] skip | [dim]sa[/] skip page | [dim]sc[/] skip category | [dim]sr <range>[/] skip range\n"
                "          [white]b[/] back page | [white]n[/] next page | [white]ps <size>[/] page size | [magenta]q[/] quit"
            )

            user_input = Prompt.ask("Action", default="n" if current_page < total_pages else "q").strip()
            cmd_parts = user_input.split(maxsplit=1)
            cmd = cmd_parts[0].lower() if cmd_parts else ""
            arg = cmd_parts[1].strip() if len(cmd_parts) > 1 else ""

            if cmd in ("q", "quit", "exit"):
                console.print("[dim]Review session ended by user.[/]")
                break

            # Backwards navigation: back to previous page
            elif cmd in ("b", "back", "p", "prev", "previous"):
                if current_page > 1:
                    current_page -= 1
                    console.print(f"[dim]Navigating back to Page {current_page}...[/]")
                else:
                    console.print("[yellow]Already on Page 1 (no previous page).[/]")

            # Forward navigation: next page
            elif cmd in ("n", "next") and not arg:
                if current_page < total_pages:
                    current_page += 1
                else:
                    console.print("[yellow]Already on the last page.[/]")

            # Adjust page size
            elif cmd in ("ps", "page-size"):
                try:
                    new_size = int(arg)
                    if new_size > 0:
                        page_size = new_size
                        console.print(f"[green]Page size updated to {page_size}.[/]")
                    else:
                        console.print("[red]Page size must be a positive integer.[/]")
                except ValueError:
                    console.print("[red]Usage: ps <number> (e.g., ps 10)[/]")

            # View / inspect specific proposal in detail with Back option
            elif cmd in ("v", "view", "inspect"):
                try:
                    target_idx = int(arg) if arg else page_items[0][0]
                    if 1 <= target_idx <= total_items:
                        p = pending[target_idx - 1]
                        detail_panel = (
                            f"[bold]ID:[/] #{target_idx} (DB ID: {p.id})\n"
                            f"[bold]Source Path:[/] {p.source_path}\n"
                            f"[bold]Proposed Category:[/] [magenta]{p.proposed_category}[/]\n"
                            f"[bold]Proposed Destination:[/] [green]{p.proposed_destination}[/]\n"
                            f"[bold]Confidence Score:[/] [yellow]{p.confidence:.2f}[/]\n"
                            f"[bold]Rationale:[/] {p.rationale}"
                        )
                        console.print(Panel(detail_panel, title=f"Proposal Inspection: #{target_idx}", expand=False))

                        action_choice = Prompt.ask(
                            "Action for this file",
                            choices=["y", "n", "e", "s", "b"],
                            default="b",
                            show_choices=True,
                        ).lower().strip()

                        if action_choice == "b":
                            console.print("[dim]Returning to proposal list view...[/]")
                            continue
                        elif action_choice == "y":
                            if execute_proposal_approval(mover, recorder, p):
                                session_moved_count += 1
                                console.print(f"[green][OK] Moved:[/] {Path(p.source_path).name} -> {p.proposed_destination}")
                            else:
                                console.print(f"[red][FAIL] Failed to move:[/] {p.source_path}")
                        elif action_choice == "n":
                            repo.update_proposal_status(p.id, "rejected")
                            recorder.record_decision(p, action="rejected")
                            session_rejected_count += 1
                            console.print(f"[yellow]Proposal #{target_idx} rejected (recorded in feedback).[/]")
                        elif action_choice == "s":
                            session_skipped_ids.add(p.id)
                            console.print(f"[dim]Skipped proposal #{target_idx} (remains pending in DB).[/]")
                        elif action_choice == "e":
                            new_dest = Prompt.ask("Enter custom destination path (or 'b' to cancel)", default=p.proposed_destination).strip()
                            if new_dest.lower() in ("b", "back"):
                                console.print("[dim]Edit cancelled. Returning to proposal list view...[/]")
                                continue
                            if execute_proposal_approval(mover, recorder, p, explicit_dest=new_dest):
                                session_moved_count += 1
                                console.print(f"[green][OK] Successfully moved to custom destination:[/] {new_dest}")
                            else:
                                console.print(f"[red][FAIL] Move failed for #{target_idx}[/]")
                    else:
                        console.print(f"[red]ID {target_idx} out of range (1-{total_items}).[/]")
                except (ValueError, IndexError):
                    console.print("[red]Usage: v <id> (e.g., v 1)[/]")

            # Skip All for current page
            elif cmd in ("sa", "skip-all", "skipall"):
                skipped_count = 0
                for disp_idx, p in page_items:
                    if p.id not in session_skipped_ids:
                        session_skipped_ids.add(p.id)
                        skipped_count += 1
                console.print(f"[dim]Skipped {skipped_count} item(s) on current page (remain pending in DB).[/]")
                if current_page < total_pages:
                    current_page += 1

            # Skip Category
            elif cmd in ("sc", "skip-category", "skipcategory"):
                target_cat = arg.lower() if arg else (page_items[0][1].proposed_category.lower() if page_items else "")
                if not target_cat:
                    console.print("[red]Usage: sc <category> (e.g. sc Academics)[/]")
                    continue
                skipped_count = 0
                for p in pending:
                    if p.proposed_category.lower() == target_cat and p.id not in session_skipped_ids:
                        session_skipped_ids.add(p.id)
                        skipped_count += 1
                console.print(f"[dim]Skipped {skipped_count} item(s) for category '{target_cat}' (remain pending in DB).[/]")

            # Skip Range
            elif cmd in ("sr", "skip-range", "skiprange") or (cmd == "skip" and arg):
                range_arg = arg
                try:
                    indices = parse_range(range_arg, total_items)
                    skipped_count = 0
                    for disp_idx in indices:
                        p = pending[disp_idx - 1]
                        if p.id not in session_skipped_ids:
                            session_skipped_ids.add(p.id)
                            skipped_count += 1
                    console.print(f"[dim]Skipped {skipped_count} item(s) in range '{range_arg}' (remain pending in DB).[/]")
                except ValueError as e:
                    console.print(f"[red]Error parsing range: {e}[/]")

            # Skip single item
            elif cmd in ("s", "skip") and not arg:
                # Skip first un-skipped item on current page
                pending_on_page = [disp_idx for disp_idx, p in page_items if p.id not in session_skipped_ids]
                if pending_on_page:
                    target_idx = pending_on_page[0]
                    target_p = pending[target_idx - 1]
                    session_skipped_ids.add(target_p.id)
                    console.print(f"[dim]Skipped proposal #{target_idx} (remains pending in DB).[/]")
                else:
                    console.print("[yellow]No unskipped items on this page.[/]")

            # Single item skip by ID
            elif cmd in ("s", "skip") and arg:
                try:
                    target_idx = int(arg)
                    if 1 <= target_idx <= total_items:
                        target_p = pending[target_idx - 1]
                        session_skipped_ids.add(target_p.id)
                        console.print(f"[dim]Skipped proposal #{target_idx} (remains pending in DB).[/]")
                    else:
                        console.print(f"[red]ID {target_idx} out of range (1-{total_items}).[/]")
                except ValueError:
                    console.print("[red]Usage: s <id> (e.g., s 3)[/]")

            # Approve all on current page
            elif (cmd in ("y", "all") and not arg) or cmd == "approve-page":
                for disp_idx, p in page_items:
                    if execute_proposal_approval(mover, recorder, p):
                        session_moved_count += 1
                        console.print(f"[green][OK] (#{disp_idx}) Moved:[/] {Path(p.source_path).name} -> {p.proposed_destination}")
                    else:
                        console.print(f"[red][FAIL] (#{disp_idx}) Failed to move:[/] {p.source_path}")

            # Approve specific ID or range (e.g. 'y 1', 'y 1-5')
            elif cmd == "y" and arg:
                try:
                    indices = parse_range(arg, total_items)
                    for disp_idx in indices:
                        p = pending[disp_idx - 1]
                        if execute_proposal_approval(mover, recorder, p):
                            session_moved_count += 1
                            console.print(f"[green][OK] (#{disp_idx}) Moved:[/] {Path(p.source_path).name} -> {p.proposed_destination}")
                        else:
                            console.print(f"[red][FAIL] (#{disp_idx}) Failed to move:[/] {p.source_path}")
                except ValueError as e:
                    console.print(f"[red]Error parsing range: {e}[/]")

            # Reject specific ID or range (e.g. 'n 2', 'n 1-3')
            elif (cmd == "n" and arg) or cmd == "reject":
                target_arg = arg or (cmd_parts[1] if len(cmd_parts) > 1 else "")
                try:
                    indices = parse_range(target_arg, total_items)
                    for disp_idx in indices:
                        p = pending[disp_idx - 1]
                        repo.update_proposal_status(p.id, "rejected")
                        recorder.record_decision(p, action="rejected")
                        session_rejected_count += 1
                        console.print(f"[yellow]Proposal #{disp_idx} rejected (recorded in feedback).[/]")
                except ValueError as e:
                    console.print(f"[red]Error parsing range: {e}[/]")

            # Edit destination for an item
            elif cmd in ("e", "edit"):
                try:
                    target_idx = int(arg) if arg else page_items[0][0]
                    if 1 <= target_idx <= total_items:
                        p = pending[target_idx - 1]
                        new_dest = Prompt.ask("Enter custom destination path (or 'b' to go back)", default=p.proposed_destination).strip()
                        if new_dest.lower() in ("b", "back"):
                            console.print("[dim]Edit cancelled. Returning to proposal list view...[/]")
                            continue
                        if execute_proposal_approval(mover, recorder, p, explicit_dest=new_dest):
                            session_moved_count += 1
                            console.print(f"[green][OK] Successfully moved to custom destination:[/] {new_dest}")
                        else:
                            console.print(f"[red][FAIL] Move failed for #{target_idx}[/]")
                    else:
                        console.print(f"[red]ID {target_idx} out of range (1-{total_items}).[/]")
                except (ValueError, IndexError):
                    console.print("[red]Usage: e <id> (e.g., e 3)[/]")

            else:
                console.print(f"[yellow]Unrecognized action: '{user_input}'. Type 'q' to quit or see controls above.[/]")

    except KeyboardInterrupt:
        console.print("\n[yellow]Session interrupted by user (Ctrl+C). Exiting safely...[/]")

    # Print live final summary of session
    remaining_pending = len(repo.get_pending_proposals(category=filter_category))
    console.print(
        f"[bold]Session summary:[/] [green]{session_moved_count} moved[/], "
        f"[yellow]{session_rejected_count} rejected[/], [dim]{len(session_skipped_ids)} skipped in session[/], "
        f"[cyan]{remaining_pending} still pending in DB[/]."
    )
