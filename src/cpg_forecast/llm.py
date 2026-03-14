"""Cloudflare Workers AI client for chat with function calling."""

from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_MODEL = "@hf/nousresearch/hermes-2-pro-mistral-7b"
BASE_URL = "https://api.cloudflare.com/client/v4/accounts"


def chat(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    *,
    model: str | None = None,
    account_id: str | None = None,
    api_token: str | None = None,
) -> dict[str, Any]:
    """Send chat request to Cloudflare Workers AI with optional tools.

    Args:
        messages: Chat messages in OpenAI format (role, content).
        tools: Tool definitions in OpenAI schema format.
        model: Model name (default: hermes-2-pro-mistral-7b).
        account_id: Cloudflare account ID (default: CLOUDFLARE_ACCOUNT_ID env).
        api_token: Cloudflare API token (default: CLOUDFLARE_API_TOKEN env).

    Returns:
        Dict with either "response" (str) or "tool_calls" (list).

    Raises:
        ValueError: If credentials are missing.
        httpx.HTTPStatusError: On API errors.
    """
    account_id = account_id or os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    api_token = api_token or os.environ.get("CLOUDFLARE_API_TOKEN")
    if not account_id or not api_token:
        raise ValueError(
            "CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN must be set"
        )

    model = model or DEFAULT_MODEL
    url = f"{BASE_URL}/{account_id}/ai/run/{model}"

    payload: dict[str, Any] = {"messages": messages}
    if tools:
        payload["tools"] = tools

    with httpx.Client(timeout=60.0) as client:
        response = client.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {api_token}"},
        )
        response.raise_for_status()
        data = response.json()

    if not data.get("success", True):
        errors = data.get("errors", [])
        raise ValueError(f"Cloudflare API error: {errors}")

    result = data.get("result", data)
    return result


def is_configured() -> bool:
    """Check if Cloudflare credentials are configured."""
    return bool(
        os.environ.get("CLOUDFLARE_ACCOUNT_ID")
        and os.environ.get("CLOUDFLARE_API_TOKEN")
    )
