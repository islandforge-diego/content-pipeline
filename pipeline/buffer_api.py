"""buffer_api.py — thin client for the Buffer GraphQL API.

Centralizes Buffer calls used by both onboarding (list channels) and publishing
(create posts). The GraphQL endpoint and mutation shapes are based on Buffer's
current public API; if Buffer changes its schema, introspect with:

    POST https://api.buffer.com/graphql
    {"query": "{ __schema { queryType { fields { name } } } }"}

All functions take an explicit access token (from BUFFER_TOKEN) so nothing here
depends on environment globals.
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


_CHANNELS_QUERY = """
query Channels($organizationId: String) {
  channels(input: { organizationId: $organizationId }) {
    id
    service
    name
    serviceUsername
    serviceType
  }
}
"""


def list_channels(token: str, org_id: str = None) -> list:
    """Return a list of channels for the organization.

    Each item: {id, service, name, serviceUsername, serviceType}
    'service' is the platform (facebook, instagram, tiktok, linkedin, youtube).
    """
    data = _graphql(_CHANNELS_QUERY, {"organizationId": org_id}, token)
    return data.get("channels", []) or []


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


def create_post(channel_id: str, text: str, media_url: str, due_at: str, kind: str, token: str) -> dict:
    """Schedule a single post to one Buffer channel. Returns the created post dict."""
    asset_type = "VIDEO" if kind == "reel" else "IMAGE"
    variables = {
        "input": {
            "channelId": channel_id,
            "text": text,
            "dueAt": due_at,
            "assets": [{"type": asset_type, "url": media_url}],
        }
    }
    result = _graphql(_CREATE_POST, variables, token).get("createPost", {})
    if "message" in result:
        raise RuntimeError(f"Buffer rejected post: {result['message']}")
    return result.get("post", {})
