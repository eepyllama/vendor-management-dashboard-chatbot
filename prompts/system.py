"""
prompts/system.py
─────────────────
All prompt templates for the VendorIQ RAG assistant.

Structure
---------
PLATFORM_CONTEXT   — static knowledge about the platform data (vendors,
                     contractors, contracts, clients). Mirrors the
                     PLATFORM_CONTEXT constant that was hard-coded in the
                     frontend HTML, now lives server-side only.

RAG_CONTEXT_TMPL   — injected when vector retrieval returns results.
                     Wraps the retrieved chunks in clear XML-style
                     delimiters so the LLM knows exactly where retrieved
                     context starts and ends.

build_system_prompt() — assembles the final system prompt that is sent
                        as the `system` message in every chat request.
"""

# ---------------------------------------------------------------------------
# Static platform knowledge
# ---------------------------------------------------------------------------

PLATFORM_CONTEXT = """You are the VendorIQ AI Assistant embedded in a vendor management platform.

## Platform Snapshot
- Contractors: 42 active. Key: Ananya, Carlos, Raj, Priya, Sophie, Lena.
- Vendors: StaffBridge (98), TalentPro (87), DevForce (83), GlobalStaff (71), PeakHire (65).
- Clients: TechCorp, FinServ, HealthNet, RetailCo, BankGroup, LogisCo.
- Critical Contracts: CTR-0088 (expires 12 days), CTR-0091 (19 days), CTR-0085 (27 days).
- KPIs: Utilization 78.4%, Revenue $1.74M, 7 open positions.

## Rules
- Be extremely concise, structured, and professional.
- Format responses with markdown.
- Cite the source document.
- Do not repeat the user's question.
"""

# ---------------------------------------------------------------------------
# RAG context injection template
# ---------------------------------------------------------------------------

RAG_CONTEXT_TMPL = """
## Retrieved document context
The following excerpts were retrieved from indexed documents and are
directly relevant to the user's question. Prioritise this information
when forming your answer and cite the source filename.

{context}

## End of retrieved context
"""

# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_system_prompt(retrieved_context: str | None = None) -> str:
    """
    Assemble the full system prompt.

    Parameters
    ----------
    retrieved_context : str | None
        Pre-formatted string of retrieved chunks produced by the RAG
        retriever.  Pass None (or empty string) when no documents are
        indexed or no relevant chunks were found — the assistant will
        answer from platform knowledge only.

    Returns
    -------
    str
        The complete system prompt ready to be sent as the `system`
        parameter in a chat completion request.
    """
    if retrieved_context and retrieved_context.strip():
        # RAG mode: Omit the detailed platform snapshot to save tokens
        prompt = (
            "You are the VendorIQ AI Assistant.\n"
            "Rules:\n"
            "- Answer strictly based on the retrieved document context below.\n"
            "- Provide a clear, comprehensive, and structured answer that completely addresses all details requested in the question.\n"
            "- Cite the source document.\n"
            "- Do not hallucinate or assume facts.\n"
        )
        prompt += "\n\n" + RAG_CONTEXT_TMPL.format(
            context=retrieved_context.strip()
        )
    else:
        prompt = PLATFORM_CONTEXT.strip()

    return prompt
