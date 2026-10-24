"""CLI Entry point for Tally Prime to Firebase Sales Voucher Synchronization."""
import json
import sys
from pathlib import Path
import click
from rich.panel import Panel
from rich.table import Table

from config.settings import settings
from src.firebase.client import FirebaseClient
from src.sync.engine import SyncEngine
from src.sync.state import SyncStateManager
from src.tally.client import TallyClient
from src.tally.odbc_client import TallyODBCClient
from src.tally.parser import parse_tally_vouchers_xml
from src.utils.logger import console, logger


@click.group()
def cli():
    """Langhar Enterprise Rice Platform - Tally Prime Sales Voucher Sync Engine."""
    pass


@cli.command(name="check")
def check_connections():
    """Verify connectivity to both Tally Prime and Firebase Firestore."""
    console.rule("[bold cyan]System Connectivity & Health Check[/bold cyan]")

    table = Table(title="Connection Status", show_header=True, header_style="bold magenta")
    table.add_column("Service", style="bold")
    table.add_column("Target / Config", style="dim")
    table.add_column("Status", justify="center")
    table.add_column("Details")

    # 1. Check Tally
    if settings.tally.use_odbc:
        tally = TallyODBCClient()
        target = f"ODBC DSN: {settings.tally.odbc_dsn}"
    else:
        tally = TallyClient()
        target = f"{tally.url} (XML API)"

    tally_ok, tally_msg = tally.check_connection()
    table.add_row(
        "Tally Prime",
        target,
        "[bold green]PASS[/bold green]" if tally_ok else "[bold red]FAIL[/bold red]",
        tally_msg
    )

    # 2. Check Firebase
    firebase = FirebaseClient()
    fb_target = f"Collection: {settings.firebase.collection_name}"
    fb_ok, fb_msg = firebase.check_connection()
    table.add_row(
        "Firebase Firestore",
        fb_target,
        "[bold green]PASS[/bold green]" if fb_ok else "[bold red]FAIL[/bold red]",
        fb_msg
    )

    console.print(table)

    if not tally_ok:
        console.print(Panel(
            "[bold yellow]How to fix Tally Prime connection:[/bold yellow]\n"
            "1. Open Tally Prime on this PC or server.\n"
            "2. Press [bold]F1 (Help) -> Settings -> Connectivity[/bold].\n"
            "3. Set [bold]TallyPrime acts as[/bold] to [bold]Both[/bold] or [bold]Server[/bold].\n"
            "4. Ensure [bold]Port[/bold] is [bold]9000[/bold] and [bold]Enable ODBC[/bold] is [bold]Yes[/bold].\n"
            "5. Restart Tally Prime and re-run this check.",
            title="Tally Setup Instructions",
            border_style="yellow"
        ))

    if not fb_ok:
        console.print(Panel(
            "[bold yellow]How to fix Firebase connection:[/bold yellow]\n"
            f"1. Open your Firebase Console (https://console.firebase.google.com).\n"
            "2. Go to [bold]Project Settings -> Service Accounts[/bold].\n"
            "3. Click [bold]Generate New Private Key[/bold] to download the JSON credentials.\n"
            f"4. Save it as [bold]{settings.firebase.credentials_path.resolve()}[/bold].",
            title="Firebase Credentials Setup",
            border_style="yellow"
        ))


@cli.command(name="sync")
@click.option("--from-date", help="Start date (YYYY-MM-DD or YYYYMMDD)", default=None)
@click.option("--to-date", help="End date (YYYY-MM-DD or YYYYMMDD)", default=None)
@click.option("--full", is_flag=True, help="Perform full synchronization (ignore last AlterID)")
def sync_vouchers(from_date, to_date, full):
    """Execute a single synchronization run."""
    engine = SyncEngine()
    result = engine.run_sync(from_date=from_date, to_date=to_date, full_resync=full)

    if result["status"] == "SUCCESS":
        console.print(f"[bold green][SUCCESS][/bold green] Successfully synced {result['synced_count']} voucher(s).")
    else:
        console.print(f"[bold red][FAILED][/bold red] Sync failed: {result.get('error')}")
        sys.exit(1)


@cli.command(name="daemon")
@click.option("--interval", default=None, type=int, help="Sync interval in seconds (default from settings)")
def run_daemon(interval):
    """Start background daemon to sync vouchers periodically."""
    engine = SyncEngine()
    engine.start_daemon(interval_seconds=interval)


@cli.command(name="status")
def view_status():
    """View current sync state and statistics."""
    state_mgr = SyncStateManager()
    state = state_mgr.load_state()

    console.rule("[bold cyan]Sync State Overview[/bold cyan]")
    table = Table(show_header=False, box=None)
    table.add_column("Key", style="bold")
    table.add_column("Value")

    table.add_row("Last Sync Timestamp:", str(state.get("last_sync_timestamp") or "Never"))
    table.add_row("Last Alter ID Synced:", str(state.get("last_alter_id", 0)))
    table.add_row("Total Vouchers Synced:", str(state.get("total_vouchers_synced", 0)))
    table.add_row("Last Execution Status:", str(state.get("last_status", "UNKNOWN")))
    if state.get("last_error"):
        table.add_row("Last Error:", f"[red]{state.get('last_error')}[/red]")
    table.add_row("State File Location:", str(state_mgr.state_file.resolve()))

    console.print(table)


@cli.command(name="reset-state")
def reset_state():
    """Reset sync state to trigger a full re-sync on next execution."""
    state_mgr = SyncStateManager()
    state_mgr.reset()
    console.print("[bold yellow]Sync state has been reset successfully.[/bold yellow]")


@cli.command(name="export-sample")
@click.option("--output", "-o", default="sample_vouchers.json", help="Path to save output JSON")
def export_sample(output):
    """Fetch vouchers from Tally (or mock file) and export parsed JSON to inspect."""
    if settings.tally.use_odbc:
        tally = TallyODBCClient()
        tally_label = f"ODBC DSN: {settings.tally.odbc_dsn}"
    else:
        tally = TallyClient()
        tally_label = tally.url

    try:
        console.print(f"Attempting to fetch live sales vouchers from Tally Prime ({tally_label})...")
        vouchers = tally.fetch_sales_vouchers()
    except Exception as e:
        console.print(f"[yellow]Could not connect to live Tally ({e}). Reading from mock XML test file...[/yellow]")
        mock_file = Path("tests/mock_sales_vouchers.xml")
        if not mock_file.exists():
            console.print("[red]Mock file not found. Ensure tests/mock_sales_vouchers.xml exists.[/red]")
            return
        with open(mock_file, "r", encoding="utf-8") as f:
            vouchers = parse_tally_vouchers_xml(f.read())

    out_path = Path(output)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(vouchers, f, indent=2, default=str)

    console.print(f"[bold green][OK][/bold green] Exported {len(vouchers)} voucher(s) to '{out_path.resolve()}'.")


if __name__ == "__main__":
    cli()
