"""LLM client factory (OpenRouter) with optional LangSmith tracing."""

from __future__ import annotations

import logging
import os
from functools import lru_cache

from openai import OpenAI

from app.config import get_settings

logger = logging.getLogger(__name__)


def configure_langsmith() -> bool:
    """
    Configure LangSmith from settings.

    Returns True if tracing is active. Requires LANGCHAIN_API_KEY / langchain_api_key;
    without a key, tracing stays off even if LANGCHAIN_TRACING_V2=true.
    """
    settings = get_settings()

    if not settings.langsmith_enabled:
        os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
        logger.info("LangSmith tracing disabled (no LANGCHAIN_API_KEY)")
        return False

    os.environ["LANGCHAIN_TRACING_V2"] = (
        "true" if settings.langchain_tracing_v2 else "false"
    )
    os.environ["LANGCHAIN_ENDPOINT"] = settings.langchain_endpoint
    os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
    os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
    os.environ["LANGSMITH_TRACING"] = os.environ["LANGCHAIN_TRACING_V2"]
    os.environ["LANGSMITH_ENDPOINT"] = settings.langchain_endpoint
    os.environ["LANGSMITH_API_KEY"] = settings.langchain_api_key
    os.environ["LANGSMITH_PROJECT"] = settings.langchain_project

    logger.info(
        "LangSmith tracing enabled (project=%s)",
        settings.langchain_project,
    )
    return True


@lru_cache
def get_llm_client() -> OpenAI:
    """
    OpenAI-compatible client pointed at OpenRouter.

    When LangSmith is configured, wraps the client so chat completions are traced.
    """
    settings = get_settings()
    key = settings.llm_api_key
    if not key or key.startswith("sk-your") or key == "sk-or-v1-your-key-here":
        raise RuntimeError(
            "OPENROUTER_API_KEY is not configured. Set a real key in .env to run analysis."
        )

    client = OpenAI(
        api_key=key,
        base_url=settings.openrouter_base_url,
        default_headers={
            "HTTP-Referer": "https://github.com/traceiq",
            "X-Title": "TraceIQ",
        },
    )

    if settings.langsmith_enabled:
        try:
            from langsmith.wrappers import wrap_openai

            client = wrap_openai(client)
            logger.info("OpenAI client wrapped for LangSmith tracing")
        except ImportError:
            logger.warning(
                "langsmith is not installed; LLM calls will not be traced. "
                "Install langsmith to enable tracing."
            )

    return client
