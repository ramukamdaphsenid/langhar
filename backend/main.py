"""CLI connectivity check for the local Tally Prime service."""
import click
from rich.panel import Panel
from rich.table import Table

from config.settings import settings
from src.tally.client import TallyClient
from src.tally.odbc_client import TallyODBCClient
from src.utils.logger import console


@click.group()
def cli():
    """Langhar live Tally voucher service."""


@cli.command(name="check")
def check_connections():
    """Verify connectivity to Tally Prime."""
    console.rule("[bold cyan]Service Connectivity Check[/bold cyan]")

    table = Table(title="Tally Connection Status", show_header=True, header_style="bold magenta")
    table.add_column("Service", style="bold")
    table.add_column("Target / Config", style="dim")
    table.add_column("Status", justify="center")
    table.add_column("Details")

    if settings.tally.use_odbc:
        tally = TallyODBCClient()
        target = f"ODBC DSN: {settings.tally.odbc_dsn}"
    else:
        tally = TallyClient()
        target = f"{tally.url} (XML API)"

    tally_ok, tally_message = tally.check_connection()
    table.add_row(
        "Tally Prime",
        target,
        "[bold green]PASS[/bold green]" if tally_ok else "[bold red]FAIL[/bold red]",
        tally_message,
    )

    console.print(table)

    if not tally_ok:
        console.print(Panel(
            "[bold yellow]Tally Prime setup:[/bold yellow]\n"
            "1. Open the company in Tally Prime.\n"
            "2. Enable the XML HTTP server in F1 (Help) -> Settings -> Connectivity.\n"
            "3. Confirm the configured port, normally 9000, and retry this check.",
            title="Connection help",
            border_style="yellow",
        ))


if __name__ == "__main__":
    cli()
