#!/usr/bin/env python3
"""CLI entry point for school portal automation"""

import asyncio
import click
from rich.console import Console
from rich.table import Table
from rich import print as rprint
from src.models.schemas import ApplicationRequest, ApplicationStatus
from src.automation.workflows import WorkflowEngine
from src.utils.logger import log
from src.config.base_config import settings


console = Console()


@click.group()
def cli():
    """School Portal Automation System
    
    An LLM-based agentic solution for automating school portal interactions.
    """
    pass


@cli.command()
@click.option('--school', required=True, help='School identifier (config file name without .yaml)')
@click.option('--username', required=True, help='Portal username')
@click.option('--password', required=True, help='Portal password')
@click.option('--app-id', help='Application ID')
@click.option('--student-name', help='Student full name')
@click.option('--student-email', help='Student email address')
def check_application(
    school: str,
    username: str,
    password: str,
    app_id: str,
    student_name: str,
    student_email: str
):
    """Check the status of a student application and download offer if available"""
    
    console.print("\n[bold blue]School Portal Automation[/bold blue]")
    console.print(f"School: [cyan]{school}[/cyan]\n")
    
    if not any([app_id, student_name, student_email]):
        console.print("[red]Error: Must provide at least one of --app-id, --student-name, or --student-email[/red]")
        return
    
    # Create request
    request = ApplicationRequest(
        school=school,
        username=username,
        password=password,
        application_id=app_id,
        student_name=student_name,
        student_email=student_email
    )
    
    # Execute workflow
    with console.status("[bold green]Running automation workflow...", spinner="dots"):
        engine = WorkflowEngine()
        result = asyncio.run(engine.execute(request))
    
    # Display results
    console.print("\n[bold]Results:[/bold]\n")
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Success", "✓ Yes" if result.success else "✗ No")
    table.add_row("Status", result.status.value.replace("_", " ").title())
    table.add_row("Offer Downloaded", "✓ Yes" if result.offer_downloaded else "✗ No")
    
    if result.offer_path:
        table.add_row("Offer Path", result.offer_path)
    
    table.add_row("Message", result.message)
    
    console.print(table)
    
    # Additional metadata
    if result.metadata:
        console.print("\n[bold]Additional Information:[/bold]")
        for key, value in result.metadata.items():
            if key not in ['school', 'application_id', 'student_name']:
                console.print(f"  {key}: {value}")
    
    console.print(f"\n[dim]Logs saved to: {settings.logs_dir}[/dim]")
    console.print(f"[dim]Screenshots saved to: {settings.logs_dir / 'screenshots'}[/dim]\n")


@cli.command()
@click.option('--school-name', required=True, help='Full name of the school')
@click.option('--url', required=True, help='Portal URL')
@click.option('--username', required=True, help='Test username for verification')
@click.option('--password', required=True, help='Test password for verification')
def onboard(school_name: str, url: str, username: str, password: str):
    """Onboard a new school by creating config and testing login"""
    
    console.print("\n[bold blue]School Onboarding Wizard[/bold blue]\n")
    console.print(f"School: [cyan]{school_name}[/cyan]")
    console.print(f"Portal: [cyan]{url}[/cyan]\n")
    
    with console.status("[bold green]Running onboarding workflow...", spinner="dots"):
        engine = WorkflowEngine()
        result = asyncio.run(engine.onboard_school(
            school_name=school_name,
            portal_url=url,
            username=username,
            password=password
        ))
    
    console.print("\n[bold]Onboarding Results:[/bold]\n")
    
    if result["success"]:
        console.print("[green]✓ Onboarding successful![/green]\n")
        console.print(f"Config file created: [cyan]{result['config_path']}[/cyan]")
        
        if "dashboard_analysis" in result:
            console.print("\n[bold]Dashboard Analysis:[/bold]")
            analysis = result["dashboard_analysis"]
            console.print(f"  Page Type: {analysis.get('page_type', 'unknown')}")
            console.print(f"  Elements Found: {', '.join(analysis.get('elements', []))}")
            console.print(f"  Confidence: {analysis.get('confidence', 0):.0%}")
        
        console.print("\n[bold green]Next steps:[/bold green]")
        console.print("1. Review and refine the config file if needed")
        console.print("2. Test with a real application using check-application command")
        console.print("3. Iterate on the config based on test results\n")
    else:
        console.print(f"[red]✗ Onboarding failed: {result['message']}[/red]\n")
        if "config_path" in result:
            console.print(f"Partial config saved to: [cyan]{result['config_path']}[/cyan]")
            console.print("You may need to manually edit the config file.\n")


@cli.command()
def list_schools():
    """List all configured schools"""
    
    console.print("\n[bold blue]Configured Schools[/bold blue]\n")
    
    config_files = list(settings.config_dir.glob("*.yaml"))
    
    if not config_files:
        console.print("[yellow]No schools configured yet.[/yellow]")
        console.print("Use 'python run.py onboard' to add a school.\n")
        return
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("School ID", style="cyan")
    table.add_column("Config File", style="green")
    
    for config_file in sorted(config_files):
        school_id = config_file.stem
        table.add_row(school_id, config_file.name)
    
    console.print(table)
    console.print(f"\n[dim]Config directory: {settings.config_dir}[/dim]\n")


@cli.command()
@click.option('--school', required=True, help='School identifier')
def show_config(school: str):
    """Display configuration for a specific school"""
    
    import yaml
    
    config_path = settings.config_dir / f"{school}.yaml"
    
    if not config_path.exists():
        console.print(f"[red]Config file not found: {config_path}[/red]\n")
        return
    
    console.print(f"\n[bold blue]Configuration for: {school}[/bold blue]\n")
    console.print(f"[dim]File: {config_path}[/dim]\n")
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Pretty print the config
    import json
    console.print(json.dumps(config, indent=2))
    console.print()


@cli.command()
def test_setup():
    """Test that the environment is configured correctly"""
    
    console.print("\n[bold blue]Testing Environment Setup[/bold blue]\n")
    
    checks = []
    
    # Check Python version
    import sys
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    checks.append(("Python version", python_version, sys.version_info >= (3, 11)))
    
    # Check Gemini API key
    try:
        api_key = settings.gemini_api_key
        has_key = bool(api_key and api_key != "your_gemini_api_key_here")
        checks.append(("Gemini API key", "Configured" if has_key else "Not set", has_key))
    except:
        checks.append(("Gemini API key", "Not set", False))
    
    # Check directories
    checks.append(("Output directory", str(settings.output_dir), settings.output_dir.exists()))
    checks.append(("Config directory", str(settings.config_dir), settings.config_dir.exists()))
    
    # Check Playwright
    try:
        from playwright.async_api import async_playwright
        checks.append(("Playwright", "Installed", True))
    except ImportError:
        checks.append(("Playwright", "Not installed", False))
    
    # Display results
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Check", style="cyan")
    table.add_column("Value", style="white")
    table.add_column("Status", style="green")
    
    all_passed = True
    for check, value, passed in checks:
        status = "✓ Pass" if passed else "✗ Fail"
        status_style = "green" if passed else "red"
        table.add_row(check, value, f"[{status_style}]{status}[/{status_style}]")
        if not passed:
            all_passed = False
    
    console.print(table)
    
    if all_passed:
        console.print("\n[green]✓ All checks passed! Environment is ready.[/green]\n")
    else:
        console.print("\n[yellow]⚠ Some checks failed. Please fix the issues above.[/yellow]")
        console.print("\n[bold]Common fixes:[/bold]")
        console.print("  - Set GEMINI_API_KEY in .env file")
        console.print("  - Run: pip install -r requirements.txt")
        console.print("  - Run: playwright install chromium\n")


if __name__ == '__main__':
    cli()

