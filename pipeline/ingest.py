#!/usr/bin/env python3
"""ingest.py — run a local file through the full content pipeline.

Steps:
  1. Transcribe video (ffmpeg + local Whisper) or use --brief for images
  2. Generate platform-specific captions (Claude Haiku)
  3. Review and edit captions in the terminal
  4. Upload to S3 and schedule posts to Buffer

Usage:
    python pipeline/ingest.py --client deba clip.mp4
    python pipeline/ingest.py --client deba photo.jpg --brief "Deba at the Garland flip"
    python pipeline/ingest.py --client deba clip.mp4 --dry-run
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytz
from dotenv import load_dotenv
from rich.console import Console

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

sys.path.insert(0, str(ROOT / "pipeline"))
from transcribe import transcribe
from caption_gen import generate_captions
from review import review_captions
from publish import publish

console = Console()

VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic"}


def _next_post_time(client: dict) -> str:
    tz = pytz.timezone(client["buffer"]["timezone"])
    now = datetime.now(tz)
    h, m = map(int, client["schedule"]["feed"]["default_time"].split(":"))
    scheduled = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if scheduled <= now:
        scheduled += timedelta(days=1)
    return scheduled.isoformat()


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("file", help="Path to the photo or video file")
    parser.add_argument("--client", required=True, help="Client slug (e.g. deba)")
    parser.add_argument("--brief", default="", help="Short description; required for images, optional override for video")
    parser.add_argument("--kind", choices=["reel", "image"], help="Override auto-detected content type")
    parser.add_argument("--dry-run", action="store_true", help="Preview payloads without uploading or posting")
    args = parser.parse_args()

    file = Path(args.file)
    if not file.exists():
        sys.exit(f"File not found: {file}")

    config_path = ROOT / "config" / "clients" / f"{args.client}.json"
    if not config_path.exists():
        sys.exit(f"Client config not found: {config_path}")
    client = json.loads(config_path.read_text())

    # Detect kind
    ext = file.suffix.lower()
    if args.kind:
        kind = args.kind
    elif ext in VIDEO_EXTS:
        kind = "reel"
    elif ext in IMAGE_EXTS:
        kind = "image"
    else:
        sys.exit(f"Unsupported file type '{ext}'. Use --kind to force.")

    console.print(f"\n[bold cyan]Content Pipeline[/bold cyan] — {client['display_name']}")
    console.print(
        f"File: [yellow]{file.name}[/yellow]  "
        f"Kind: [yellow]{kind}[/yellow]"
        + ("  [dim](dry run)[/dim]" if args.dry_run else "")
    )

    # Step 1: Transcribe or use brief
    if kind == "reel" and not args.brief:
        console.print("\n[bold]Transcribing video...[/bold]")
        transcript = transcribe(str(file))
        word_count = len(transcript.split())
        console.print(f"[green]✓[/green] {word_count} words\n[dim]{transcript[:200]}{'…' if len(transcript) > 200 else ''}[/dim]")
    elif kind == "image" and not args.brief:
        sys.exit("Images require --brief. Example: --brief \"Deba at the Garland property flip\"")
    else:
        transcript = args.brief

    # Step 2: Generate captions
    schedule = client["schedule"]["feed"]
    platforms = schedule["reels_channels"] if kind == "reel" else schedule["image_channels"]
    console.print(f"\n[bold]Generating captions for {len(platforms)} platforms...[/bold]")
    captions = generate_captions(client, transcript, kind, platforms)
    console.print(f"[green]✓[/green] Captions drafted")

    # Step 3: Review
    default_dt = _next_post_time(client)
    approved, post_datetime = review_captions(captions, default_dt)
    if not approved:
        sys.exit(0)

    # Step 4: Publish
    token = os.environ.get("BUFFER_TOKEN", "")
    if not token and not args.dry_run:
        sys.exit("BUFFER_TOKEN not set. Add it to .env or export it.")

    publish(str(file), client, approved, post_datetime, kind, token, dry_run=args.dry_run)
    console.print("\n[bold green]Done![/bold green]\n")


if __name__ == "__main__":
    main()
