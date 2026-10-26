"""CLI command: propose file classifications using the selected classifier."""

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from organizer.ai.base import ClassifierUnavailable
from organizer.config.loader import load_rules_config
from organizer.propose_service import VALID_MODELS, run_propose
from organizer.storage.repository import Repository

console = Console()


def propose(
    config_file: str = typer.Option("config/rules.yaml", "--config", help="Path to rules YAML file"),
    min_confidence: Optional[float] = typer.Option(
        None, "--min-confidence", help="Minimum confidence threshold required for matching rules"
    ),
    organize_root: Optional[str] = typer.Option(
        None, "--organize-root", help="Override base directory for organized folders (defaults to scan root)"
    ),
    model: str = typer.Option(
        "ml", "--model", help=f"Classifier backend: {' | '.join(VALID_MODELS)}"
    ),
    no_fallback: bool = typer.Option(
        False, "--no-fallback", help="Fail hard if the requested model is unavailable (no fallback to rules)"
    ),
    db: str = typer.Option("data/organizer.db", "--db", help="Path to SQLite database file"),
) -> None:
    """Run the selected classifier over scanned files and store proposals in SQLite."""
    if model not in VALID_MODELS:
        console.print(
            f"[bold red]Error:[/] invalid --model {model!r}. Valid: {', '.join(VALID_MODELS)}."
        )
        raise typer.Exit(code=1)

    try:
        rules_cfg = load_rules_config(config_file)
    except Exception as e:
        console.print(f"[bold red]Configuration error:[/] {e}")
        raise typer.Exit(code=1)

    if min_confidence is not None:
        rules_cfg.defaults.min_confidence_for_proposal = min_confidence

    repo = Repository(db)

    try:
        result = run_propose(
            repo,
            rules_cfg,
            model=model,
            organize_root=organize_root,
            no_fallback=no_fallback,
        )
    except ClassifierUnavailable as e:
        console.print(f"[bold red]Error:[/] {e}")
        if getattr(e, "hint", None):
            console.print(f"[dim]{e.hint}[/]")
        raise typer.Exit(code=1)
    except RuntimeError as e:
        console.print(f"[bold red]Error:[/] {e}")
        raise typer.Exit(code=1)
    except ValueError as e:
        console.print(f"[bold red]Error:[/] {e}")
        raise typer.Exit(code=1)

    if result.fell_back:
        console.print(
            f"[yellow]--model {model} unavailable ({result.fallback_reason}); "
            f"fell back to {result.backend}.[/]"
        )

    if result.proposals_saved == 0:
        console.print(
            "[yellow]No unproposed files found. Run 'organizer scan <path>' first "
            "or all files already have pending proposals.[/]"
        )
        return

    if result.bootstrapped_examples:
        console.print(
            f"[dim]Cold start: bootstrapped {result.bootstrapped_examples} "
            f"pseudo-labeled examples from rules.[/]"
        )

    console.print(
        f"[bold cyan]Evaluating with backend [bold]{result.backend}[/]...[/]"
    )

    table = Table(
        title=f"Generated Proposals ({result.proposals_saved} files, backend={result.backend})"
    )
    table.add_column("Proposed Category", style="cyan", no_wrap=True)
    table.add_column("Count", justify="right", style="green")

    for cat, count in result.category_counts.most_common():
        table.add_row(cat, str(count))

    console.print(table)
    console.print(f"[bold green]Saved {result.proposals_saved} pending proposal(s) into database.[/]")
    console.print("Run [bold cyan]organizer review[/] to review and execute moves.")