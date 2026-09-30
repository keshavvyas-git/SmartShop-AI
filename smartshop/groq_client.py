"""Small, server-side client for Groq Chat Completions and browser search."""

from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import urlparse

import requests
import streamlit as st


API_URL = "https://api.groq.com/openai/v1/chat/completions"
MAX_HISTORY_MESSAGES = 6
MAX_MESSAGE_LENGTH = 1400
TRUSTED_SOURCE_DOMAINS = {
    # Official product makers and component vendors.
    "acer.com", "amd.com", "apple.com", "asus.com", "canon-europe.com",
    "dell.com", "hp.com", "intel.com", "lenovo.com", "lg.com", "logitech.com",
    "microsoft.com", "mi.com", "motorola.com", "nvidia.com", "oneplus.com",
    "oppo.com", "realme.com", "samsung.com", "sony.com", "vivo.com", "xiaomi.com",
    # Established independent review publications.
    "cnet.com", "consumerreports.org", "digitaltrends.com", "gsmarena.com",
    "nytimes.com", "notebookcheck.net", "pcmag.com", "rtings.com", "techradar.com",
    "theverge.com", "tomsguide.com", "trustedreviews.com", "wired.com",
    # Direct listings from established Indian retailers.
    "croma.com", "flipkart.com", "reliancedigital.in", "tatacliq.com", "vijaysales.com",
}
MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")
PLAIN_URL = re.compile(r"https?://[^\s)\]>]+", re.IGNORECASE)

SYSTEM_PROMPT = """You are Ani, a concise shopping assistant. Help with shopping, product discovery, comparisons, buying advice, and questions that directly help someone choose or use a product. Politely decline unrelated requests in one short sentence and invite a shopping question.

Use India and INR as defaults. Interpret shorthand budgets such as 30k as ₹30,000 unless another market is specified. Keep answers concise (aim for 140 words, excluding links). Ask one short follow-up if an essential budget, region, or use case is missing.

Research current product facts with browser search. Never invent a product, price, feature, review, or source. Prefer official manufacturer specifications and warranty pages, government or standards sources, established independent product-testing publications, and direct listings from well-known authorized retailers. Verify exact model, variant, and country; do not rely on search snippets alone or use forums, social posts, anonymous reviews, affiliate comparison blogs, or unknown shops. Link trusted sources inline near the claims. Never emit opaque citation markers. If trusted sources do not support a reliable price or three distinct options, state that and provide fewer supported choices.

When enough details are available, return a short intro if useful, then one Markdown comparison table with columns Product, Approx. price, Why it fits, Main trade-off, with at most three supported rows. Follow it with one concise **Recommendation:** sentence and a short **In simple terms:** paragraph. Avoid jargon and keep the answer focused. Do not emit raw HTML or JSON."""


def _setting(name: str, default: str = "") -> str:
    """Read a local/host environment variable or a Community Cloud secret."""
    value = os.getenv(name)
    if value:
        return value
    try:
        secret = st.secrets.get(name, default)
    except Exception:
        # Local runs without a secrets.toml file are expected to use .env.
        return default
    return str(secret) if secret is not None else default


class AssistantError(Exception):
    """Safe, user-facing errors from validation or the upstream AI service."""


def _normalize_history(history: list[dict[str, Any]]) -> list[dict[str, str]]:
    if not isinstance(history, list):
        raise AssistantError("Send a message to start shopping with Ani.")

    messages = []
    for item in history[-MAX_HISTORY_MESSAGES:]:
        if not isinstance(item, dict) or item.get("role") not in {"user", "assistant"}:
            continue
        content = item.get("content")
        if isinstance(content, str) and content.strip():
            messages.append({"role": item["role"], "content": content.strip()[:MAX_MESSAGE_LENGTH]})

    if not messages or messages[-1]["role"] != "user":
        raise AssistantError("Send a message to start shopping with Ani.")
    return messages


def _collect_sources(message: dict[str, Any]) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    seen: set[str] = set()
    tools = message.get("executed_tools", [])
    if not isinstance(tools, list):
        return found

    for tool in tools:
        search_results = tool.get("search_results", {}) if isinstance(tool, dict) else {}
        results = search_results.get("results", []) if isinstance(search_results, dict) else []
        if not isinstance(results, list):
            continue
        for result in results:
            if not isinstance(result, dict):
                continue
            url = result.get("url", "")
            title = result.get("title", "Source")
            if not isinstance(url, str) or not isinstance(title, str):
                continue
            if not _is_trusted_url(url) or url in seen:
                continue
            seen.add(url)
            found.append({"title": title.strip()[:180] or "Source", "url": url})
            if len(found) >= 15:
                return found
    return found


def _is_trusted_url(url: str) -> bool:
    """Allow HTTPS links from explicitly trusted source domains only."""
    if len(url) > 2048:
        return False
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
    except ValueError:
        return False
    if parsed.scheme != "https" or not hostname or parsed.username or parsed.password:
        return False
    hostname = hostname.lower().rstrip(".")
    if hostname.endswith((".gov", ".gov.in", ".nic.in", ".edu")):
        return True
    return any(
        hostname == domain or hostname.endswith(f".{domain}")
        for domain in TRUSTED_SOURCE_DOMAINS
    )


def _clean_answer_links(answer: str) -> str:
    """Remove unsupported links from generated Markdown before rendering."""
    answer = MARKDOWN_LINK.sub(
        lambda match: match.group(0) if _is_trusted_url(match.group(2)) else match.group(1),
        answer,
    )
    return PLAIN_URL.sub(
        lambda match: match.group(0) if _is_trusted_url(match.group(0)) else "",
        answer,
    )


def get_assistant_reply(history: list[dict[str, Any]]) -> dict[str, Any]:
    api_key = _setting("GROQ_API_KEY").strip()
    if not api_key:
        raise AssistantError("Ani needs a Groq API key. Add GROQ_API_KEY to your environment settings.")

    model = _setting("GROQ_MODEL", "openai/gpt-oss-120b")
    try:
        max_tokens = int(_setting("GROQ_MAX_COMPLETION_TOKENS", "900"))
    except ValueError:
        max_tokens = 900
    max_tokens = min(max(max_tokens, 256), 1200)

    payload = {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}, *_normalize_history(history)],
        "tools": [{"type": "browser_search"}],
        "tool_choice": "auto",
        "temperature": 0.2,
        "max_completion_tokens": max_tokens,
    }

    for attempt in range(2):
        try:
            response = requests.post(
                API_URL,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=(10, 90),
            )
        except requests.Timeout as error:
            raise AssistantError("That research took too long. Try a more focused request.") from error
        except requests.RequestException as error:
            raise AssistantError("Ani could not reach Groq just now. Check your connection and try again.") from error

        try:
            data = response.json()
        except requests.JSONDecodeError:
            data = {}
        if response.ok:
            choices = data.get("choices", []) if isinstance(data, dict) else []
            first_choice = choices[0] if isinstance(choices, list) and choices else {}
            raw_message = first_choice.get("message", {}) if isinstance(first_choice, dict) else {}
            message = raw_message if isinstance(raw_message, dict) else {}
            answer = message.get("content")
            if isinstance(answer, str) and answer.strip():
                clean_answer = re.sub(
                    r"\s*(?:[【〖]\s*\d+\s*†\s*(?:L[\d–-]+|source)\s*[】〗]|\[\s*\d+\s*†\s*L[\d–-]+\s*\])",
                    "",
                    _clean_answer_links(answer.strip()),
                    flags=re.IGNORECASE,
                )
                return {"answer": clean_answer, "sources": _collect_sources(message)}
            raise AssistantError("Ani did not receive a usable answer. Please try again.")

        error_data = data.get("error", {}) if isinstance(data, dict) else {}
        upstream_message = error_data.get("message", "") if isinstance(error_data, dict) else ""
        if response.status_code == 400 and attempt == 0 and any(
            phrase in upstream_message.lower() for phrase in ("parsing failed", "failed_generation")
        ):
            payload["temperature"] = 0.1
            continue
        if response.status_code in {401, 403}:
            raise AssistantError("Groq could not authenticate the server API key. Check GROQ_API_KEY.")
        if response.status_code == 429:
            raise AssistantError("Ani is busy right now. Wait a moment and try again.")
        raise AssistantError("Ani could not complete that research. Please try again in a moment.")

    raise AssistantError("Ani could not complete that request. Please try again.")
