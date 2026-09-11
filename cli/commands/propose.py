"""CLI command: propose file classifications using the rule engine."""

from collections import Counter
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table

from organizer.config.loader import load_rules_config
from organizer.rules.engine import RuleBasedClassifier
from organizer.storage.repository import Repository

console = Console()


def propose(
    config_file: str = typer.Option("config/rules.yaml", "--config", help="Path to rules YAML file"),
    min_confidence: Optional[float] = typer.Option(
        None, "--min-confidence", help="Minimum confidence threshold required for matching rules"
    ),
    db: str = typer.Option("data/organizer.db", "--db", help="Path to SQLite database file"),
) -> None:
    """Run the rule engine over scanned files with no pending proposal and store proposals in SQLite."""
    try:
        rules_cfg = load_rules_config(config_file)
    except Exception as e:
        console.print(f"[bold red]Configuration error:[/] {e}")
        raise typer.Exit(code=1)

    if min_confidence is not None:
        rules_cfg.defaults.min_confidence_for_proposal = min_confidence

    repo = Repository(db)
    classifier = RuleBasedClassifier(rules_cfg)

    unproposed_files = repo.get_files_without_pending_proposals()
    if not unproposed_files:
        console.print("[yellow]No unproposed files found. Run 'organizer scan <path>' first or all files already have pending proposals.[/]")
        return

    console.print(f"[bold cyan]Evaluating rules for {len(unproposed_files)} file(s)...[/]")

    category_counts: Counter[str] = Counter()
    proposals_saved = 0

    for file_record in unproposed_files:
        proposal = classifier.classify(file_record)
        repo.save_proposal(proposal)
        category_counts[proposal.proposed_category] += 1
        proposals_saved += 1

    table = Table(title=f"Generated Proposals ({proposals_saved} files)")
    table.add_column("Proposed Category", style="cyan", no_wrap=True)
    table.add_column("Count", justify="right", style="green")

    for cat, count in category_counts.most_common():
        table.add_row(cat, str(count))

    console.print(table)
    console.print(f"[bold green]Saved {proposals_saved} pending proposal(s) into database.[/]")
    console.print("Run [bold cyan]organizer approve[/] to review and execute moves.")
