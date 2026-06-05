"""
rag/pipeline.py
────────────────
The RAG pipeline: the single entry point that the chat API route calls.

It orchestrates:
  1. Retrieval  — Retriever.retrieve(query)  → RetrievalResult
  2. Prompting  — build_system_prompt(context) → system string
  3. Generation — LLMService.stream_chat(messages, system) → token stream

The pipeline returns an async generator that yields SSE-formatted strings.
The API route consumes this generator directly and forwards it to the browser.

SSE format
----------
Each yielded item is one of:

  data: <token text>\n\n           — a streamed token chunk
  data: [SOURCES] src1|src2\n\n   — sent once at the end, listing cited docs
  data: [DONE]\n\n                 — signals stream completion to the frontend

The frontend JavaScript reads these events and:
  - Appends token chunks to the current bot message bubble
  - Parses [SOURCES] to build the citation pills
  - Hides the typing indicator on [DONE]
"""

import json
import logging
from collections.abc import AsyncIterator

from prompts.system import build_system_prompt, RAG_CONTEXT_TMPL
from prompts.report import ReportMode, get_report_prompt
from rag.retriever import Retriever
from services.llm_service import LLMService

logger = logging.getLogger(__name__)


class RAGPipeline:
    """
    Wires retriever + LLM into a streaming RAG chain.

    Parameters
    ----------
    retriever : Retriever
    llm       : LLMService
    """

    def __init__(self, retriever: Retriever, llm: LLMService) -> None:
        self._retriever = retriever
        self._llm = llm

    # ------------------------------------------------------------------
    # Primary entry point
    # ------------------------------------------------------------------

    async def stream(
        self,
        query: str,
        history: list[dict],
        mode: ReportMode | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """
        Run the full RAG pipeline and stream the response as SSE events.

        Parameters
        ----------
        query   : the user's latest message (plain text)
        history : list of prior turns in OpenAI message format
                  [{"role": "user"|"assistant", "content": "..."}]
                  Should NOT include the current query — it is appended here.
        mode    : optional ReportMode for report generation prompt templates
        max_tokens: dynamic max tokens limit for the response

        Yields
        ------
        str
            SSE-formatted event strings ready to be written to the
            HTTP response body.
        """
        logger.info("RAG pipeline — query: %.80s…", query)

        # ------------------------------------------------------------------
        # 1. Retrieve relevant chunks
        # ------------------------------------------------------------------
        retrieval = self._retriever.retrieve(query)

        if retrieval.context:
            logger.info(
                "Retrieved %d chunks from: %s",
                len(retrieval.chunks),
                ", ".join(retrieval.sources),
            )
        else:
            logger.info("No relevant chunks found — answering from platform data")

        # ------------------------------------------------------------------
        # 2. Build system prompt (platform context + optional RAG context)
        # ------------------------------------------------------------------
        if mode:
            from prompts.system import PLATFORM_CONTEXT
            system_prompt = PLATFORM_CONTEXT.strip()
            if retrieval.context:
                system_prompt += "\n\n" + RAG_CONTEXT_TMPL.format(
                    context=retrieval.context.strip()
                )
            system_prompt += "\n\n" + get_report_prompt(mode)
        else:
            system_prompt = build_system_prompt(
                retrieved_context=retrieval.context or None
            )

        # ------------------------------------------------------------------
        # 3. Assemble message list (history + current query)
        # ------------------------------------------------------------------
        messages = _trim_history(history) + [
            {"role": "user", "content": query}
        ]

        # ------------------------------------------------------------------
        # 4. Stream LLM response token by token
        # ------------------------------------------------------------------
        endpoint_source = "report" if mode else "chat"
        try:
            async for token in self._llm.stream_chat(
                messages=messages,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                endpoint_source=endpoint_source,
            ):
                # Escape the token for safe SSE transmission
                yield _sse(token)

        except Exception as exc:
            logger.exception("LLM streaming failed: %s", exc)
            yield _sse(f"\n\n⚠️ An error occurred: {exc}")

        # ------------------------------------------------------------------
        # 5. Send source citations (if any)
        # ------------------------------------------------------------------
        if retrieval.sources:
            sources_payload = "|".join(retrieval.sources)
            yield _sse(f"[SOURCES] {sources_payload}")

        # ------------------------------------------------------------------
        # 6. Signal completion
        # ------------------------------------------------------------------
        yield _sse("[DONE]")

    # ------------------------------------------------------------------
    # Non-streaming variant (for internal use / testing)
    # ------------------------------------------------------------------

    async def complete(
        self,
        query: str,
        history: list[dict],
        mode: ReportMode | None = None,
        max_tokens: int | None = None,
    ) -> dict:
        """
        Run the pipeline without streaming and return the full response.

        Returns
        -------
        dict with keys:
          - answer   : str
          - sources  : list[str]
          - chunks   : int
        """
        retrieval = self._retriever.retrieve(query)
        if mode:
            from prompts.system import PLATFORM_CONTEXT
            system_prompt = PLATFORM_CONTEXT.strip()
            if retrieval.context:
                system_prompt += "\n\n" + RAG_CONTEXT_TMPL.format(
                    context=retrieval.context.strip()
                )
            system_prompt += "\n\n" + get_report_prompt(mode)
        else:
            system_prompt = build_system_prompt(
                retrieved_context=retrieval.context or None
            )
        messages = _trim_history(history) + [
            {"role": "user", "content": query}
        ]
        endpoint_source = "report" if mode else "chat"
        answer = await self._llm.complete_chat(
            messages=messages,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            endpoint_source=endpoint_source,
        )
        return {
            "answer": answer,
            "sources": retrieval.sources,
            "chunks": len(retrieval.chunks),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sse(data: str) -> str:
    """
    Wrap a string in the SSE event format.
    Newlines inside the data are escaped so they don't break the frame.
    """
    # Replace literal newlines with the SSE continuation marker
    safe = data.replace("\n", "\\n")
    return f"data: {safe}\n\n"


def _trim_history(history: list[dict], max_turns: int = 10) -> list[dict]:
    """
    Keep only the most recent max_turns * 2 messages (user + assistant pairs)
    to avoid exceeding the model's context window.
    """
    # Each turn is 2 messages; keep the last max_turns pairs
    limit = max_turns * 2
    return history[-limit:] if len(history) > limit else history
