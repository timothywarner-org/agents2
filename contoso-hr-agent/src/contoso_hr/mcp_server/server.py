"""
Contoso HR Agent — FastMCP 2 MCP Server.

Demonstrates all five MCP primitives with domain-relevant examples.

Transport: stdio (MCP Inspector) or SSE on port 8091.
  stdio:  npx @modelcontextprotocol/inspector uv run hr-mcp --stdio
  SSE:    uv run hr-mcp  →  http://localhost:8091/sse

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PRIMITIVE 1 — TOOLS  (server-side functions the LLM can call)
  get_candidate(candidate_id)          — full EvaluationResult for one candidate
  list_candidates(limit, decision)     — recent evaluations, optional filter
  trigger_resume_evaluation(text, fn)  — run full LangGraph + CrewAI pipeline
  query_policy(question)               — ChromaDB semantic search
  generate_eval_summary(candidate_id)  — sampling: LLM-written exec summary
  confirm_and_evaluate(resume_text)    — elicitation: confirm before pipeline run

PRIMITIVE 2 — RESOURCES  (data the LLM can read, static + parameterized)
  Static:
    schema://candidate                 — EvaluationResult JSON schema
    stats://evaluations                — aggregate disposition counts
    samples://resumes                  — list of sample resume files
    config://settings                  — current app config (no secrets)
  Parameterized templates:
    candidate://{candidate_id}         — one candidate as formatted markdown
    policy://{topic}                   — policy chunks for a topic keyword

PRIMITIVE 3 — PROMPTS  (reusable message templates)
  evaluate_resume(resume_text, role)   — multi-message trainer eval prompt
  policy_query(question)               — structured policy Q&A prompt
  disposition_review(candidate_id)     — fetch + format candidate for review

PRIMITIVE 4 — SAMPLING  (server asks the LLM to generate text)
  Used in: generate_eval_summary tool
  ctx.sample() sends candidate eval data to the connected LLM and returns
  a concise executive summary suitable for a hiring manager briefing.

PRIMITIVE 5 — ELICITATION  (server asks the user a question mid-tool)
  Used in: confirm_and_evaluate tool
  ctx.elicit() pauses the tool, presents a confirmation form to the user,
  and resumes only on accept — guarding the expensive pipeline run.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal, Optional

from fastmcp import FastMCP
from fastmcp.server.context import Context
from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel

# Breadcrumb console for live demos. Writes to stderr only — never stdout —
# so it's safe under stdio transport (which owns stdout for JSON-RPC). When
# Tim tabs to the terminal during a demo, this is what the audience sees.
# In SSE mode the same panels render alongside Rich's normal logging.
_demo_console = Console(stderr=True, force_terminal=True, width=92)


def _breadcrumb(title: str, body: str, style: str = "cyan") -> None:
    """Emit a Rich panel to stderr so MCP primitive activity is demo-visible.

    Kept silent-on-failure: a logging crash must never break a tool call.
    """
    try:
        _demo_console.print(Panel(body, title=f"[bold]{title}[/bold]",
                                   border_style=style, padding=(0, 1)))
    except Exception:
        pass

# ---------------------------------------------------------------------------
# FastMCP 2 Server Instance
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="contoso-hr-agent",
    instructions=(
        "The Contoso HR Agent MCP server provides tools for querying candidate evaluations, "
        "triggering resume screening, and searching the HR policy knowledge base. "
        "All evaluations are performed by a 3-agent AI pipeline (PolicyExpert, ResumeAnalyst, "
        "DecisionMaker) running on Azure AI Foundry."
    ),
)


def _get_store():
    from contoso_hr.config import get_config
    from contoso_hr.memory.sqlite_store import HRSQLiteStore
    config = get_config()
    return HRSQLiteStore(config.data_dir / "hr.db")


def _get_project_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    return Path.cwd()


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_candidate(candidate_id: str) -> dict:
    """Get the full AI evaluation result for a specific candidate.

    Args:
        candidate_id: Unique candidate identifier (8-char hex string).

    Returns:
        Complete EvaluationResult including scores, decision, reasoning, and next steps.
    """
    store = _get_store()
    result = store.get_result(candidate_id)
    if result is None:
        return {"error": f"Candidate '{candidate_id}' not found"}
    return result.model_dump()


@mcp.tool()
async def list_candidates(
    limit: int = 20,
    decision_filter: str = "",
) -> list[dict]:
    """List recent candidate evaluations.

    Args:
        limit: Maximum number of results to return (default 20).
        decision_filter: Filter by disposition: 'Strong Match', 'Possible Match',
            'Needs Review', 'Not Qualified', or '' for all.

    Returns:
        List of candidate summaries with name, decision, scores, and timestamp.
    """
    store = _get_store()
    if decision_filter:
        results = store.get_candidates_by_decision(decision_filter, limit)
    else:
        results = store.get_recent_candidates(limit)
    return [c.model_dump() for c in results]


@mcp.tool()
async def trigger_resume_evaluation(
    resume_text: str,
    filename: str = "mcp_submission.txt",
) -> dict:
    """Submit resume text directly for AI evaluation (bypasses file watcher).

    Runs the full LangGraph + CrewAI pipeline synchronously and returns results.

    Args:
        resume_text: Plain text content of the resume.
        filename: Display name for the submission (e.g. 'candidate_jane.txt').

    Returns:
        EvaluationResult dict with decision, scores, and next steps.
        Processing may take 30-120 seconds depending on LLM response times.
    """
    from contoso_hr.watcher.process_resume import process_resume_text

    # process_resume_text runs the full LangGraph + CrewAI pipeline synchronously
    # (30-120s of blocking LLM/Brave/Chroma calls). Run it on a worker thread so
    # the MCP event loop can keep servicing pings and other requests.
    result = await asyncio.to_thread(process_resume_text, resume_text, filename)
    if result is None:
        return {"error": "Evaluation failed — check server logs for details"}
    return result.model_dump()


class EvalConfirmationForm(BaseModel):
    """Pydantic schema for the confirm_and_evaluate elicitation form.

    Each field's description appears as the form-field label in clients that
    render rich elicitation modals (MCP Inspector, Claude Desktop). Bare
    snake_case names would be all the user sees otherwise.
    """

    confirmed: Annotated[
        bool,
        Field(
            description=(
                "Required. Check this box to confirm you want to run the full "
                "AI evaluation pipeline. Leave unchecked to cancel."
            ),
        ),
    ] = False

    priority: Annotated[
        Literal["low", "normal", "urgent"],
        Field(
            description=(
                "Pipeline-log priority hint. 'urgent' surfaces this candidate "
                "to the top of the Candidates page; 'low' files it without "
                "auto-refresh notifications."
            ),
        ),
    ] = "normal"

    requester_notes: Annotated[
        str,
        Field(
            description=(
                "Optional. Free-text note attached to the run log (e.g. "
                "'rush — VP wants this by EOD' or 'screening for AZ-104 cohort')."
            ),
        ),
    ] = ""


@mcp.tool(
    name="confirm-and-evaluate",
    title="Confirm before running resume evaluation",
    description=(
        "Demonstrates the MCP elicitation primitive: the server pauses the "
        "tool, asks the user to fill out a structured confirmation form, and "
        "only runs the expensive pipeline if the user accepts. If your client "
        "does not support elicitation, the tool returns a clear status message."
    ),
)
async def confirm_and_evaluate(
    resume_text: Annotated[
        str,
        Field(
            description=(
                "Plain text resume content. For demos, paste any of the files "
                "from sample_resumes/ — start with RESUME_alice_zhang.txt."
            ),
        ),
    ],
    ctx: Context,
    filename: Annotated[
        str,
        Field(
            description="Display name for the submission, shown in the confirmation modal.",
        ),
    ] = "mcp_submission.txt",
) -> dict:
    """Submit a resume for evaluation, gated by an interactive confirmation form.

    PRIMITIVE 5 — ELICITATION
    The tool fires ctx.elicit() with a Pydantic-based form schema. In MCP
    Inspector and Claude Desktop, a modal appears asking the user to confirm,
    set priority, and optionally leave a note. In VS Code/Copilot Chat, support
    is inconsistent — when elicitation isn't supported, the tool returns a
    diagnostic status rather than crashing the demo.
    """
    preview = resume_text[:300].strip().replace("\n", " ")
    _breadcrumb(
        "ELICITATION → sent",
        f"Tool: confirm_and_evaluate\n"
        f"Filename: {filename}\n"
        f"Preview: {preview[:120]}{'…' if len(preview) > 120 else ''}\n"
        f"Form fields: confirmed (bool), priority (low/normal/urgent), requester_notes (str)",
        style="yellow",
    )

    try:
        elicitation_result = await ctx.elicit(
            message=(
                f"### Ready to evaluate **{filename}**?\n\n"
                f"**Preview:** _{preview}{'…' if len(resume_text) > 300 else ''}_\n\n"
                f"This will call Azure AI Foundry, ChromaDB, and Brave Search.\n"
                f"Estimated time: **30–120 seconds**.\n\n"
                f"Set the priority and confirm to proceed."
            ),
            response_type=EvalConfirmationForm,
        )
    except Exception as e:
        # Client doesn't support elicitation, or the protocol round-trip
        # failed. Return a diagnostic dict rather than crashing the demo.
        _breadcrumb(
            "ELICITATION → unsupported",
            f"Client returned: {type(e).__name__}: {e}\n"
            f"Tool returned a diagnostic status; pipeline did NOT run.",
            style="red",
        )
        return {
            "status": "elicitation_unsupported",
            "client_error": f"{type(e).__name__}: {e}",
            "message": (
                "This client does not support the MCP elicitation primitive. "
                "Use MCP Inspector or Claude Desktop to demo elicitation, or "
                "call the `trigger_resume_evaluation` tool to bypass the "
                "confirmation gate."
            ),
        }

    action = elicitation_result.action
    _breadcrumb(
        f"ELICITATION → user clicked '{action}'",
        f"Result: {action}\n"
        f"Data: {getattr(elicitation_result, 'data', None)}",
        style="green" if action == "accept" else "yellow",
    )

    if action != "accept":
        return {
            "status": action,
            "message": f"Evaluation cancelled ({action}) — pipeline did not run.",
        }

    data = elicitation_result.data
    if not data.confirmed:
        return {
            "status": "declined",
            "message": "User left the 'confirmed' checkbox unchecked — pipeline did not run.",
        }

    await ctx.info(
        f"Evaluation confirmed (priority={data.priority}, "
        f"notes={data.requester_notes!r}), starting pipeline..."
    )

    from contoso_hr.watcher.process_resume import process_resume_text

    # See trigger_resume_evaluation: pipeline is synchronous and long-running,
    # so it must run off the event loop.
    result = await asyncio.to_thread(process_resume_text, resume_text, filename)
    if result is None:
        return {"error": "Evaluation failed — check server logs for details"}

    payload = result.model_dump()
    payload["_elicitation"] = {
        "priority": data.priority,
        "requester_notes": data.requester_notes,
    }
    return payload


class CommitteePreferences(BaseModel):
    """Pydantic schema for the demo-elicitation-showcase form.

    A wide-but-shallow form designed to show off every elicitation field type
    in one screen: enum/Literal, bool, float, and free-text. No backend effect —
    the tool just echoes the captured form data back so demos stay fast.
    """

    seniority: Annotated[
        Literal["junior", "mid", "senior", "principal"],
        Field(
            description=(
                "Target seniority for this hire. Drives the role rubric and "
                "the minimum certifications check downstream."
            ),
        ),
    ] = "senior"

    certifications_required: Annotated[
        bool,
        Field(
            description=(
                "Whether Microsoft certifications (AZ-104, AZ-305, AI-102, etc.) "
                "are a hard requirement or a 'nice to have'."
            ),
        ),
    ] = True

    remote_ok: Annotated[
        bool,
        Field(
            description="Is fully-remote acceptable, or does the role require Nashville HQ presence?",
        ),
    ] = True

    min_satisfaction_score: Annotated[
        float,
        Field(
            description=(
                "Minimum learner-satisfaction score on a 5.0 scale. Contoso "
                "policy floor is 4.5; some senior roles want 4.7+."
            ),
            ge=0.0,
            le=5.0,
        ),
    ] = 4.5

    notes: Annotated[
        str,
        Field(
            description=(
                "Free-text committee notes. Anything you'd want a future "
                "candidate-search tool to weight."
            ),
        ),
    ] = ""


@mcp.tool(
    name="demo-elicitation-showcase",
    title="Demo: elicit committee preferences (no side effects)",
    description=(
        "A zero-cost elicitation demo. Pops up a multi-field form (enum, bool, "
        "float, string) to show what the MCP elicitation primitive looks like "
        "in your client — without triggering the expensive evaluation pipeline. "
        "Use this for live workshops where waiting 30-120 seconds for the real "
        "tool would kill the energy."
    ),
)
async def demo_elicitation_showcase(ctx: Context) -> dict:
    """Demonstrate elicitation form mechanics with zero side effects.

    Best demo tool in the kit: in MCP Inspector and Claude Desktop, the
    audience watches a multi-field modal appear, fills it in, and sees the
    captured data echoed back instantly. In VS Code, returns a clear
    diagnostic so the demo can move on.
    """
    _breadcrumb(
        "ELICITATION → sent (showcase)",
        "Tool: demo_elicitation_showcase\n"
        "Form fields: seniority (enum), certifications_required (bool),\n"
        "             remote_ok (bool), min_satisfaction_score (float 0-5),\n"
        "             notes (str)",
        style="yellow",
    )

    try:
        result = await ctx.elicit(
            message=(
                "### Capture hiring committee preferences\n\n"
                "Fill out the form below — this is a demo of the MCP "
                "**elicitation primitive**. No backend pipeline runs; the "
                "tool just echoes your input back so you can see what an "
                "elicitation form looks like in this client."
            ),
            response_type=CommitteePreferences,
        )
    except Exception as e:
        _breadcrumb(
            "ELICITATION → unsupported (showcase)",
            f"Client returned: {type(e).__name__}: {e}",
            style="red",
        )
        return {
            "status": "elicitation_unsupported",
            "client_error": f"{type(e).__name__}: {e}",
            "message": (
                "This client does not support MCP elicitation. Try MCP "
                "Inspector or Claude Desktop to see the form modal."
            ),
        }

    action = result.action
    _breadcrumb(
        f"ELICITATION → user clicked '{action}' (showcase)",
        f"Result: {action}\nData: {getattr(result, 'data', None)}",
        style="green" if action == "accept" else "yellow",
    )

    if action != "accept":
        return {"status": action, "message": f"User {action}ed the form — nothing captured."}

    data = result.data
    return {
        "status": "accepted",
        "captured_preferences": {
            "seniority": data.seniority,
            "certifications_required": data.certifications_required,
            "remote_ok": data.remote_ok,
            "min_satisfaction_score": data.min_satisfaction_score,
            "notes": data.notes,
        },
        "demo_note": (
            "These preferences were captured via the MCP elicitation primitive. "
            "In a production agent they'd seed a follow-up candidate search; "
            "in this demo they just illustrate the form mechanics."
        ),
    }


_SAMPLING_SYSTEM_PROMPT = (
    "You are a senior HR analyst at Contoso summarizing technical trainer "
    "candidate evaluations for busy hiring managers. Write in clear, "
    "professional prose."
)


def _build_summary_prompt(r) -> str:
    """Build the user prompt for the candidate-summary task.

    Pulled out so both the sampling path and the server-fallback path use
    the EXACT same prompt — the audience can compare apples to apples.
    """
    eval_data = (
        f"Candidate: {r.candidate_name}\n"
        f"Disposition: {r.decision} (overall score {r.overall_score}/100)\n"
        f"Skills match: {r.skills_match_score}/100, Experience: {r.experience_score}/100\n"
        f"Strengths: {', '.join(r.strengths or []) or 'none recorded'}\n"
        f"Red flags: {', '.join(r.red_flags or []) or 'none identified'}\n"
        f"Reasoning: {r.reasoning or 'not recorded'}\n"
        f"Next steps: {'; '.join(r.next_steps or []) or 'none specified'}"
    )
    return (
        "Write a concise 3-5 sentence executive summary of this candidate "
        "evaluation for a hiring manager who has not read the full report. "
        "Lead with the disposition and score, mention the top strength and "
        "top red flag, and close with the recommended next step. Be direct "
        "and professional.\n\n"
        f"{eval_data}"
    )


@mcp.tool(
    name="generate-eval-summary",
    title="Summarize a candidate evaluation",
    description=(
        "Demonstrates the MCP sampling primitive: asks the connected LLM "
        "client to write a 3-5 sentence executive summary of an existing "
        "candidate evaluation. Falls back to a direct server-side Azure AI "
        "Foundry call when the client doesn't support sampling, with a "
        "visible header showing which path executed."
    ),
)
async def generate_eval_summary(
    candidate_id: Annotated[
        str,
        Field(
            description=(
                "The 8-character hex candidate ID. Find these on the "
                "Candidates page or by calling the list_candidates tool first."
            ),
            pattern=r"^[0-9a-fA-F]{8}$",
        ),
    ],
    ctx: Context,
) -> str:
    """Generate a hiring-manager executive summary via MCP sampling (with fallback).

    PRIMITIVE 4 — SAMPLING
    Best path: ctx.sample() asks the connected LLM client to generate the
    summary. The server provides structured data; the *client's* LLM writes
    prose. This inverts the normal flow.

    Fallback path: when the client doesn't support sampling (notably VS Code
    Copilot Chat as of early 2026), the server calls Azure AI Foundry directly
    using the same prompt. The output is prefixed with a visible header so
    the audience can see which path fired.
    """
    store = _get_store()
    result = store.get_result(candidate_id)
    if result is None:
        return f"Candidate '{candidate_id}' not found."

    user_prompt = _build_summary_prompt(result)

    _breadcrumb(
        "SAMPLING → request sent",
        f"Tool: generate_eval_summary\n"
        f"Candidate: {result.candidate_name} ({candidate_id})\n"
        f"Prompt length: {len(user_prompt)} chars\n"
        f"Asking client to generate summary via ctx.sample()...",
        style="cyan",
    )

    await ctx.info(f"Requesting LLM summary for candidate {candidate_id}")

    # Try the proper sampling primitive first. If the client doesn't support
    # it (or any other failure occurs in the round-trip), fall back to a
    # direct server-side Azure AI Foundry call using the SAME prompt — the
    # audience sees an apples-to-apples comparison.
    try:
        sampling_result = await ctx.sample(
            messages=user_prompt,
            system_prompt=_SAMPLING_SYSTEM_PROMPT,
            max_tokens=256,
        )
        summary_text = (sampling_result.text or "").strip()
        if not summary_text:
            raise RuntimeError("sampling returned empty text")

        _breadcrumb(
            "SAMPLING → client responded",
            f"Path: client-sampled (the connected LLM wrote this)\n"
            f"Response: {len(summary_text)} chars",
            style="green",
        )
        header = "[via client-sampled — the connected LLM wrote this summary]"
        return f"{header}\n\n{summary_text}"

    except Exception as e:
        # Common cases hit here:
        #   - VS Code Copilot Chat: McpError "client does not support sampling"
        #   - Inspector without a mock LLM response wired up: timeout/empty
        #   - Network/protocol hiccups
        # In every case we want a useful answer, not a broken demo.
        _breadcrumb(
            "SAMPLING → client unsupported, using server fallback",
            f"Client returned: {type(e).__name__}: {e}\n"
            f"Falling back to direct Azure AI Foundry call (same prompt)...",
            style="yellow",
        )

        try:
            from contoso_hr.config import get_config
            config = get_config()
            llm = config.get_llm()

            # LangChain's invoke is sync — offload to a thread so the MCP
            # event loop keeps responding to pings during the LLM call.
            from langchain_core.messages import HumanMessage, SystemMessage
            messages = [
                SystemMessage(content=_SAMPLING_SYSTEM_PROMPT),
                HumanMessage(content=user_prompt),
            ]
            response = await asyncio.to_thread(llm.invoke, messages)
            summary_text = (response.content or "").strip()

            _breadcrumb(
                "SAMPLING → server fallback complete",
                f"Path: server-fallback (Azure AI Foundry via {config.azure_foundry_chat_model})\n"
                f"Response: {len(summary_text)} chars",
                style="green",
            )

            header = (
                f"[via server-fallback — client did not support sampling "
                f"({type(e).__name__}); same prompt sent directly to "
                f"{config.azure_foundry_chat_model}]"
            )
            return f"{header}\n\n{summary_text}"

        except Exception as fallback_err:
            _breadcrumb(
                "SAMPLING → both paths failed",
                f"Sampling error: {type(e).__name__}: {e}\n"
                f"Fallback error: {type(fallback_err).__name__}: {fallback_err}",
                style="red",
            )
            return (
                f"[sampling demo failed — both paths errored]\n\n"
                f"Client sampling: {type(e).__name__}: {e}\n"
                f"Server fallback: {type(fallback_err).__name__}: {fallback_err}"
            )


@mcp.tool()
async def query_policy(question: str) -> str:
    """Query the Contoso HR policy knowledge base using semantic search.

    Args:
        question: Natural language question about Contoso HR policy.
                  Example: 'What is the compensation band for Level 3?'

    Returns:
        Relevant policy text chunks from ChromaDB.
    """
    from contoso_hr.knowledge.retriever import query_policy_knowledge

    # query_policy_knowledge is fully synchronous (blocking Azure embedding HTTP
    # call + ChromaDB SQLite reads). Running it inline would block the asyncio
    # event loop and stall the MCP transport — Inspector and VS Code see this
    # as a hang. Offload to a worker thread so the loop stays responsive.
    context = await asyncio.to_thread(query_policy_knowledge, question, 4)
    if not context.chunks:
        return "No relevant policy content found. Ensure knowledge base has been seeded (uv run hr-seed)."

    parts = []
    for chunk, source in zip(context.chunks, context.sources):
        parts.append(f"[{source}]\n{chunk}")
    return "\n\n---\n\n".join(parts)


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


@mcp.resource("schema://candidate")
def candidate_schema() -> str:
    """JSON schema for candidate evaluation results."""
    from contoso_hr.models import EvaluationResult
    return json.dumps(EvaluationResult.model_json_schema(), indent=2)


@mcp.resource("stats://evaluations")
def evaluation_stats() -> str:
    """Current aggregate statistics for all candidate evaluations."""
    store = _get_store()
    return json.dumps(store.get_stats(), indent=2)


@mcp.resource("samples://resumes")
def list_sample_resumes() -> str:
    """List of available sample resume files for testing."""
    root = _get_project_root()
    sample_dir = root / "sample_resumes"
    if not sample_dir.exists():
        return json.dumps({"samples": []})
    files = sorted(sample_dir.glob("*.txt")) + sorted(sample_dir.glob("*.md"))
    return json.dumps({
        "samples": [
            {"filename": f.name, "size_bytes": f.stat().st_size}
            for f in files
        ]
    }, indent=2)


@mcp.resource("config://settings")
def get_config_settings() -> str:
    """Current application configuration (no secrets)."""
    from contoso_hr.config import get_config
    config = get_config()
    return json.dumps({
        "chat_model": config.azure_foundry_chat_model,
        "embedding_model": config.azure_foundry_embedding_model,
        "api_version": config.azure_foundry_api_version,
        "endpoint": config.azure_foundry_endpoint,
        "azure_tenant_id": config.azure_tenant_id,
        "azure_subscription_id": config.azure_subscription_id,
        "azure_resource_group": config.azure_resource_group,
        "watch_poll_seconds": config.watch_poll_seconds,
        "log_level": config.log_level,
        "engine_port": config.engine_port,
        "mcp_port": config.mcp_port,
        "incoming_dir": str(config.incoming_dir),
        "outgoing_dir": str(config.outgoing_dir),
    }, indent=2)


# ---------------------------------------------------------------------------
# Resource Templates  (PRIMITIVE 2b — parameterized URIs)
#
# URI parameters map directly to function arguments.  FastMCP registers
# these as ResourceTemplates rather than static Resources, so clients can
# enumerate the template and instantiate it with concrete values.
# ---------------------------------------------------------------------------


@mcp.resource("candidate://{candidate_id}")
def candidate_resource(candidate_id: str) -> str:
    """Formatted markdown profile for a single evaluated candidate.

    URI example: candidate://a1b2c3d4

    Args:
        candidate_id: 8-char hex candidate identifier.

    Returns:
        Markdown-formatted evaluation summary, or an error message if not found.
    """
    store = _get_store()
    result = store.get_result(candidate_id)
    if result is None:
        return f"# Candidate Not Found\n\nNo evaluation exists for `{candidate_id}`."

    r = result
    lines = [
        f"# {r.candidate_name}",
        f"**ID:** `{r.candidate_id}`  |  **Decision:** {r.decision}  |  **Score:** {r.overall_score}/100",
        "",
        f"## Scores",
        f"- Skills match: {r.skills_match_score}/100",
        f"- Experience: {r.experience_score}/100",
        "",
        f"## Strengths",
        *[f"- {s}" for s in (r.strengths or [])],
        "",
        f"## Red Flags",
        *(([f"- {f}" for f in r.red_flags]) if r.red_flags else ["- None identified"]),
        "",
        f"## Reasoning",
        r.reasoning or "_No reasoning recorded._",
        "",
        f"## Recommended Next Steps",
        *[f"{i+1}. {s}" for i, s in enumerate(r.next_steps or [])],
        "",
        f"_Evaluated: {r.evaluated_at}_",
    ]
    return "\n".join(lines)


@mcp.resource("policy://{topic}")
def policy_topic_resource(topic: str) -> str:
    """HR policy chunks relevant to a topic keyword.

    URI example: policy://compensation  or  policy://mct-requirements

    Performs semantic search against ChromaDB and returns the top 3 matching
    policy chunks as plain text, each prefixed with its source document name.

    Args:
        topic: Keyword or short phrase describing the policy area of interest.

    Returns:
        Relevant policy text, or a message if no content is found.
    """
    from contoso_hr.knowledge.retriever import query_policy_knowledge

    context = query_policy_knowledge(topic, k=3)
    if not context.chunks:
        return f"No policy content found for topic: '{topic}'. Run `uv run hr-seed` to populate the knowledge base."

    parts = [f"# HR Policy: {topic}\n"]
    for chunk, source in zip(context.chunks, context.sources):
        parts.append(f"## [{source}]\n{chunk}")
    return "\n\n---\n\n".join(parts)


# ---------------------------------------------------------------------------
# Prompts  (PRIMITIVE 3 — reusable message templates)
#
# Prompts return str (single user message), or list[dict] for multi-turn
# conversations with system context, user instructions, and assistant priming.
# FastMCP converts dict items to PromptMessage objects automatically.
# ---------------------------------------------------------------------------


@mcp.prompt(
    name="score-trainer-resume",
    title="Score a candidate resume",
    description=(
        "Score a trainer-candidate resume against Contoso's hiring rubric and "
        "return a disposition (Strong Match, Possible Match, Needs Review, or "
        "Not Qualified) with strengths, red flags, and recommended next steps."
    ),
)
def evaluate_resume(
    resume_text: Annotated[
        str,
        Field(
            description=(
                "Paste the full resume text. Plain text or markdown is fine — "
                "headings, bullet points, and certification lists all parse cleanly. "
                "Minimum useful length is roughly half a page."
            ),
        ),
    ],
    role: Annotated[
        str,
        Field(
            default="",
            description=(
                "Target role to evaluate against. Leave blank for the generic "
                "'Contoso technical trainer' rubric, or specify a track, e.g. "
                "'Senior Trainer — Azure Infrastructure' or 'M365 Security Trainer'."
            ),
        ),
    ] = "",
) -> list[dict]:
    """Score a trainer-candidate resume and recommend a hiring disposition."""
    role_label = role or "Contoso technical trainer"
    return [
        {
            "role": "user",
            "content": (
                f"You are a senior talent acquisition specialist at Contoso, evaluating "
                f"candidates for technical trainer roles covering Microsoft Azure, M365, "
                f"and Security certification courses.\n\n"
                f"Evaluate the following resume for the role of **{role_label}**.\n\n"
                f"Score each dimension 0–100 and recommend exactly one disposition:\n"
                f"- **Strong Match** (80+): Schedule interview immediately\n"
                f"- **Possible Match** (55–79): Schedule technical screen\n"
                f"- **Needs Review** (35–54): Recruiter follow-up needed\n"
                f"- **Not Qualified** (<35): Decline with courtesy\n\n"
                f"Evaluation criteria:\n"
                f"1. MCT (Microsoft Certified Trainer) status — required for Strong Match\n"
                f"2. Microsoft certifications: AZ-104, AZ-305, AZ-400, SC-300, AI-102\n"
                f"3. Training delivery volume and learner satisfaction (target 4.5+/5.0)\n"
                f"4. Curriculum development or course authorship experience\n"
                f"5. Hands-on technical depth in Azure/M365/Security\n\n"
                f"---\n\n{resume_text}"
            ),
        },
        {
            "role": "assistant",
            "content": (
                "## Evaluation Summary\n\n"
                "**Skills Match Score:** \n"
                "**Experience Score:** \n"
                "**Overall Score:** \n"
                "**Disposition:** \n\n"
                "### Strengths\n- \n\n"
                "### Red Flags\n- \n\n"
                "### Reasoning\n\n"
                "### Recommended Next Steps\n1. "
            ),
        },
    ]


@mcp.prompt(
    name="ask-hr-policy",
    title="Ask an HR policy question",
    description=(
        "Ask a question about Contoso HR policy and get a grounded answer that "
        "cites the source policy document. The assistant will say so explicitly "
        "if the answer isn't covered by policy rather than guessing."
    ),
)
def policy_query(
    question: Annotated[
        str,
        Field(
            description=(
                "The HR policy question to answer, in plain English. "
                "Examples: 'What is the compensation band for Level 3 trainers?', "
                "'Is MCT certification required for senior roles?', "
                "'What's the minimum learner satisfaction score for a Strong Match?'"
            ),
        ),
    ],
) -> list[dict]:
    """Ask a grounded question about Contoso HR policy with source citations."""
    return [
        {
            "role": "user",
            "content": (
                "You are the Contoso HR Policy Assistant. Answer questions accurately "
                "and concisely using only Contoso HR policy documentation. "
                "Always cite the relevant policy section or document name. "
                "If the answer is not covered by policy, say so explicitly — "
                "do not speculate."
            ),
        },
        {
            "role": "user",
            "content": f"Policy question: {question}",
        },
    ]


@mcp.prompt(
    name="prep-hiring-debrief",
    title="Prep a hiring debrief for a candidate",
    description=(
        "Load an existing candidate evaluation from the database and return a "
        "hiring-committee debrief: a one-paragraph hiring rationale, three "
        "targeted interview questions based on red flags, and any policy "
        "considerations relevant to the disposition."
    ),
)
async def disposition_review(
    candidate_id: Annotated[
        str,
        Field(
            description=(
                "The 8-character hex candidate ID (for example 'a1b2c3d4'). "
                "Find these on the Candidates page in the web UI, or call the "
                "list_candidates tool first to discover recent IDs."
            ),
            pattern=r"^[0-9a-fA-F]{8}$",
        ),
    ],
    ctx: Context,
) -> list[dict]:
    """Build a hiring-committee debrief packet for an existing candidate evaluation."""
    await ctx.info(f"Loading candidate {candidate_id} for disposition review")

    store = _get_store()
    result = store.get_result(candidate_id)
    if result is None:
        return [
            {
                "role": "user",
                "content": f"Candidate `{candidate_id}` was not found in the database. Please verify the ID.",
            }
        ]

    r = result
    candidate_summary = (
        f"**Name:** {r.candidate_name}\n"
        f"**Decision:** {r.decision}  |  **Overall Score:** {r.overall_score}/100\n"
        f"**Skills Match:** {r.skills_match_score}/100  |  **Experience:** {r.experience_score}/100\n\n"
        f"**Strengths:** {', '.join(r.strengths or []) or 'None recorded'}\n"
        f"**Red Flags:** {', '.join(r.red_flags or []) or 'None identified'}\n\n"
        f"**Reasoning:** {r.reasoning or 'Not recorded'}\n\n"
        f"**Next Steps:** {'; '.join(r.next_steps or []) or 'None specified'}"
    )

    await ctx.info(f"Candidate loaded: {r.candidate_name} — {r.decision}")

    return [
        {
            "role": "user",
            "content": (
                "You are a Contoso hiring committee chair preparing for a candidate debrief. "
                "Review the evaluation below and provide: (1) a one-paragraph hiring rationale, "
                "(2) three targeted interview questions based on the red flags or experience gaps, "
                "and (3) any policy considerations relevant to this disposition.\n\n"
                f"## Candidate Evaluation\n\n{candidate_summary}"
            ),
        },
    ]
