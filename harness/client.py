"""Talking to an endpoint: which one, as which provider, and what it costs.

Where this sits: `bench.py` builds one client per run; `replay.py` uses it to
make calls; `estimate.py` uses `endpoint_info()` to price a run before it
starts.

Two facts shape this file:

1. Every target speaks the OpenAI chat-completions protocol. OpenRouter does,
   and so does a vLLM or SGLang server you run yourself. So one client class
   (the official `openai` SDK) reaches all of them; only `base_url` changes.

2. On OpenRouter, one model id can be served by many providers on different
   hardware. The request can pin a provider with
   `extra_body={"provider": {"only": ["cerebras"], "allow_fallbacks": False}}`.
   That is how "same model, different silicon" becomes one flag. When the
   provider is not pinned, OpenRouter picks by its own price-weighted routing
   and the report says "auto".

Easy to get wrong: OpenRouter's per-call cost arrives in the *last* streamed
chunk's `usage` field. Reading usage before the stream ends gives nothing.
`replay.py` handles that; this file only knows how to build the request.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import httpx
from openai import OpenAI

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


@dataclass
class Target:
    """One thing to bench: a model on an endpoint, optionally pinned to a provider."""

    model: str
    provider: str = "auto"  # an OpenRouter provider slug, or "auto", or "local"
    base_url: str = OPENROUTER_BASE_URL

    @property
    def label(self) -> str:
        return f"{self.model} @ {self.provider}"


@dataclass
class EndpointInfo:
    """What OpenRouter says about one provider's serving of a model.

    Prices are USD per token (not per million), as the API returns them.
    Quantization is the provider's own declaration; "unknown" is a real answer
    and goes into the conditions block as such.
    """

    provider: str  # display name, lower-cased, e.g. "cerebras"
    slug: str  # the routing slug OpenRouter accepts in provider.only, e.g. "cerebras"
    quantization: str
    prompt_price_per_token: float
    completion_price_per_token: float
    context_length: int | None


def make_client(base_url: str) -> OpenAI:
    """Build an SDK client for the endpoint. Reads the matching key from the environment.

    OpenRouter: OPENROUTER_API_KEY. Anything else: LOCAL_API_KEY, falling back
    to a placeholder because local servers usually do not check the key.
    """
    if base_url == OPENROUTER_BASE_URL:
        key = os.environ.get("OPENROUTER_API_KEY", "")
        if not key:
            raise RuntimeError("OPENROUTER_API_KEY is not set (copy .env.example to .env)")
    else:
        key = os.environ.get("LOCAL_API_KEY") or "not-needed"
    # max_retries covers transient failures; the 429 backoff in replay.py covers
    # per-minute rate limits, which need longer waits than the SDK's default.
    return OpenAI(api_key=key, base_url=base_url, timeout=120.0, max_retries=2)


def request_extras(target: Target, session_id: str, reasoning: str = "low") -> tuple[dict, dict]:
    """Return (extra_body, extra_headers) for one request to this target.

    Provider pinning goes in the body, so OpenRouter routes only to that
    provider and never silently falls back to another one (a fallback would
    put a different chip's numbers under the wrong label). The session id goes
    in a header so a router that keeps KV-cache locality per session can use
    it, the same way MLPerf sends X-Session-ID.

    `reasoning` controls how much a reasoning model thinks before answering:
    "low", "medium", "high" set an effort; "off" asks the model not to reason
    at all (for models with a thinking toggle, such as Qwen3.x); "none" sends
    nothing and takes the model's default. OpenRouter maps these to each
    model's own knob and ignores them for models without one. Some models
    honour "off" but not "low", which is why "off" exists: the fixture run
    showed Qwen3.6 spending every output token thinking and emitting no answer
    at effort low. The choice is a condition and the report records it.
    """
    extra_body: dict = {}
    if target.base_url == OPENROUTER_BASE_URL and target.provider not in ("auto", "local"):
        extra_body["provider"] = {"only": [target.provider], "allow_fallbacks": False}
    if reasoning == "off":
        extra_body["reasoning"] = {"enabled": False}
    elif reasoning != "none":
        extra_body["reasoning"] = {"effort": reasoning}
    extra_headers = {
        "X-Session-ID": session_id,
        "HTTP-Referer": "https://github.com/antje/bakeoff",
        "X-Title": "bakeoff",
    }
    return extra_body, extra_headers


def endpoint_info(model: str) -> list[EndpointInfo]:
    """Ask OpenRouter which providers serve this model today, at what price and quantization.

    Public endpoint, no key required. Used for the pre-run cost estimate and
    for the conditions block. Returns an empty list when the model is unknown
    or the network is down; callers treat that as "conditions unknown", not as
    an error, because the bench itself can still run.
    """
    url = f"{OPENROUTER_BASE_URL}/models/{model}/endpoints"
    try:
        response = httpx.get(url, timeout=15.0)
        response.raise_for_status()
    except httpx.HTTPError:
        return []
    endpoints = response.json().get("data", {}).get("endpoints", [])
    info: list[EndpointInfo] = []
    for endpoint in endpoints:
        pricing = endpoint.get("pricing", {})
        # The tag looks like "cerebras/fp16"; the part before the slash is the
        # routing slug that provider.only accepts.
        tag = str(endpoint.get("tag") or "")
        info.append(
            EndpointInfo(
                provider=str(endpoint.get("provider_name", "")).lower(),
                slug=tag.split("/")[0] if tag else str(endpoint.get("provider_name", "")).lower(),
                quantization=str(endpoint.get("quantization") or "unknown"),
                prompt_price_per_token=float(pricing.get("prompt", 0) or 0),
                completion_price_per_token=float(pricing.get("completion", 0) or 0),
                context_length=endpoint.get("context_length"),
            )
        )
    return info


def find_endpoint(infos: list[EndpointInfo], provider: str) -> EndpointInfo | None:
    """Pick the EndpointInfo for a provider slug, matching loosely on name."""
    wanted = provider.lower()
    for info in infos:
        if wanted in (info.slug, info.provider):
            return info
    for info in infos:
        if wanted in info.provider or info.provider in wanted:
            return info
    return None
