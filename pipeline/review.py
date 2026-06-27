"""review.py — terminal UI for reviewing and editing captions before publishing."""
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

console = Console()

PLATFORM_COLORS = {
    "instagram": "magenta",
    "facebook":  "blue",
    "tiktok":    "cyan",
    "linkedin":  "bright_blue",
    "youtube":   "red",
}


def review_captions(captions: dict, default_datetime: str) -> tuple:
    """Interactively review and edit captions.

    Returns (approved_captions, post_datetime).
    Returns ({}, '') if the user cancels.
    """
    console.print("\n[bold cyan]─── Caption Review ───[/bold cyan]\n")

    approved = {}
    platforms = list(captions.keys())

    for i, platform in enumerate(platforms, 1):
        color = PLATFORM_COLORS.get(platform, "white")
        text = captions[platform]

        console.print(
            Panel(
                text,
                title=f"[bold {color}]{platform.upper()}[/bold {color}]  [{i}/{len(platforms)}]",
                border_style=color,
                expand=False,
                padding=(1, 2),
            )
        )

        action = Prompt.ask(
            f"  [green]↵ keep[/green]  [yellow]type[/yellow]=replace  [red]s[/red]=skip",
            default="",
        )

        if action.lower() == "s":
            console.print(f"  [dim]Skipped {platform}[/dim]\n")
            continue
        elif action == "":
            approved[platform] = text
            console.print(f"  [green]✓ Kept[/green]\n")
        else:
            approved[platform] = action
            console.print(f"  [green]✓ Updated[/green]\n")

    if not approved:
        console.print("[red]No captions approved — nothing to post.[/red]")
        return {}, ""

    console.print(f"[bold]Post datetime:[/bold] [yellow]{default_datetime}[/yellow]")
    post_dt = Prompt.ask(
        "  [green]↵ use default[/green]  or type an ISO 8601 datetime",
        default=default_datetime,
    )

    console.print()
    if not Confirm.ask("[bold green]Looks good — publish?[/bold green]"):
        console.print("[red]Cancelled.[/red]")
        return {}, ""

    return approved, post_dt
