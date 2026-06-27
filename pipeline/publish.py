"""publish.py — upload to S3 and schedule posts to Buffer."""
import subprocess
from pathlib import Path

import requests
from rich.console import Console

console = Console()

BUFFER_GRAPHQL = "https://api.buffer.com/graphql"

# Buffer's GraphQL mutation for creating a post.
# If Buffer changes their schema, introspect via: POST BUFFER_GRAPHQL with {"query": "{__schema{types{name}}}"}
_CREATE_POST = """
mutation CreatePost($input: CreatePostInput!) {
  createPost(input: $input) {
    ... on CreatePostSuccess {
      post { id status dueAt }
    }
    ... on InvalidInput {
      message
    }
  }
}
"""


def upload_to_s3(file_path: str, client: dict, dry_run: bool = False) -> str:
    """Upload file to S3 and return a presigned URL."""
    bucket = client["s3"]["bucket"]
    region = client["s3"]["region"]
    uploader = Path(__file__).parent.parent / "uploader" / "push_to_s3.sh"

    if dry_run:
        return f"https://{bucket}.s3.{region}.amazonaws.com/[dry-run/{Path(file_path).name}]"

    result = subprocess.run(
        ["bash", str(uploader), file_path, "--share", "--bucket", bucket, "--region", region],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"S3 upload failed:\n{result.stderr}")

    # push_to_s3.sh prints the presigned URL as the last line of stdout
    lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
    if not lines:
        raise RuntimeError("S3 uploader produced no output")
    return lines[-1]


def _post_to_channel(channel_id: str, caption: str, media_url: str, due_at: str, kind: str, token: str) -> dict:
    asset_type = "VIDEO" if kind == "reel" else "IMAGE"
    variables = {
        "input": {
            "channelId": channel_id,
            "text": caption,
            "dueAt": due_at,
            "assets": [{"type": asset_type, "url": media_url}],
        }
    }
    resp = requests.post(
        BUFFER_GRAPHQL,
        json={"query": _CREATE_POST, "variables": variables},
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(f"Buffer API error: {data['errors']}")
    result = data.get("data", {}).get("createPost", {})
    if "message" in result:
        raise RuntimeError(f"Buffer rejected post: {result['message']}")
    return result.get("post", {})


def publish(file_path: str, client: dict, captions: dict, post_datetime: str, kind: str, token: str, dry_run: bool = False):
    """Upload to S3 and create Buffer posts for all approved captions."""
    console.print("\n[bold]Uploading to S3...[/bold]")
    media_url = upload_to_s3(file_path, client, dry_run)
    console.print(f"[green]✓[/green] {media_url}")

    schedule = client["schedule"]["feed"]
    targets = schedule["reels_channels"] if kind == "reel" else schedule["image_channels"]
    channels = client["buffer"]["channels"]

    console.print(f"\n[bold]Scheduling to Buffer...[/bold]")
    for platform in targets:
        if platform not in captions:
            console.print(f"  [dim]{platform}: skipped (no caption)[/dim]")
            continue
        channel_id = channels[platform]["id"]

        if dry_run:
            console.print(f"  [dim]{platform}: would post to channel {channel_id} ({len(captions[platform])} chars)[/dim]")
            continue

        try:
            post = _post_to_channel(channel_id, captions[platform], media_url, post_datetime, kind, token)
            console.print(f"  [green]✓[/green] {platform} — Buffer id {post.get('id', '?')}")
        except Exception as e:
            console.print(f"  [red]✗[/red] {platform}: {e}")
