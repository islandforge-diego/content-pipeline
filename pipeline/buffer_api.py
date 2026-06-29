"""buffer_api.py — thin client for the Buffer GraphQL API.

Schema verified against Buffer's live GraphQL (api.buffer.com/graphql). Used by
onboarding (list channels) and publishing (create posts).

Auth: a Buffer access token (BUFFER_TOKEN) sent as a Bearer header. Create one at
https://publish.buffer.com/settings/api.
"""
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


def _platform_metadata(platform, kind, text, yt_category="22"):
    """Per-network metadata Buffer requires. Returns a PostInputMetaData dict or None.

    - Instagram/Facebook need a post type (video -> reel, image -> post).
    - Instagram also needs shouldShareToFeed.
    - YouTube needs a title and a category id.
    """
    post_type = "reel" if kind == "reel" else "post"
    if platform == "instagram":
        return {"instagram": {"type": post_type, "shouldShareToFeed": True}}
    if platform == "facebook":
        return {"facebook": {"type": post_type}}
    if platform == "youtube":
        # First non-empty line of the caption makes a sensible Short title (<=95 chars).
        first = next((ln.strip() for ln in (text or "").splitlines() if ln.strip()), "New video")
        return {"youtube": {"title": first[:95], "categoryId": yt_category}}
    return None  # tiktok / linkedin need no extra metadata


def build_create_post_input(channel_id, text, media_url, due_at, kind, platform="",
                            as_draft=True, yt_category="22"):
    """Build the CreatePostInput payload (pure; unit-tested separately).

    - schedulingType 'automatic' = Buffer publishes for you (vs 'notification' reminders).
    - mode 'customScheduled' + dueAt = scheduled for a specific time.
    - assets use Buffer's @oneOf shape: {image|video: {url}}.
    - metadata carries per-network requirements (post type, YouTube title/category).
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
    meta = _platform_metadata(platform, kind, text, yt_category)
    if meta:
        payload["metadata"] = meta
    return payload


def create_post(channel_id, text, media_url, due_at, kind, token, platform="",
                as_draft=True, yt_category="22") -> dict:
    """Schedule (or draft) a single post to one Buffer channel. Returns the post dict."""
    variables = {"input": build_create_post_input(
        channel_id, text, media_url, due_at, kind, platform, as_draft, yt_category)}
    result = _graphql(_CREATE_POST, variables, token).get("createPost", {})
    if result.get("__typename") == "PostActionSuccess":
        return result.get("post", {})
    # Any other union member is an error type carrying a message
    raise RuntimeError(result.get("message") or f"Buffer rejected post ({result.get('__typename','unknown')})")
