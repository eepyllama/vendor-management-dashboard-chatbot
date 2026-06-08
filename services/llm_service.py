"""
services/llm_service.py
────────────────────────
Groq LLM service with streaming support.

Provider : Groq (free tier — https://console.groq.com)
Default  : llama-3.1-8b-instant  (fast, generous free limits)
Fallback  : llama-3.1-70b-versatile (better quality, same free tier)

Two call modes
--------------
1. stream_chat()  — yields Server-Sent Event chunks as they arrive.
                    Used by POST /api/chat so the browser receives
                    tokens progressively (replaces the one-shot fetch
                    in the original HTML).

2. complete_chat() — collects the full response and returns it as a
                     string.  Used internally by non-streaming callers
                     (e.g. contract draft generation).

Message format
--------------
Both methods accept a list of dicts:
    [{"role": "user"|"assistant", "content": "..."}]

The system prompt is passed separately and prepended automatically.
"""

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from functools import lru_cache

from groq import AsyncGroq

logger = logging.getLogger(__name__)


class LLMService:
    """
    Async Groq client wrapper.

    Parameters
    ----------
    api_key : str | None
        Groq API key.  Falls back to GROQ_API_KEY env var.
    model : str | None
        Model identifier.  Falls back to LLM_MODEL env var,
        then to "llama-3.1-8b-instant".
    max_tokens : int
        Maximum tokens in the completion.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> None:
        self._api_key = api_key or os.getenv("GROQ_API_KEY", "")
        if not self._api_key:
            raise ValueError(
                "GROQ_API_KEY is not set. "
                "Get a free key at https://console.groq.com"
            )

        self._model = model or os.getenv("LLM_MODEL", "llama-3.1-8b-instant")
        self._max_tokens = max_tokens or int(os.getenv("LLM_MAX_TOKENS", "1024"))
        self._chat_max_tokens = int(os.getenv("CHAT_MAX_TOKENS", "600"))
        self._report_max_tokens = int(os.getenv("REPORT_MAX_TOKENS", "400"))
        self._client = AsyncGroq(api_key=self._api_key)
        logger.info("LLM service ready — model: %s", self._model)

    # ------------------------------------------------------------------
    # Streaming (primary path for the chat endpoint)
    # ------------------------------------------------------------------

    async def stream_chat(
        self,
        messages: list[dict],
        system_prompt: str,
        max_tokens: int | None = None,
        endpoint_source: str = "chat",
    ) -> AsyncIterator[str]:
        """
        Stream a chat completion token by token.

        Yields
        ------
        str
            Each yielded string is a text delta (one or more characters).
            The caller is responsible for formatting these as SSE events.
        """
        # Groq uses the OpenAI message format: system goes in the messages
        # list as the first entry with role="system".
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        limit = max_tokens or self._chat_max_tokens

        try:
            stream = await self._client.chat.completions.create(
                model=self._model,
                messages=full_messages,
                max_tokens=limit,
                temperature=0.3,      # lower = more factual / deterministic
                stream=True,
                extra_body={"stream_options": {"include_usage": True}},
            )
            async for chunk in stream:
                if chunk.choices:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield delta
                if hasattr(chunk, "usage") and chunk.usage is not None:
                    # Log usage statistics
                    from services.metrics_service import get_metrics_service
                    get_metrics_service().log_usage(
                        prompt_tokens=chunk.usage.prompt_tokens,
                        completion_tokens=chunk.usage.completion_tokens,
                        total_tokens=chunk.usage.total_tokens,
                        model_name=self._model,
                        endpoint_source=endpoint_source,
                    )

        except Exception as exc:
            logger.exception("Groq streaming error: %s", exc)
            yield f"\n\n[Error: {exc}]"

    # ------------------------------------------------------------------
    # Non-streaming (used for contract drafts, analysis, etc.)
    # ------------------------------------------------------------------

    async def complete_chat(
        self,
        messages: list[dict],
        system_prompt: str,
        max_tokens: int | None = None,
        endpoint_source: str = "report",
    ) -> str:
        """
        Return the full assistant response as a single string.
        """
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        limit = max_tokens or self._report_max_tokens

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=full_messages,
                max_tokens=limit,
                temperature=0.3,
            )
            if hasattr(response, "usage") and response.usage is not None:
                from services.metrics_service import get_metrics_service
                get_metrics_service().log_usage(
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    total_tokens=response.usage.total_tokens,
                    model_name=self._model,
                    endpoint_source=endpoint_source,
                )
            return response.choices[0].message.content or ""

        except Exception as exc:
            logger.exception("Groq completion error: %s", exc)
            return f"[Error contacting LLM: {exc}]"

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def health_check(self) -> dict:
        """
        Verify the Groq API key is present and the client is configured.

        A real live call is made only if HEALTH_CHECK_LIVE=true is set in
        the environment (useful for staging smoke tests, not for polling).
        """
        if not self._api_key:
            return {"ok": False, "error": "GROQ_API_KEY not set"}

        if os.getenv("HEALTH_CHECK_LIVE", "false").lower() == "true":
            try:
                await self._client.chat.completions.create(
                    model=self._model,
                    messages=[{"role": "user", "content": "ping"}],
                    max_tokens=1,
                )
                return {"ok": True, "model": self._model}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        # Default: assume ok if key is present — confirmed on first real use
        return {"ok": True, "model": self._model}

# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_llm_service() -> LLMService:
    """
    Return the shared LLMService instance.
    Raises ValueError if GROQ_API_KEY is not set.
    """
    return LLMService()
