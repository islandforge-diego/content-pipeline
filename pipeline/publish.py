"""publish.py — upload media to S3 (boto3) and schedule posts to Buffer.

S3 upload uses boto3 directly so it runs cross-platform (Mac/Windows/Linux) with
no bash dependency. The shell uploader (uploader/push_to_s3.sh) remains for
terminal users; this module is what the CLI and web UI call.
"""
import mimetypes
from pathlib import Path

import boto3
from botocore.config import Config
from rich.console import Console

from buffer_api import create_post

console = Console()

PRESIGN_TTL = 7 * 24 * 3600  # 7 days, matches push_to_s3.sh --share default


def _s3_client(region: str):
    """S3 client pinned to the bucket's REGIONAL endpoint with virtual-hosted
    addressing. Without this, presigned URLs use the region-less global host and
    external fetchers (Buffer) get HTTP 403 on the signature."""
    return boto3.client(
        "s3",
        region_name=region,
        endpoint_url=f"https://s3.{region}.amazonaws.com",
        config=Config(s3={"addressing_style": "virtual"}, signature_version="s3v4"),
    )


def upload_to_s3(file_path: str, client: dict, dry_run: bool = False, key_prefix: str = "",
                 on_progress=None) -> str:
    """Upload a file to the client's S3 bucket and return a presigned URL.

    Block Public Access stays ON; we hand out short-lived presigned URLs that
    Buffer/Canva download at schedule time. `on_progress(percent)` is called
    during upload (0-100) for the UI progress bar.
    """
    bucket = client["s3"]["bucket"]
    region = client["s3"]["region"]
    name = Path(file_path).name
    key = f"{key_prefix.rstrip('/')}/{name}" if key_prefix else name

    if dry_run:
        if on_progress:
            on_progress(100)
        return f"https://{bucket}.s3.{region}.amazonaws.com/[dry-run]/{key}"

    s3 = _s3_client(region)
    content_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    total = Path(file_path).stat().st_size or 1
    sent = {"n": 0}

    def cb(chunk):
        if on_progress:
            sent["n"] += chunk
            on_progress(min(100, int(sent["n"] * 100 / total)))

    s3.upload_file(
        file_path, bucket, key,
        ExtraArgs={"ContentType": content_type},
        Callback=cb,
    )
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=PRESIGN_TTL,
    )


def target_channels(client: dict, kind: str) -> list:
    """Return the platform names this kind of post should go to, per config."""
    feed = client["schedule"]["feed"]
    return feed["reels_channels"] if kind == "reel" else feed["image_channels"]


def publish(file_path, client, captions, post_datetime, kind, token, dry_run=False, on_event=None):
    """Upload to S3 and create Buffer posts for all approved captions.

    on_event(kind, payload) is an optional callback for UI progress:
      ('upload', url) / ('post', {platform, status, id|error})
    Returns a result dict: {media_url, posts: [{platform, ok, id|error}]}.
    """
    def emit(ev, payload):
        if on_event:
            on_event(ev, payload)

    as_draft = client.get("buffer", {}).get("create_as_draft", True)
    yt_category = client.get("buffer", {}).get("youtube_category_id", "22")

    console.print("\n[bold]Uploading to S3...[/bold]")
    media_url = upload_to_s3(file_path, client, dry_run,
                            on_progress=lambda pct: emit("upload_progress", pct))
    console.print(f"[green]✓[/green] {media_url}")
    emit("upload", media_url)

    channels = client["buffer"]["channels"]
    results = []

    console.print("\n[bold]Scheduling to Buffer...[/bold]")
    for platform in target_channels(client, kind):
        if platform not in captions:
            console.print(f"  [dim]{platform}: skipped (no caption)[/dim]")
            continue
        channel_id = channels[platform]["id"]

        if dry_run:
            console.print(f"  [dim]{platform}: would post to {channel_id} ({len(captions[platform])} chars)[/dim]")
            results.append({"platform": platform, "ok": True, "id": "(dry-run)"})
            emit("post", results[-1])
            continue

        try:
            post = create_post(channel_id, captions[platform], media_url, post_datetime,
                               kind, token, platform=platform, as_draft=as_draft,
                               yt_category=yt_category)
            entry = {"platform": platform, "ok": True, "id": post.get("id", "?"),
                     "status": post.get("status", "")}
            console.print(f"  [green]✓[/green] {platform} — Buffer id {entry['id']}")
        except Exception as e:
            entry = {"platform": platform, "ok": False, "error": str(e)}
            console.print(f"  [red]✗[/red] {platform}: {e}")
        results.append(entry)
        emit("post", entry)

    return {"media_url": media_url, "posts": results, "as_draft": as_draft}
