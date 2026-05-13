"""
Pydantic v2 data contracts for Contoso HR Agent.

Data flow:
  ResumeSubmission (input)
    → PolicyContext   (ChromaDB retrieval result)
    → CandidateEval   (ResumeAnalyst output)
    → HRDecision      (DecisionMaker output)
    → EvaluationResult (final output → SQLite + web)

Token tracking models are reused from the agent MVP pattern.
"""

from __future__ import annotations

from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


# =============================================================================
# Token Tracking (reused pattern)
# =============================================================================


class TokenUsage(BaseModel):
    """Token usage for a single LLM call."""

    input_tokens: int
    output_tokens: int
    total_tokens: int
    model_name: str
    estimated_cost_usd: Optional[float] = None


class AgentTokens(BaseModel):
    """Token usage for one agent/node."""

    agent_name: str
    usage: TokenUsage


class PipelineTokens(BaseModel):
    """Aggregated token usage across all pipeline agents."""

    agents: list[AgentTokens]
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    estimated_total_cost_usd: Optional[float] = None
    cost_breakdown: dict[str, float] = Field(default_factory=dict)
    efficiency_metrics: dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# Input Models
# =============================================================================


class ResumeSubmission(BaseModel):
    """Input to the HR evaluation pipeline.

    Can originate from:
    - A file dropped into data/incoming/ (source='incoming_folder')
    - A file uploaded via the web chat UI (source='upload')
    """

    candidate_id: str = Field(default_factory=lambda: str(uuid4())[:8])
    filename: str
    raw_text: str
    source: Literal["upload", "incoming_folder"] = "incoming_folder"
    session_id: str = Field(default_factory=lambda: str(uuid4()))


# =============================================================================
# Agent Output Models
# =============================================================================


class PolicyContext(BaseModel):
    """Result of a ChromaDB policy knowledge retrieval.

    Produced by the PolicyExpert agent's query_hr_policy tool.
    """

    chunks: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    # Per-chunk similarity in [0.0, 1.0]; same index as chunks/sources.
    # Derived from ChromaDB cosine distance via similarity = 1 - distance.
    # Empty when retrieval skipped or distances were unavailable.
    scores: list[float] = Field(default_factory=list)
    query: str = ""


class CandidateEval(BaseModel):
    """Resume evaluation produced by the ResumeAnalyst agent."""

    skills_match_score: int = Field(ge=0, le=100, description="0-100 skills alignment score")
    experience_score: int = Field(ge=0, le=100, description="0-100 experience depth score")
    culture_fit_notes: str = ""
    red_flags: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    recommended_role: Optional[str] = None
    web_research_notes: str = ""
    candidate_name: Optional[str] = None  # Extracted from resume by ResumeAnalyst


class HRDecision(BaseModel):
    """Final hiring decision produced by the DecisionMaker agent."""

    decision: Literal["Strong Match", "Possible Match", "Needs Review", "Not Qualified"]
    reasoning: str
    next_steps: list[str] = Field(default_factory=list)
    policy_compliance_notes: str = ""
    overall_score: int = Field(
        ge=0, le=100, description="Composite score (weighted skills + experience)"
    )


# =============================================================================
# Final Output Model
# =============================================================================


class EvaluationResult(BaseModel):
    """Complete evaluation result written to SQLite and served by the web API."""

    candidate_id: str
    run_id: str
    filename: str
    timestamp_utc: str
    candidate_name: str = "Unknown"
    candidate_eval: CandidateEval
    hr_decision: HRDecision
    policy_context_summary: str = ""
    duration_seconds: Optional[float] = None
    token_usage: Optional[PipelineTokens] = None

    @property
    def decision(self) -> str:
        return self.hr_decision.decision

    @property
    def overall_score(self) -> int:
        return self.hr_decision.overall_score


# =============================================================================
# API / Chat Models (used by engine.py)
# =============================================================================


class ChatMessage(BaseModel):
    """Inbound chat message from the web UI."""

    message: str
    session_id: str = Field(default_factory=lambda: str(uuid4()))


class ProvenanceSource(BaseModel):
    """A single retrieved evidence chunk surfaced to the user.

    One entry per chunk returned by query_hr_policy (or analogous web/search
    tool). The UI renders these as a collapsed sources panel under the
    assistant's reply.
    """

    type: Literal["policy", "web"] = "policy"
    name: str  # filename for policy, URL or page title for web
    preview: str = ""  # first ~200 chars of the chunk
    full_text: Optional[str] = None  # full chunk, lazily revealed by UI
    score: Optional[float] = None  # similarity in [0,1] when available


class ProvenanceGrounding(BaseModel):
    """Structural signals about retrieval quality.

    Deliberately NOT named "confidence" — these are observable retrieval
    facts (how many chunks matched, how strong the top match was, which
    tools fired). LLM self-rated confidence is a Responsible AI anti-pattern
    and is intentionally absent from this model.
    """

    retrieved_chunks: int = 0
    chunks_above_threshold: int = 0  # chunks with score >= 0.5
    top_similarity: Optional[float] = None
    tools_invoked: list[str] = Field(default_factory=list)
    web_search_used: bool = False


class Provenance(BaseModel):
    """Transparency block attached to a chat reply."""

    sources: list[ProvenanceSource] = Field(default_factory=list)
    grounding: ProvenanceGrounding = Field(default_factory=ProvenanceGrounding)
    # Plain-text caveat the UI surfaces verbatim. Keeping it server-side
    # ensures every client sees the same wording — including any future
    # CLI/agent integration that bypasses the web UI.
    disclaimer: str = (
        "Grounding signals reflect retrieval quality, not answer correctness. "
        "Verify policy details against the source documents linked above."
    )


class ChatResponse(BaseModel):
    """Outbound chat response to the web UI."""

    reply: str
    session_id: str
    suggestions: list[str] = Field(default_factory=list)
    provenance: Optional[Provenance] = None


class UploadResponse(BaseModel):
    """Response after a resume file is uploaded."""

    candidate_id: str
    filename: str
    status: Literal["queued", "error"] = "queued"
    message: str = "Resume queued for evaluation. Check the Candidates page for results."


class CandidateSummary(BaseModel):
    """Lightweight summary for the candidates grid view."""

    candidate_id: str
    run_id: str
    filename: str
    candidate_name: str
    decision: str
    overall_score: int
    timestamp_utc: str
    duration_seconds: Optional[float] = None
