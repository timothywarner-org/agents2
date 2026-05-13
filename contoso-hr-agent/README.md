# Contoso HR Agent

An O'Reilly training demo showing production AI agent patterns through a realistic HR use case: automated resume screening for the open Microsoft Certified Trainer (MCT) position and HR policy Q&A.

## What It Demonstrates

| Pillar | Implementation |
|--------|----------------|
| **(a) Interactive chat** | Web chat UI + FastAPI `/api/chat` backed by ChatConciergeAgent ("Alex") with ChromaDB-grounded policy retrieval |
| **(b) Event-driven autonomy** | `ResumeWatcher` polls `data/incoming/` every 3 s -- drop a resume, the 3-agent pipeline runs automatically |
| **(c) Memory and state** | LangGraph `SqliteSaver` checkpoints + SQLite candidate store + two-layer chat history (localStorage + server JSON) |
| **(d) Multi-agent reasoning** | LangGraph StateGraph orchestrates 3 CrewAI agents in a parallel fan-out/fan-in pipeline: intake -> [PolicyExpert \|\| ResumeAnalyst] -> DecisionMaker, one `Crew.kickoff()` per node |
| **(e) Tool use and MCP** | FastMCP 2 server (stdio + SSE) demonstrating all 5 MCP primitives: tools, resources, resource templates, prompts, sampling (`ctx.sample()`), and elicitation (`ctx.elicit()`) + `query_hr_policy` tool (ChromaDB) + `brave_web_search` tool (Brave API) |

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Azure AI Foundry account with deployed chat + embedding models
- Node.js (optional, for MCP Inspector)

### Setup

```bash
# Windows
.\scripts\setup.ps1

# Linux/macOS
./scripts/setup.sh
```

Copy `.env.example` to `.env` and fill in your credentials:

```bash
AZURE_AI_FOUNDRY_ENDPOINT=https://scribe-foundry-resource.cognitiveservices.azure.com/
AZURE_AI_FOUNDRY_KEY=your-api-key
AZURE_AI_FOUNDRY_CHAT_MODEL=gpt-5.4-1
AZURE_AI_FOUNDRY_EMBEDDING_MODEL=text-embedding-ada-002-1
AZURE_AI_FOUNDRY_API_VERSION=2024-05-01-preview
BRAVE_API_KEY=your-brave-search-api-key       # free tier at brave.com/search/api
```

Seed the knowledge base:

```bash
uv run hr-seed --reset   # clears ChromaDB and re-ingests all policy docs (8 docs, 146 chunks)
```

### Start, Stop, Bounce

One command turns the whole stack on. Force-kills the four project ports first
(8090 engine, 8091 MCP SSE, 5273 Inspector proxy, 6374 Inspector UI), starts
the watcher + MCP Inspector + engine, and auto-opens **two browser tabs** —
the chat UI and the MCP Inspector.

```bash
# Windows
.\scripts\start.ps1     # start everything + open both tabs
.\scripts\stop.ps1      # kill everything (safe to run anytime)

# Linux/macOS
./scripts/start.sh
./scripts/stop.sh
```

**Bounce** = stop, then start. From an interactive session, just press **Ctrl+C**
in the start window — the script's cleanup handler kills every child process and
clears the ports, ready for the next start. If something orphaned a process
(crashed shell, killed terminal), `stop.ps1` is the recovery hatch.

The engine prints startup URIs:

- **Web UI:** <http://localhost:8090/chat.html>
- **API:** <http://localhost:8090/api>
- **Docs:** <http://localhost:8090/docs>
- **MCP Inspector:** <http://localhost:6374>

Open the Web UI in your browser. A global nav bar across all pages links to **Chat**, **Candidates**, **Pipeline Runs**, **Memory**, and **Responsible AI**.

## Agent Roster

```mermaid
%%{init: {'theme':'base','themeVariables':{'primaryColor':'#0078D4','primaryTextColor':'#FFFFFF','primaryBorderColor':'#004E8C','lineColor':'#767676','secondaryColor':'#E8E8E8','tertiaryColor':'#F3F2F1'}}}%%
flowchart TD
    subgraph concierge ["Chat Concierge (Alex)"]
        direction TB
        C_ROLE["Role: HR Chat Concierge"]
        C_TOOL["Tool: query_hr_policy"]
        C_WHEN["When: /api/chat request"]
        C_NOTE["verbose=False"]
    end

    subgraph parallel ["Parallel Fan-Out (pipeline nodes 2-3)"]
        direction LR
        subgraph policy ["Policy Expert"]
            direction TB
            P_ROLE["Role: HR Policy Expert"]
            P_TOOL["Tool: query_hr_policy"]
        end

        subgraph analyst ["Resume Analyst"]
            direction TB
            A_ROLE["Role: Sr. Talent Acquisition"]
            A_TOOL["Tool: brave_web_search"]
        end
    end

    subgraph decision ["Decision Maker"]
        direction TB
        D_ROLE["Role: Hiring Committee Chair"]
        D_TOOL["Tools: none (pure reasoning)"]
        D_WHEN["When: pipeline node 4"]
    end

    concierge -.- |"standalone"| concierge
    policy & analyst --> decision

    style concierge fill:#0078D4,stroke:#004E8C,color:#FFFFFF
    style parallel fill:#F3F2F1,stroke:#767676,color:#000000
    style policy fill:#107C10,stroke:#004E8C,color:#FFFFFF
    style analyst fill:#107C10,stroke:#004E8C,color:#FFFFFF
    style decision fill:#107C10,stroke:#004E8C,color:#FFFFFF
```

- **ChatConciergeAgent ("Alex")** -- Handles interactive chat Q&A via `/api/chat`. Uses `query_hr_policy` to ground every policy answer in ChromaDB. Set to `verbose=False` so crew output does not leak into chat responses.
- **PolicyExpertAgent** -- Pipeline node 2 (parallel branch). Retrieves Contoso HR policies from ChromaDB and assesses candidate compliance, recommended level (L1--L5), and compensation band. Runs concurrently with ResumeAnalyst.
- **ResumeAnalystAgent** -- Pipeline node 3 (parallel branch). Scores candidate fit (skills 0--100, experience 0--100) using resume analysis and optional Brave web search for credential verification. Runs concurrently with PolicyExpert; accepts `Optional[PolicyContext]` and falls back to standard policy text when policy context is unavailable.
- **DecisionMakerAgent** -- Pipeline node 4 (fan-in). Pure reasoning over prior agent outputs. Waits for both parallel branches to complete, then renders one of four dispositions with an overall score and concrete next steps.

## Evaluation Pipeline

```mermaid
%%{init: {'theme':'base','themeVariables':{'primaryColor':'#0078D4','primaryTextColor':'#FFFFFF','primaryBorderColor':'#004E8C','lineColor':'#767676','secondaryColor':'#E8E8E8','tertiaryColor':'#F3F2F1'}}}%%
sequenceDiagram
    actor User
    participant W as ResumeWatcher<br/>(3s poll)
    participant LG as LangGraph<br/>StateGraph
    participant PE as PolicyExpert<br/>CrewAI Crew
    participant CB as ChromaDB<br/>(146 chunks)
    participant RA as ResumeAnalyst<br/>CrewAI Crew
    participant BS as Brave Search<br/>API
    participant DM as DecisionMaker<br/>CrewAI Crew
    participant DB as SQLite<br/>(hr.db)
    participant UI as Web UI<br/>(candidates.html)

    User->>W: Drop resume into data/incoming/
    Note over User,W: .txt, .md, .pdf, .docx

    W->>LG: process_resume_file()
    LG->>LG: intake node (validate)

    Note over PE,RA: Parallel fan-out from intake

    par policy_expert branch
        LG->>PE: policy_expert node
        PE->>CB: query_hr_policy("trainer qualifications")
        CB-->>PE: policy chunks + sources
        PE-->>LG: PolicyContext + policy_meta (partial state)
    and resume_analyst branch
        LG->>RA: resume_analyst node
        RA->>BS: brave_web_search("verify certs")
        BS-->>RA: search results JSON
        RA-->>LG: CandidateEval (partial state)
    end

    Note over LG: Fan-in: merge partial states

    LG->>DM: decision_maker node (waits for both branches)
    DM-->>LG: HRDecision (disposition + reasoning)

    LG->>LG: notify node (assemble result)
    LG->>DB: save_result(EvaluationResult)

    UI->>DB: GET /api/candidates (auto-refresh 10s)
    DB-->>UI: candidate cards

    alt Strong Match (score 80+)
        Note over DM: Schedule interview immediately
    else Possible Match (score 55-79)
        Note over DM: Schedule technical screen
    else Needs Review (score 35-54)
        Note over DM: Recruiter follow-up needed
    else Not Qualified (score below 35)
        Note over DM: Decline with courtesy
    end
```

## Demo Walkthrough

### 1. Chat with the HR Assistant

Open `http://localhost:8090/chat.html` and ask policy questions:

- "What is Contoso's EEO policy?"
- "What is the salary band for a Level 3 trainer?"
- "How does the interview process work?"

Alex retrieves answers from the ChromaDB knowledge base (8 docs, 146 chunks) using the `query_hr_policy` tool. Six suggestion buttons appear on initial load for quick-start topics.

**Session management:** The chat UI includes a "New chat" button (resets the UI in-place with a new session ID, no page reload) and a "Clear history" button (wipes the current session only). A **Past Sessions** panel in the right sidebar lists previous conversations (fetched via `GET /api/chat/sessions`). Click any past session to switch context. The last 6 turns from the last 2 past sessions are injected into the ChatConcierge task prompt for cross-session continuity.

### 2. Upload a Resume

Click the upload area in the chat UI and upload any resume from `sample_resumes/` (for example, `RESUME_Sarah_Chen_AZ-104_Trainer-v3.txt`). The pipeline runs automatically:

1. **intake** -- validates the ResumeSubmission
2. **policy_expert** + **resume_analyst** -- run in PARALLEL (fan-out from intake). PolicyExpert queries ChromaDB; ResumeAnalyst scores skills/experience with optional Brave web search. Each returns only its own state keys for safe merge.
3. **decision_maker** -- fan-in: waits for both branches, then renders disposition (Strong Match / Possible Match / Needs Review / Not Qualified)
4. **notify** -- assembles EvaluationResult, writes to SQLite

Alternatively, drop any `.txt`, `.md`, `.pdf`, or `.docx` file directly into `data/incoming/` while the watcher is running.

### 3. View Candidate Results

Open `http://localhost:8090/candidates.html` -- auto-refreshes every 10 seconds. Click any card for the full evaluation detail including scores, strengths, red flags, reasoning, and next steps.

### 4. View Pipeline Runs

Open `http://localhost:8090/runs.html` -- the Pipeline Trace viewer. Split-panel layout: the left panel lists all pipeline runs, and the right panel shows a visual trace for the selected run. Parallel branches (policy_expert and resume_analyst) appear side-by-side with a "parallel fan-out" label.

### 5. Peek at Agent Memory

Open `http://localhost:8090/meta.html` -- the Memory page. Live snapshot of every persistent store the agent owns: `hr.db`, `checkpoints.db`, the ChromaDB collection (146 chunks, 8 docs), server-side chat sessions in `data/chat_sessions/`, and the outgoing result archive in `data/outgoing/`. Each card shows path, size, row/file count, last-modified time, and (for ChromaDB) the ingested document list. Backed by the `GET /api/meta` endpoint -- each per-store summary is wrapped in try/except so a future schema shift degrades to `{"error": ...}` per-store instead of breaking the whole response. Run a pipeline, then click Refresh and watch the counts change.

### 6. Map the Pipeline onto Responsible AI

Open `http://localhost:8090/rai.html` -- a static reference page that maps Microsoft's six Responsible AI principles (fairness, reliability and safety, privacy and security, inclusiveness, transparency, accountability) onto specific nodes and data stores in this pipeline. Below the principle grid is a curated list of Azure AI services that could be wired up to reinforce each principle -- Azure OpenAI content filters (already on), Azure AI Content Safety, AI Foundry Evaluations, Microsoft Purview, Defender for Cloud, Azure Monitor -- each annotated with where it would plug in. None of these services are wired into this demo; the banner at the top of the page makes that explicit. The page is a teaching artifact for the Responsible AI section of the course.

### 7. Observe Memory and Persistence

Each pipeline run uses a stable `thread_id` with LangGraph `SqliteSaver`. Run the same resume twice and the second run finds prior checkpoint state in `data/checkpoints.db`.

Chat history uses two-layer persistence (see Diagram D below). Pipeline results persist in `data/hr.db`. The Memory page (step 5) is the fastest way to see all of this from one view.

### 8. Explore the MCP Server

If you used `start.ps1`, the MCP Inspector is already running in the background (stdio mode). Otherwise, launch it manually:

```bash
npx @modelcontextprotocol/inspector uv run hr-mcp --stdio
```

The Inspector UI opens at `http://localhost:6374`. Try:

- **Tools:** `list_candidates` -- see all evaluations; `query_policy` with "What is the hiring process?"; `trigger_resume_evaluation` with resume text from a sample file
- **Sampling:** `generate_eval_summary` -- the server calls `ctx.sample()` to have the connected LLM write an executive summary for a candidate
- **Elicitation:** `confirm_and_evaluate` -- the server calls `ctx.elicit()` to present a confirmation form before running the expensive pipeline
- **Resource templates:** `candidate://{candidate_id}` and `policy://{topic}` -- parameterized resources that return formatted markdown
- **Prompts:** `disposition_review` -- fetches a candidate from SQLite and formats a review conversation using Context

## Data Model Chain

```mermaid
%%{init: {'theme':'base','themeVariables':{'primaryColor':'#0078D4','primaryTextColor':'#FFFFFF','primaryBorderColor':'#004E8C','lineColor':'#767676','secondaryColor':'#E8E8E8','tertiaryColor':'#F3F2F1'}}}%%
flowchart TD
    RS["ResumeSubmission<br/>---<br/>candidate_id<br/>filename<br/>raw_text"]
    PC["PolicyContext<br/>---<br/>chunks<br/>sources<br/>query"]
    CE["CandidateEval<br/>---<br/>skills_match_score<br/>experience_score<br/>red_flags"]
    HD["HRDecision<br/>---<br/>decision<br/>overall_score<br/>reasoning"]
    ER["EvaluationResult<br/>---<br/>candidate_id<br/>candidate_name<br/>timestamp_utc"]

    CHROMA[("ChromaDB<br/>146 chunks")]
    BRAVE["Brave Search API"]
    SQLITE[("SQLite<br/>hr.db")]

    RS -->|"parallel fan-out"| PC
    RS -->|"parallel fan-out"| CE
    CHROMA -.->|"policy chunks"| PC
    BRAVE -.->|"web results"| CE
    PC --> HD
    CE --> HD
    HD --> ER
    ER -->|"save_result()"| SQLITE

    style RS fill:#0078D4,stroke:#004E8C,color:#FFFFFF
    style PC fill:#50B0F0,stroke:#004E8C,color:#000000
    style CE fill:#50B0F0,stroke:#004E8C,color:#000000
    style HD fill:#50B0F0,stroke:#004E8C,color:#000000
    style ER fill:#0078D4,stroke:#004E8C,color:#FFFFFF
    style CHROMA fill:#107C10,stroke:#004E8C,color:#FFFFFF
    style BRAVE fill:#C08000,stroke:#C08000,color:#FFFFFF
    style SQLITE fill:#107C10,stroke:#004E8C,color:#FFFFFF
```

All models are Pydantic v2 BaseModel classes defined in `src/contoso_hr/models.py`. The pipeline passes serialized dicts (`model_dump()`) through LangGraph state for checkpoint compatibility.

## Chat Memory Architecture

```mermaid
%%{init: {'theme':'base','themeVariables':{'primaryColor':'#0078D4','primaryTextColor':'#FFFFFF','primaryBorderColor':'#004E8C','lineColor':'#767676','secondaryColor':'#E8E8E8','tertiaryColor':'#F3F2F1'}}}%%
flowchart LR
    LS["Browser<br/>localStorage<br/>(session_id)"]
    UI["Chat UI<br/>(chat.html)"]
    SIDEBAR["Past Sessions<br/>panel (sidebar)"]
    API["FastAPI<br/>/api/chat"]
    SESSIONS_API["GET /api/chat/sessions"]
    ALEX["ChatConciergeAgent<br/>(Alex)"]
    QHP["query_hr_policy<br/>tool"]
    CHROMA[("ChromaDB")]
    JSON["data/chat_sessions/<br/>{session_id}.json"]
    PAST["Past session context<br/>(last 6 turns from<br/>last 2 sessions)"]

    LS <-->|"instant restore<br/>on reload"| UI
    SIDEBAR -->|"GET sessions list"| SESSIONS_API
    SESSIONS_API -->|"session list +<br/>preview + count"| SIDEBAR
    SIDEBAR -->|"click to switch"| UI
    UI -->|"POST {message,<br/>session_id}"| API
    API -->|"build context"| PAST
    PAST -->|"inject into<br/>task prompt"| ALEX
    API -->|"Crew.kickoff()"| ALEX
    ALEX -->|"tool call"| QHP
    QHP -->|"semantic search"| CHROMA
    CHROMA -->|"policy chunks"| QHP
    QHP -->|"grounded answer"| ALEX
    ALEX -->|"reply"| API
    API -->|"write-through"| JSON
    API -->|"ChatResponse"| UI

    style LS fill:#E8E8E8,stroke:#767676,color:#000000
    style UI fill:#0078D4,stroke:#004E8C,color:#FFFFFF
    style SIDEBAR fill:#E8E8E8,stroke:#767676,color:#000000
    style SESSIONS_API fill:#50B0F0,stroke:#004E8C,color:#000000
    style API fill:#0078D4,stroke:#004E8C,color:#FFFFFF
    style ALEX fill:#50B0F0,stroke:#004E8C,color:#000000
    style QHP fill:#50B0F0,stroke:#004E8C,color:#000000
    style CHROMA fill:#107C10,stroke:#004E8C,color:#FFFFFF
    style JSON fill:#E8E8E8,stroke:#767676,color:#000000
    style PAST fill:#F3F2F1,stroke:#767676,color:#000000
```

Two-layer persistence keeps chat responsive and durable:

- **Client-side:** `localStorage` keyed by `session_id` -- instant restore on page reload, no server round-trip.
- **Server-side:** JSON files in `data/chat_sessions/{session_id}.json` -- survives browser clears, accessible via API.
- **Cross-session context:** The last 6 turns from the last 2 past sessions are injected into the ChatConcierge task prompt, giving Alex awareness of recent prior conversations.

**Session management UI:** "New chat" resets the UI in-place with a fresh session ID (no reload). "Clear history" wipes the current session only. The Past Sessions sidebar panel lists all previous sessions with message count, preview, and timestamp.

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/chat/sessions` | GET | List all chat sessions with message count, preview, and timestamp |
| `/api/chat/history/{session_id}` | GET | Retrieve persisted chat history for a session |
| `/api/chat/history/{session_id}` | DELETE | Clear persisted chat history for a session |

## Project Structure

```
contoso-hr-agent/
├── src/contoso_hr/
│   ├── pipeline/              # LangGraph + CrewAI pipeline
│   │   ├── graph.py           # StateGraph: 5 nodes (intake, policy_expert,
│   │   │                      #   resume_analyst, decision_maker, notify)
│   │   ├── agents.py          # ChatConciergeAgent, PolicyExpertAgent,
│   │   │                      #   ResumeAnalystAgent, DecisionMakerAgent
│   │   ├── tasks.py           # CrewAI Task factories (inject state into prompts)
│   │   ├── tools.py           # @tool: query_hr_policy, brave_web_search
│   │   └── prompts.py         # Agent system prompts (persona + output format)
│   ├── knowledge/             # ChromaDB vectorization + retrieval
│   │   ├── vectorizer.py      # Ingest policy docs -> embeddings -> ChromaDB
│   │   └── retriever.py       # query_policy_knowledge(question, k) -> PolicyContext
│   ├── watcher/               # File watcher for data/incoming/
│   │   ├── resume_watcher.py  # ResumeWatcher: polls every 3s
│   │   └── process_resume.py  # Runs LangGraph pipeline + saves result
│   ├── memory/                # Persistence layer
│   │   ├── sqlite_store.py    # HRSQLiteStore: candidates + evaluations tables
│   │   └── checkpoints.py     # LangGraph SqliteSaver wrapper
│   ├── mcp_server/            # FastMCP 2 (stdio + SSE)
│   │   ├── server.py          # All 5 MCP primitives (tools, resources, prompts, sampling, elicitation)
│   │   └── __main__.py        # Entry point (--stdio flag for Inspector, else SSE on 8091)
│   ├── util/                  # Utilities
│   │   ├── port_utils.py      # force_kill_port(port)
│   │   ├── fs.py              # ensure_dirs()
│   │   └── token_tracking.py  # Token usage tracking
│   ├── engine.py              # FastAPI app (port 8090, serves web/ static files)
│   ├── config.py              # Config dataclass, Azure AI Foundry LLM/embeddings
│   ├── models.py              # Pydantic v2 data contracts (full model chain)
│   └── logging_setup.py       # Rich-based structured logging
├── web/                       # HTML/JS/CSS frontend (nav bar across all pages)
│   ├── chat.html / chat.js    # Chat UI with upload, session mgmt, past sessions
│   ├── candidates.html / .js  # Candidate results grid (auto-refresh)
│   ├── runs.html / runs.js    # Pipeline Trace viewer (split-panel, parallel viz)
│   ├── meta.html              # Memory page -- live snapshot of all 5 stores via /api/meta
│   ├── rai.html               # Responsible AI -- 6 principles + Azure service map (static)
│   └── style.css              # Shared styles
├── data/                      # Runtime data (gitignored)
│   ├── incoming/              # Resume drop folder (watched)
│   ├── processed/             # Archived after evaluation
│   ├── outgoing/              # Result JSON files
│   ├── chroma/                # ChromaDB vector store
│   ├── chat_sessions/         # Server-side chat history
│   ├── hr.db                  # SQLite candidate store
│   └── checkpoints.db         # LangGraph SqliteSaver
├── sample_resumes/            # 13 trainer candidate resumes (RESUME_*.txt)
├── sample_knowledge/          # HR policy docs (.md, .pdf, .docx, .pptx)
├── scripts/                   # Setup and launch scripts
│   ├── setup.ps1 / setup.sh
│   ├── start.ps1 / start.sh
│   └── start_mcp.ps1 / .sh
├── tests/                     # Pytest test suite
└── pyproject.toml             # Project config (uv, ruff, scripts)
```

## API Reference

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/chat` | POST | Send a chat message to Alex (ChatConciergeAgent). Body: `{message, session_id}`. Returns `{reply, session_id, suggestions}`. |
| `/api/upload` | POST | Upload a resume file (`.txt`, `.md`, `.pdf`, `.docx`). Saved to `data/incoming/` for watcher pickup. Returns `{candidate_id, filename, status, message}`. |
| `/api/candidates` | GET | List evaluated candidates. Query params: `limit` (default 50), `decision` (filter). Returns `CandidateSummary[]`. |
| `/api/candidates/{id}` | GET | Full `EvaluationResult` for one candidate. 404 if not found. |
| `/api/stats` | GET | Aggregate statistics: total evaluations, decision breakdown, average score, average duration. |
| `/api/meta` | GET | Live snapshot of every persistent store (hr.db, checkpoints.db, chroma/, chat_sessions/, outgoing/) with path, size, row/file count, mtime, and the ChromaDB ingested-doc list. Each per-store probe is try/except-wrapped so one schema shift cannot break the whole response. Powers `meta.html`. |
| `/api/chat/sessions` | GET | List all chat sessions with message count, preview, and timestamp. |
| `/api/chat/history/{session_id}` | GET | Retrieve persisted chat history for a session. |
| `/api/chat/history/{session_id}` | DELETE | Clear persisted chat history for a session. |
| `/api/health` | GET | Health check. Returns `{status: "ok"}`. |

## Sample Resume Corpus

The 13 `RESUME_*.txt` files in `sample_resumes/` cover three quality tiers for MCT trainer screening:

| Tier | Candidates | Description |
|------|-----------|-------------|
| **Excellent** | Sarah Chen, Alice Zhang, Rachel Torres, Tomoko Sato | Active MCT, multiple Azure/M365/Security certs, strong training metrics (100+ sessions, 4.7+ ratings) |
| **Mid-tier** | Bob Martinez, David Park, James Okafor, Carol Okonkwo, Priya Kapoor | Some relevant certs or experience, but gaps in training delivery or credentials |
| **Poor match** | David Kim, Kevin Walsh, Marcus Johnson, Alex Rivera | No MCT, no training experience, or entirely different career focus |

## Azure AI Foundry Deployment

| Setting | Value |
|---------|-------|
| Resource group | `scribe-rg` |
| Resource name | `scribe-foundry-resource` |
| Endpoint | `https://scribe-foundry-resource.cognitiveservices.azure.com/` |
| Region | `eastus2` |
| Chat deployment | `gpt-5.4-1` (model `gpt-5.4`, version `2026-03-05`) |
| Embedding deployment | `text-embedding-ada-002-1` (model `text-embedding-ada-002`) |
| API version | `2024-05-01-preview` |

Teardown when finished — substitute YOUR resource group, never run against shared infra:

```bash
az group delete --name <your-resource-group> --yes --no-wait
```

## MCP Server (FastMCP 2 -- All 5 Primitives)

Supports two transports: **stdio** (primary for local dev with MCP Inspector) and **SSE** (port 8091, for programmatic clients).

```bash
# stdio (recommended for Inspector -- auto-started by start.ps1)
npx @modelcontextprotocol/inspector uv run hr-mcp --stdio

# SSE (standalone, binds port 8091)
uv run hr-mcp
```

### Primitive 1 -- Tools

| Tool | Parameters | Purpose |
|------|-----------|---------|
| `get_candidate` | `candidate_id` | Full EvaluationResult for one candidate |
| `list_candidates` | `limit`, `decision_filter` | Recent evaluations (filterable by disposition) |
| `trigger_resume_evaluation` | `resume_text`, `filename` | Run the full pipeline directly (bypasses watcher) |
| `query_policy` | `question` | ChromaDB semantic search over HR policy docs |
| `generate_eval_summary` | `candidate_id` | **Sampling:** calls `ctx.sample()` to have the connected LLM write an executive summary |
| `confirm_and_evaluate` | `resume_text`, `filename` | **Elicitation:** calls `ctx.elicit()` to present a confirmation form before running the pipeline |

### Primitive 2 -- Resources

**Static resources:**

| URI | Content |
|-----|---------|
| `schema://candidate` | EvaluationResult JSON schema |
| `stats://evaluations` | Aggregate evaluation statistics |
| `samples://resumes` | List of available sample resume files |
| `config://settings` | Current application configuration (no secrets) |

**Parameterized resource templates:**

| URI Template | Content |
|--------------|---------|
| `candidate://{candidate_id}` | Formatted markdown profile for one evaluated candidate |
| `policy://{topic}` | HR policy chunks for a topic keyword (semantic search, top 3 results) |

### Primitive 3 -- Prompts

| Prompt | Parameters | Returns | Purpose |
|--------|-----------|---------|---------|
| `evaluate_resume` | `resume_text`, `role` (optional) | `list[dict]` (multi-message) | System persona + scoring rubric + assistant primer for structured resume evaluation |
| `policy_query` | `question` | `list[dict]` (multi-message) | Grounding instruction + policy question as separate user turns |
| `disposition_review` | `candidate_id` | `list[dict]` (multi-message) | Uses Context to fetch live candidate data from SQLite and format a review conversation |

### Primitive 4 -- Sampling

Used in: `generate_eval_summary` tool. The server sends structured candidate evaluation data to the connected LLM via `ctx.sample()` and receives back a concise 3--5 sentence executive summary suitable for a hiring manager briefing. This inverts the normal flow -- the server drives the LLM, not the other way around.

### Primitive 5 -- Elicitation

Used in: `confirm_and_evaluate` tool. Before running the expensive LangGraph + CrewAI pipeline (30--120 seconds, LLM API calls), the server calls `ctx.elicit()` to pause and present a confirmation form collecting `confirmed` (bool) and `priority` (str). If the user declines or cancels, the pipeline never runs. Requires a client that supports elicitation (MCP Inspector supports it in stdio mode).

## Remote MCP Servers (.mcp.json)

- **Azure MCP** (`@azure/mcp`) -- inspect/provision Azure AI Foundry resources
- **Brave Search MCP** (`@modelcontextprotocol/server-brave-search`) -- web search (also used directly in ResumeAnalystAgent)

## Extension Ideas

- Email notifications via Microsoft Graph API when a candidate is evaluated
- Add a 5th agent: InterviewScheduler that proposes calendar slots
- Connect Azure MCP to provision Foundry resources automatically in the demo
- Upgrade ChromaDB to Azure AI Search for enterprise-scale vector retrieval
- Add token usage tracking and cost dashboards to the web UI
- Implement webhook notifications for real-time pipeline status updates
