"""
api/routes/chat.py
───────────────────
POST /api/chat — run the RAG pipeline and stream the response as SSE.
Supports Report Mode validation, auto-regeneration retry, and history pruning.
"""

import logging #used for debugging and monitoring 
import os #used to read environment variables
import asyncio #used to add small delays between streaming chunks for a smoother real-time response experience for the client
from fastapi import APIRouter, Depends, HTTPException #used to define API routes, handle dependencies, and manage HTTP exceptions in the chat endpoint
from fastapi.responses import StreamingResponse #used to stream the response from the RAG pipeline back as Server-Sent Events (SSE)
from pydantic import BaseModel, Field #used to define data models for request validation and structured data handling in the chat endpoint
from api.dependencies import get_pipeline
from rag.pipeline import RAGPipeline
from prompts.report import ReportMode

logger = logging.getLogger(__name__)
router = APIRouter()


class Message(BaseModel):
    role: str        # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    history: list[Message] = Field(default_factory=list)
    mode: ReportMode | None = None


def validate_report_table(text: str, mode: ReportMode) -> bool:
    """
    Validate that the report text contains a valid markdown table with correct headers.
    If mode is CUSTOM or the text indicates unavailable documents, return True.
    """
    cleaned = text.strip()
    if cleaned == "Not available in uploaded documents.":
        return True

    if mode == ReportMode.CUSTOM:
        return len(cleaned) > 0

    expected_headers = {
        ReportMode.WEEKLY_SUMMARY: ["Employee", "Event", "Date", "Client"],
        ReportMode.COMPLIANCE: ["Contractor", "Document", "Expiry Date", "Status"],
        ReportMode.VENDOR: ["Vendor", "Status", "Notes"],
        ReportMode.CONTRACTOR: ["Contractor", "Role", "Status", "Notes"]
    }

    headers = expected_headers.get(mode)
    if not headers:
        return True

    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    found_headers = False
    found_separator = False

    for i, line in enumerate(lines):
        if not (line.startswith("|") and line.endswith("|")):
            continue

        cols = [col.strip() for col in line.split("|")[1:-1]]
        if len(cols) == len(headers) and all(h.lower() == c.lower() for h, c in zip(headers, cols)):
            found_headers = True
            # Check if next line is a separator line (e.g. |---|---|)
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                if (
                    next_line.startswith("|")
                    and next_line.endswith("|")
                    and "-" in next_line
                ):
                    sep_cols = [col.strip() for col in next_line.split("|")[1:-1]]
                    if all(
                        all(char in "-:" for char in col) and len(col) > 0
                        for col in sep_cols
                    ):
                        found_separator = True
            break

    return found_headers and found_separator


@router.post("/chat")
async def chat(
    request: ChatRequest,
    pipeline: RAGPipeline = Depends(get_pipeline),
):
    """
    Stream a RAG-powered chat response as Server-Sent Events.
    For standard chat: Streams raw LLM chunks dynamically.
    For reports: Buffers LLM completion, validates Markdown schema,
                 auto-regenerates on failure, then streams the result to client.
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query must not be empty.")

    raw_history = [m.model_dump() for m in request.history]

    # History pruning (Phase 7)
    if request.mode:
        # Report mode: clear history completely
        history = []
    else:
        # Chat mode: keep last 2 turns (last 4 messages) to save token footprint
        history = raw_history[-4:]

    async def event_stream():
        try:
            if request.mode:
                # Report Mode: Buffer, Validate, and Stream
                report_max_tokens = int(os.getenv("REPORT_MAX_TOKENS", "400"))
                
                # First generation attempt
                res = await pipeline.complete(
                    query=request.query,
                    history=history,
                    mode=request.mode,
                    max_tokens=report_max_tokens,
                )
                answer = res["answer"]
                sources = res["sources"]

                # Validate
                valid = validate_report_table(answer, request.mode)
                if not valid:
                    logger.warning("Report validation failed on first attempt. Retrying...")
                    
                    expected_headers = {
                        ReportMode.WEEKLY_SUMMARY: ["Employee", "Event", "Date", "Client"],
                        ReportMode.COMPLIANCE: ["Contractor", "Document", "Expiry Date", "Status"],
                        ReportMode.VENDOR: ["Vendor", "Status", "Notes"],
                        ReportMode.CONTRACTOR: ["Contractor", "Role", "Status", "Notes"]
                    }
                    headers = expected_headers.get(request.mode, [])
                    
                    retry_prompt = (
                        "The previous output was invalid. Please regenerate the report.\n"
                        f"Enforce the required table structure and columns: {', '.join(headers)}.\n"
                        "Do not include any introduction, summary, recommendations, commentary, or text outside the table.\n"
                        "Output ONLY the markdown table. If the information is unavailable, output 'Not available in uploaded documents.'"
                    )
                    
                    retry_history = history + [
                        {"role": "user", "content": request.query},
                        {"role": "assistant", "content": answer},
                        {"role": "user", "content": retry_prompt}
                    ]
                    
                    # Second attempt
                    res = await pipeline.complete(
                        query=request.query,
                        history=retry_history,
                        mode=request.mode,
                        max_tokens=report_max_tokens,
                    )
                    answer = res["answer"]
                    sources = res["sources"]
                    
                    # Final check
                    valid = validate_report_table(answer, request.mode)
                    if not valid:
                        logger.error("Report validation failed on second attempt. Aborting.")
                        yield "data: [ERROR] Report generation failed.  Please try again or rephrase your request.\n\n"
                        yield "data: [DONE]\n\n"
                        return

                # Stream the validated buffered text in chunks to client
                chunk_size = 30
                for i in range(0, len(answer), chunk_size):
                    chunk = answer[i : i + chunk_size]
                    yield f"data: {chunk.replace('\n', '\\n')}\n\n"
                    await asyncio.sleep(0.01) # Small delay to mimic smooth streaming

                if sources:
                    sources_payload = "|".join(sources)
                    yield f"data: [SOURCES] {sources_payload}\n\n"

                yield "data: [DONE]\n\n"

            else:
                # Chat Mode: Standard stream (Phase 8 max tokens limit)
                chat_max_tokens = int(os.getenv("CHAT_MAX_TOKENS", "600"))
                async for chunk in pipeline.stream(
                    query=request.query,
                    history=history,
                    mode=None, #streams tokens directly without report formatting
                    max_tokens=chat_max_tokens,
                ):
                    yield chunk

        except Exception as exc:
            logger.exception("Stream error: %s", exc)
            yield "data: [ERROR] An internal error occurred. Please try again.\\n\\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",      # disable Nginx buffering
        },
    )
