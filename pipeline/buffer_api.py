"""buffer_api.py — thin client for the Buffer GraphQL API.

Schema verified against Buffer's live GraphQL (api.buffer.com/graphql). Used by
onboarding (list channels) and publishing (create posts).

Auth: a Buffer access token (BUFFER_TOKEN) sent as a Bearer header. Create one at
https://publish.buffer.com/settings/api.
"""
from datetime import datetime, timedelta

import requests

GRAPHQL_URL = "https://api.buffer.com/graphql"


def _graphql(query: str, variables: dict, token: str) -> dict:
    resp = requests.post(
        GRAPHQL_URL,
        json={"query": query, "variables": variables},
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("errors"):
        raise RuntimeError(f"Buffer API error: {data['errors']}")
    return data.get("data", {})


# --------------------------------------------------------------- channels

_CHANNELS_QUERY = """
query Channels($organizationId: OrganizationId!) {
  channels(input: { organizationId: $organizationId }) {
    id
    service
    name
    displayName
    type
  }
}
"""


def list_channels(token: str, org_id: str) -> list:
    """Return the org's channels: [{id, service, name, displayName, type}].

    'service' is the platform (instagram, facebook, tiktok, linkedin, youtube).
    """
    data = _graphql(_CHANNELS_QUERY, {"organizationId": org_id}, token)
    return data.get("channels", []) or []


# --------------------------------------------------------------- create post

_CREATE_POST = """
mutation CreatePost($input: CreatePostInput!) {
  createPost(input: $input) {
    __typename
    ... on PostActionSuccess { post { id status dueAt } }
    ... on InvalidInputError { message }
    ... on UnauthorizedError { message }
    ... on NotFoundError { message }
    ... on UnexpectedError { message }
    ... on RestProxyError { message code }
    ... on LimitReachedError { message }
  }
}
"""


DEFAULT_META_OPTS = {
    "facebook_post_type": "post",   # FB Reels via API are unreliable; a video 'post' is safe
    "youtube_category_id": "22",
    "youtube_privacy": "public",
    "youtube_made_for_kids": False,
}


def _platform_metadata(platform, kind, text, opts=None):
    """Per-network metadata Buffer requires. Returns a PostInputMetaData dict or None.

    - Instagram needs a post type (video -> reel, image -> post) + shouldShareToFeed.
    - Facebook needs a type; default 'post' (Reels error with UnexpectedError).
    - YouTube needs title, category, privacy, and madeForKids — omitting the last two
      makes Buffer's resolver fail with a generic UnexpectedError.
    - TikTok / LinkedIn need none.
    """
    o = {**DEFAULT_META_OPTS, **(opts or {})}
    if platform == "instagram":
        return {"instagram": {"type": "reel" if kind == "reel" else "post", "shouldShareToFeed": True}}
    if platform == "facebook":
        ftype = o["facebook_post_type"] if kind == "reel" else "post"
        return {"facebook": {"type": ftype}}
    if platform == "youtube":
        first = next((ln.strip() for ln in (text or "").splitlines() if ln.strip()), "New video")
        return {"youtube": {
            "title": first[:95],
            "categoryId": o["youtube_category_id"],
            "privacy": o["youtube_privacy"],
            "madeForKids": bool(o["youtube_made_for_kids"]),
        }}
    return None


def build_create_post_input(channel_id, text, media_url, due_at, kind, platform="",
                            as_draft=True, opts=None):
    """Build the CreatePostInput payload (pure; unit-tested separately).

    - schedulingType 'automatic' = Buffer publishes for you (vs 'notification' reminders).
    - mode 'customScheduled' + dueAt = scheduled for a specific time.
    - assets use Buffer's @oneOf shape: {image|video: {url}}.
    - metadata carries per-network requirements (see _platform_metadata).
    - saveToDraft keeps it as a draft for approval (honors the 'drafts for approval' rule).
    """
    asset_key = "video" if kind == "reel" else "image"
    payload = {
        "channelId": channel_id,
        "text": text,
        "schedulingType": "automatic",
        "mode": "customScheduled",
        "dueAt": due_at,
        "assets": [{asset_key: {"url": media_url}}],
        "saveToDraft": bool(as_draft),
    }
    meta = _platform_metadata(platform, kind, text, opts)
    if meta:
        payload["metadata"] = meta
    return payload


_DELETE_POST = """
mutation DeletePost($input: DeletePostInput!) {
  deletePost(input: $input) {
    __typename
    ... on DeletePostSuccess { id }
    ... on VoidMutationError { message }
  }
}
"""


def delete_post(post_id, token):
    """Delete a Buffer post by id (used to clean up validation test drafts)."""
    return _graphql(_DELETE_POST, {"input": {"id": post_id}}, token).get("deletePost", {})


_POSTS_QUERY = """
query Posts($input: PostsInput!) {
  posts(input: $input, first: 100) {
    edges { node { id channelId dueAt status } }
  }
}
"""


_SCHEDULED_QUERY = """
query Posts($input: PostsInput!, $after: String) {
  posts(input: $input, first: 100, after: $after) {
    edges { node {
      id channelId channelService status dueAt text schedulingType
      assets { type source thumbnail }
      metadata {
        __typename
        ... on InstagramPostMetadata { type }
        ... on FacebookPostMetadata { type }
        ... on YoutubePostMetadata { type }
        ... on TiktokPostMetadata { type }
        ... on LinkedInPostMetadata { type }
      }
    } }
    pageInfo { hasNextPage endCursor }
  }
}
"""


def list_scheduled_posts(token, org_id, channel_ids=None,
                         statuses=("scheduled", "draft", "needs_approval", "sent", "sending"),
                         since=None):
    """Return posts for the org's channels, sorted by time, paginating fully.

    `since` (ISO datetime) limits to posts dueAt >= since. `statuses` includes sent
    so history shows. Each node also carries schedulingType + metadata.type so the
    caller can tell stories (type 'story') from feed posts.
    """
    flt = {"status": list(statuses)}
    if channel_ids:
        flt["channelIds"] = channel_ids
    if since:
        flt["dueAt"] = {"start": since}
    base = {"organizationId": org_id, "filter": flt,
            "sort": [{"field": "dueAt", "direction": "asc"}]}
    nodes, after = [], None
    for _ in range(20):  # safety cap: up to 2000 posts
        data = _graphql(_SCHEDULED_QUERY, {"input": base, "after": after}, token)
        conn = data.get("posts", {})
        nodes += [e["node"] for e in (conn.get("edges") or [])]
        pi = conn.get("pageInfo", {}) or {}
        if not pi.get("hasNextPage"):
            break
        after = pi.get("endCursor")
    return nodes


def posts_at(token, org_id, channel_ids, due_at):
    """Return existing posts on the given channels scheduled within the same minute
    as due_at (used to warn about double-booking a time slot).
    """
    start = due_at
    try:
        end = (datetime.fromisoformat(due_at) + timedelta(minutes=1)).isoformat()
    except Exception:
        end = due_at
    variables = {"input": {
        "organizationId": org_id,
        "filter": {
            "channelIds": channel_ids,
            "dueAt": {"start": start, "end": end},
            "status": ["scheduled", "draft", "needs_approval"],
        },
    }}
    data = _graphql(_POSTS_QUERY, variables, token)
    return [e["node"] for e in (data.get("posts", {}).get("edges", []) or [])]


def create_story_reminder(channel_id, media_url, due_at, note, kind, token) -> dict:
    """Schedule an Instagram STORY as a notification reminder.

    schedulingType 'notification' = Buffer pings Deba at the time to post manually
    and add the interactive sticker in-app. `note` carries the sticker prompt so she
    knows what to add. Returns the created post dict.
    """
    asset_key = "video" if kind == "reel" else "image"
    payload = {
        "channelId": channel_id,
        "text": note or "",
        "schedulingType": "notification",
        "mode": "customScheduled",
        "dueAt": due_at,
        "assets": [{asset_key: {"url": media_url}}],
        "metadata": {"instagram": {"type": "story", "shouldShareToFeed": False}},
    }
    result = _graphql(_CREATE_POST, {"input": payload}, token).get("createPost", {})
    if result.get("__typename") == "PostActionSuccess":
        return result.get("post", {})
    raise RuntimeError(result.get("message") or f"Buffer rejected story ({result.get('__typename','unknown')})")


def create_post(channel_id, text, media_url, due_at, kind, token, platform="",
                as_draft=True, opts=None) -> dict:
    """Schedule (or draft) a single post to one Buffer channel. Returns the post dict."""
    variables = {"input": build_create_post_input(
        channel_id, text, media_url, due_at, kind, platform, as_draft, opts)}
    result = _graphql(_CREATE_POST, variables, token).get("createPost", {})
    if result.get("__typename") == "PostActionSuccess":
        return result.get("post", {})
    # Any other union member is an error type carrying a message
    raise RuntimeError(result.get("message") or f"Buffer rejected post ({result.get('__typename','unknown')})")
