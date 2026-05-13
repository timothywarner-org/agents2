"""
Contoso HR Agent — FastAPI engine.

Serves the web UI (static files from web/) and REST API endpoints:
  POST /api/chat          — HR policy Q&A chatbot
  POST /api/upload        — Resume file upload → queued for evaluation
  GET  /api/candidates    — List evaluated candidates (for grid view)
  GET  /api/candidates/{id} — Full evaluation detail
  GET  /api/stats         — Aggregate statistics

Kills port ENGINE_PORT on startup to ensure clean bind.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import get_config
from .logging_setup import get_hr_logger, print_banner, setup_logging
from .memory.sqlite_store import HRSQLiteStore
from .models import (
    CandidateSummary,
    ChatMessage,
    ChatResponse,
    EvaluationResult,
    Provenance,
    ProvenanceGrounding,
    ProvenanceSource,
    UploadResponse,
)
from .pipeline.tools import tool_capture
from .util.port_utils import force_kill_port

# ---------------------------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Contoso HR Agent",
    description="AI-powered resume screening and HR policy Q&A",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Chat session memory — persisted to data/chat_sessions/{session_id}.json
#
# Each session file is a JSON array of {role, content} dicts, matching the
# LangChain message format. The in-memory dict is a write-through cache:
# reads load from disk on first access, writes flush to disk immediately.
# This gives the LLM full conversation context across server restarts.
# ---------------------------------------------------------------------------

_chat_histories: dict[str, list[dict]] = {}


def _sessions_dir() -> Path:
    config = get_config()
    d = config.data_dir / "chat_sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_session(session_id: str) -> list[dict]:
    """Load history from disk into the in-memory cache if not already loaded."""
    if session_id not in _chat_histories:
        path = _sessions_dir() / f"{session_id}.json"
        if path.exists():
            try:
                _chat_histories[session_id] = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                _chat_histories[session_id] = []
        else:
            _chat_histories[session_id] = []
    return _chat_histories[session_id]


def _save_session(session_id: str, history: list[dict]) -> None:
    """Flush the current history to disk."""
    path = _sessions_dir() / f"{session_id}.json"
    try:
        path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass  # non-fatal — memory still works in-process


def _build_past_session_context(current_session_id: str, max_sessions: int = 2, max_turns: int = 6) -> str:
    """Return a compact excerpt from the most recent past sessions.

    Pulls up to `max_turns` turns from each of the `max_sessions` most
    recently modified session files, skipping the current session. Each
    message is truncated to 200 chars to keep the prompt tight.
    """
    sessions_dir = _sessions_dir()
    past_files = sorted(
        [p for p in sessions_dir.glob("*.json") if p.stem != current_session_id],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:max_sessions]

    if not past_files:
        return ""

    blocks = []
    for path in past_files:
        try:
            history = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not history:
            continue
        excerpt_turns = history[-max_turns:]
        lines = []
        for turn in excerpt_turns:
            role_label = "User" if turn.get("role") == "user" else "Alex (you)"
            lines.append(f"  {role_label}: {turn.get('content', '')[:200]}")
        blocks.append("\n".join(lines))

    if not blocks:
        return ""

    return "\n\n---\n".join(blocks)


# Threshold above which we count a chunk as "matched" for the grounding
# summary. ChromaDB cosine similarity 0.5 corresponds to a moderately
# strong match in our corpus — empirical, not magical. Tune if recall feels off.
_GROUNDING_MATCH_THRESHOLD = 0.5
# Preview chunk length surfaced to the UI before "expand to full". Long
# enough to identify the relevant passage, short enough to keep the chat
# readable.
_CHUNK_PREVIEW_CHARS = 200


def _build_provenance(captured: list[dict]) -> Provenance:
    """Turn the per-request tool-capture buffer into a Provenance block.

    Each captured entry is one tool invocation. Currently handles
    query_hr_policy (one entry → N sources, one per chunk) and
    brave_web_search (one entry → N sources, one per web result). Errors and
    skipped invocations don't produce sources but still count toward
    tools_invoked so the user can see what was attempted.
    """
    sources: list[ProvenanceSource] = []
    tools_invoked: list[str] = []
    web_search_used = False
    all_scores: list[float] = []

    for entry in captured:
        tool_name = entry.get("tool", "unknown")
        if tool_name not in tools_invoked:
            tools_invoked.append(tool_name)

        if tool_name == "query_hr_policy":
            chunks = entry.get("chunks") or []
            srcs = entry.get("sources") or []
            scores = entry.get("scores") or []
            for i, chunk in enumerate(chunks):
                src_name = srcs[i] if i < len(srcs) else "unknown"
                score = scores[i] if i < len(scores) else None
                sources.append(ProvenanceSource(
                    type="policy",
                    name=src_name,
                    preview=chunk[:_CHUNK_PREVIEW_CHARS].strip(),
                    full_text=chunk,
                    score=score,
                ))
                if score is not None:
                    all_scores.append(score)

        elif tool_name == "brave_web_search":
            web_search_used = True
            for result in (entry.get("results") or []):
                title = result.get("title", "") or result.get("url", "(no title)")
                desc = result.get("description", "")
                sources.append(ProvenanceSource(
                    type="web",
                    name=result.get("url") or title,
                    preview=desc[:_CHUNK_PREVIEW_CHARS],
                    full_text=desc,
                    score=None,
                ))

    grounding = ProvenanceGrounding(
        retrieved_chunks=len(sources),
        chunks_above_threshold=sum(
            1 for s in all_scores if s >= _GROUNDING_MATCH_THRESHOLD
        ),
        top_similarity=max(all_scores) if all_scores else None,
        tools_invoked=tools_invoked,
        web_search_used=web_search_used,
    )
    return Provenance(sources=sources, grounding=grounding)


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------


@app.post("/api/chat", response_model=ChatResponse)
async def chat(message: ChatMessage) -> ChatResponse:
    """Handle a chat message via the ChatConcierge CrewAI agent.

    The concierge uses the query_hr_policy tool so policy answers are
    grounded in ChromaDB-retrieved Contoso documentation. Conversation
    history is included in the task prompt for context continuity.
    """
    logger = get_hr_logger()
    config = get_config()

    # Track wall-time for the runs.html observability view. Using monotonic
    # so a clock change mid-request doesn't yield a negative latency.
    import time
    chat_run_id = uuid.uuid4().hex[:12]
    started_monotonic = time.monotonic()

    # Load (or create) persistent session history
    history = _load_session(message.session_id)
    history.append({"role": "user", "content": message.message})

    # Build a compact transcript of recent turns to give the agent context
    recent = history[-20:]
    transcript_lines = []
    for turn in recent[:-1]:  # exclude current message — it's the task
        role_label = "User" if turn["role"] == "user" else "Alex (you)"
        transcript_lines.append(f"{role_label}: {turn['content'][:300]}")
    transcript = "\n".join(transcript_lines) if transcript_lines else "(new conversation)"

    # Pull in excerpts from recent past sessions so the agent can reference
    # things the user mentioned in previous conversations.
    past_context = _build_past_session_context(message.session_id)
    past_context_block = (
        f"\nPRIOR SESSION CONTEXT (recent past conversations — use only if relevant):\n{past_context}\n"
        if past_context else ""
    )

    # Per-request capture buffer for tool invocations. The ContextVar token
    # lets us reset cleanly even if kickoff raises. The tools in pipeline.tools
    # check this var and append to the list whenever it's set.
    captured: list[dict] = []
    capture_token = tool_capture.set(captured)
    provenance: Optional[Provenance] = None

    try:
        from crewai import Crew, Process, Task
        from contoso_hr.pipeline.agents import ChatConciergeAgent

        llm = config.get_crew_llm()
        agent = ChatConciergeAgent.create(llm)

        task = Task(
            description=f"""Respond to the user's message as Alex, the Contoso HR Chat Concierge.
{past_context_block}
CURRENT CONVERSATION:
{transcript}

USER'S CURRENT MESSAGE:
{message.message}

Use query_hr_policy for any policy question. Keep the response concise and conversational.
Do not repeat the conversation history in your reply — just answer the current message.""",
            expected_output="A helpful, concise conversational reply to the user's message.",
            agent=agent,
        )

        crew = Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential,
            verbose=False,
        )

        result = await asyncio.to_thread(crew.kickoff)
        reply = result.raw.strip()

    except Exception as e:
        logger.error(f"Chat concierge error: {e}", e)
        reply = (
            "I'm sorry, I encountered an error. "
            "Please check that Azure AI Foundry is configured and the knowledge base is seeded."
        )
    finally:
        # Always reset the ContextVar and build provenance from whatever we
        # captured (possibly nothing, e.g. if the agent answered from memory
        # without invoking a tool — that's a legitimate signal too).
        tool_capture.reset(capture_token)
        try:
            provenance = _build_provenance(captured)
        except Exception as prov_err:
            # Provenance is a transparency feature; if building it fails for
            # any reason, log and continue rather than break the chat reply.
            logger.error(f"Provenance build failed: {prov_err}", prov_err)
            provenance = None

    history.append({"role": "assistant", "content": reply})

    # Persist to disk so context survives server restarts
    _save_session(message.session_id, history)

    # Record this chat turn as a tracked run for runs.html. We do this in a
    # try/except so a transient SQLite failure can never blow up a chat reply.
    try:
        latency_ms = int((time.monotonic() - started_monotonic) * 1000)
        tools_used = list(provenance.grounding.tools_invoked) if provenance else []
        prov_json = provenance.model_dump_json() if provenance else None
        store = HRSQLiteStore(config.data_dir / "hr.db")
        store.save_chat_run(
            run_id=chat_run_id,
            session_id=message.session_id,
            user_message=message.message,
            assistant_reply=reply,
            tools_invoked=tools_used,
            provenance_json=prov_json,
            latency_ms=latency_ms,
        )
    except Exception as run_err:
        logger.error(f"Chat run persist failed: {run_err}", run_err)

    suggestions = _get_suggestions(message.message)

    return ChatResponse(
        reply=reply,
        session_id=message.session_id,
        suggestions=suggestions,
        provenance=provenance,
    )


@app.post("/api/upload", response_model=UploadResponse)
async def upload_resume(file: UploadFile = File(...)) -> UploadResponse:
    """Accept a resume file upload and queue it for evaluation.

    Saves the file to data/incoming/ where the watcher will pick it up.
    Returns immediately with a queued status.
    """
    logger = get_hr_logger()
    config = get_config()

    # Validate file type
    allowed_extensions = {".txt", ".md", ".pdf", ".docx"}
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in allowed_extensions:
        return UploadResponse(
            candidate_id="",
            filename=file.filename or "",
            status="error",
            message=f"Supported formats: .txt, .md, .pdf, .docx. Got: {suffix}",
        )

    # Generate a safe filename
    candidate_id = str(uuid.uuid4())[:8]
    safe_name = f"upload_{candidate_id}{suffix}"
    dest = config.incoming_dir / safe_name

    config.incoming_dir.mkdir(parents=True, exist_ok=True)

    try:
        content = await file.read()
        dest.write_bytes(content)
        logger.file_operation("Queued upload", str(dest))
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        return UploadResponse(
            candidate_id=candidate_id,
            filename=file.filename or safe_name,
            status="error",
            message=f"Failed to save file: {e}",
        )

    return UploadResponse(
        candidate_id=candidate_id,
        filename=file.filename or safe_name,
        status="queued",
        message=(
            "Resume queued for evaluation! "
            "The AI pipeline will process it shortly. "
            "Check the Candidates page for results (auto-refreshes every 10s)."
        ),
    )


@app.get("/api/chat/history/{session_id}")
async def get_chat_history(session_id: str) -> dict:
    """Return the persisted chat history for a session.

    Useful for debugging memory persistence and for the MCP server.
    """
    history = _load_session(session_id)
    return {"session_id": session_id, "message_count": len(history), "history": history}


@app.delete("/api/chat/history/{session_id}")
async def clear_chat_history(session_id: str) -> dict:
    """Delete the persisted chat history for a session."""
    _chat_histories.pop(session_id, None)
    path = _sessions_dir() / f"{session_id}.json"
    if path.exists():
        path.unlink()
    return {"session_id": session_id, "cleared": True}


@app.get("/api/chat/sessions")
async def list_chat_sessions() -> dict:
    """List all persisted chat sessions, sorted by most recently updated.

    Returns metadata for each session: id, message count, last user message
    preview, and last-updated timestamp (Unix seconds).
    """
    sessions_dir = _sessions_dir()
    sessions = []
    for path in sorted(sessions_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        session_id = path.stem
        try:
            history = json.loads(path.read_text(encoding="utf-8"))
            last_user = next(
                (m["content"] for m in reversed(history) if m.get("role") == "user"), ""
            )
            sessions.append({
                "session_id": session_id,
                "message_count": len(history),
                "last_message_preview": last_user[:80],
                "last_updated": path.stat().st_mtime,
            })
        except Exception:
            continue
    return {"sessions": sessions}


@app.get("/api/chat-runs")
async def list_chat_runs(limit: int = 50) -> dict:
    """Return recent chat runs for the unified Pipeline Runs view.

    Each row pairs the user's message with the assistant reply, the tools
    invoked, full provenance, and observed latency. runs.html merges these
    with /api/candidates so a single timeline shows both pipeline runs and
    chat turns.
    """
    config = get_config()
    store = HRSQLiteStore(config.data_dir / "hr.db")
    return {"runs": store.get_recent_chat_runs(limit=limit)}


@app.get("/api/chat-runs/{run_id}")
async def get_chat_run(run_id: str) -> dict:
    """Return a single chat run by run_id."""
    config = get_config()
    store = HRSQLiteStore(config.data_dir / "hr.db")
    run = store.get_chat_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"chat run {run_id} not found")
    return run


@app.get("/api/candidates", response_model=list[CandidateSummary])
async def list_candidates(
    limit: int = 50,
    decision: Optional[str] = None,
) -> list[CandidateSummary]:
    """Return the list of evaluated candidates for the grid view.

    Args:
        limit: Maximum number of results (default 50).
        decision: Filter by advance/hold/reject (optional).
    """
    config = get_config()
    store = HRSQLiteStore(config.data_dir / "hr.db")

    if decision:
        return store.get_candidates_by_decision(decision, limit)
    return store.get_recent_candidates(limit)


@app.get("/api/candidates/{candidate_id}", response_model=EvaluationResult)
async def get_candidate(candidate_id: str) -> EvaluationResult:
    """Return the full evaluation result for a specific candidate.

    Args:
        candidate_id: Unique candidate identifier.
    """
    config = get_config()
    store = HRSQLiteStore(config.data_dir / "hr.db")
    result = store.get_result(candidate_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Candidate {candidate_id} not found")
    return result


@app.get("/api/stats")
async def get_stats() -> dict:
    """Return aggregate evaluation statistics."""
    config = get_config()
    store = HRSQLiteStore(config.data_dir / "hr.db")
    return store.get_stats()


@app.get("/api/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "service": "contoso-hr-agent"}


# ---------------------------------------------------------------------------
# Meta endpoint — snapshot of every persistent store the agent owns.
# Used by web/meta.html to teach learners "what does the agent remember?"
# ---------------------------------------------------------------------------

def _stat_path(path: Path) -> dict:
    """Common path metadata: exists, size_bytes, mtime ISO-8601."""
    if not path.exists():
        return {"path": str(path), "exists": False, "size_bytes": 0, "mtime": None}
    if path.is_file():
        size = path.stat().st_size
    else:
        size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    return {"path": str(path), "exists": True, "size_bytes": size, "mtime": mtime}


def _summarize_sqlite(db_path: Path, known_tables: Optional[list[str]] = None) -> dict:
    """Row counts for each table in a SQLite file. Degrades gracefully on schema surprises."""
    info = _stat_path(db_path)
    info["tables"] = {}
    if not info["exists"]:
        return info
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            cur = conn.cursor()
            if known_tables is None:
                # Introspect (LangGraph checkpoints — schema is internal, may shift)
                cur.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
                tables = [row[0] for row in cur.fetchall()]
            else:
                tables = known_tables
            for table in tables:
                try:
                    cur.execute(f"SELECT COUNT(*) FROM {table}")
                    info["tables"][table] = cur.fetchone()[0]
                except sqlite3.Error as exc:
                    info["tables"][table] = {"error": str(exc)}
        finally:
            conn.close()
    except sqlite3.Error as exc:
        info["error"] = str(exc)
    return info


def _summarize_chroma(chroma_dir: Path) -> dict:
    """ChromaDB collection inventory: count + distinct source filenames."""
    info = _stat_path(chroma_dir)
    info["collection"] = None
    info["chunk_count"] = 0
    info["doc_sources"] = []
    if not info["exists"]:
        return info
    try:
        import chromadb
        from .knowledge.vectorizer import COLLECTION_NAME

        client = chromadb.PersistentClient(path=str(chroma_dir))
        collection = client.get_or_create_collection(name=COLLECTION_NAME)
        info["collection"] = COLLECTION_NAME
        info["chunk_count"] = collection.count()
        # Pull metadatas only — no embeddings or documents — so this stays cheap.
        if info["chunk_count"] > 0:
            sample = collection.get(include=["metadatas"], limit=10000)
            sources = {m.get("source") for m in sample.get("metadatas", []) if m}
            info["doc_sources"] = sorted(s for s in sources if s)
    except Exception as exc:  # ChromaDB raises a wide tree of errors; one catch is fine here
        info["error"] = f"{type(exc).__name__}: {exc}"
    return info


def _summarize_dir(dir_path: Path, glob_pattern: str) -> dict:
    """File-count + total-size summary for a directory of matched files."""
    info = _stat_path(dir_path)
    info["file_count"] = 0
    info["newest_mtime"] = None
    if not info["exists"] or not dir_path.is_dir():
        return info
    files = list(dir_path.glob(glob_pattern))
    info["file_count"] = len(files)
    if files:
        newest = max(files, key=lambda f: f.stat().st_mtime)
        info["newest_mtime"] = datetime.fromtimestamp(
            newest.stat().st_mtime, tz=timezone.utc
        ).isoformat()
    return info


@app.get("/api/meta")
async def get_meta() -> dict:
    """Snapshot every persistent store the agent owns. Read-only, cheap, ~sub-100ms."""
    config = get_config()
    data_dir = config.data_dir
    return {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "data_dir": str(data_dir),
        "stores": {
            "hr_db": {
                "label": "HR Evaluations (SQLite)",
                "description": "Candidates + evaluations from the LangGraph pipeline.",
                **_summarize_sqlite(data_dir / "hr.db", ["candidates", "evaluations"]),
            },
            "checkpoints_db": {
                "label": "LangGraph Checkpoints (SQLite)",
                "description": "Per-thread state snapshots written by SqliteSaver. Schema is internal to LangGraph.",
                **_summarize_sqlite(data_dir / "checkpoints.db", None),
            },
            "chroma": {
                "label": "ChromaDB Vector Store",
                "description": "Embedded policy chunks for RAG retrieval.",
                **_summarize_chroma(data_dir / "chroma"),
            },
            "chat_sessions": {
                "label": "Chat Sessions (JSON)",
                "description": "One JSON file per chat session — survives browser clears.",
                **_summarize_dir(data_dir / "chat_sessions", "*.json"),
            },
            "outgoing": {
                "label": "Pipeline Outputs (JSON)",
                "description": "Full EvaluationResult written by the watcher after each pipeline run.",
                **_summarize_dir(data_dir / "outgoing", "*.json"),
            },
        },
    }


# ---------------------------------------------------------------------------
# Static file serving (web UI)
# ---------------------------------------------------------------------------

def _mount_static() -> None:
    """Mount the web/ directory for static file serving."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "web").exists():
            web_dir = parent / "web"
            app.mount("/", StaticFiles(directory=str(web_dir), html=True), name="web")
            return


_mount_static()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_suggestions(user_message: str) -> list[str]:
    """Generate context-aware quick-reply suggestions."""
    msg_lower = user_message.lower()
    if any(w in msg_lower for w in ["salary", "pay", "compensation", "band"]):
        return ["What is the salary band for a Senior Trainer?", "How are bonuses calculated?"]
    if any(w in msg_lower for w in ["mct", "certified trainer", "certification"]):
        return ["Is MCT required for all trainer roles?", "Which Azure certs does Contoso value most?"]
    if any(w in msg_lower for w in ["interview", "hire", "hiring", "process"]):
        return ["What is the trainer interview process?", "What does the technical screen involve?"]
    if any(w in msg_lower for w in ["resume", "cv", "upload", "candidate"]):
        return ["How do I submit a resume?", "What makes a strong trainer resume?"]
    if any(w in msg_lower for w in ["score", "decision", "match", "qualified", "review", "disposition"]):
        return ["What does 'Strong Match' mean?", "When does a candidate get 'Needs Review'?"]
    return [
        "What certifications does Contoso require for trainers?",
        "How do I submit a resume for evaluation?",
        "What is Contoso's EEO policy?",
    ]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Start the FastAPI server on ENGINE_PORT, killing any existing process first."""
    import uvicorn

    config = get_config()
    setup_logging(config.log_level)
    print_banner()

    port = config.engine_port
    force_kill_port(port)

    mcp_port = config.mcp_port
    print(f"\n  Web UI:  http://localhost:{port}/chat.html")
    print(f"  API:     http://localhost:{port}/api/")
    print(f"  Docs:    http://localhost:{port}/docs")
    print(f"  MCP SSE: http://localhost:{mcp_port}/sse\n")

    uvicorn.run(
        "contoso_hr.engine:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level=config.log_level.lower(),
    )
