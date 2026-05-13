# Contoso HR Agent -- O'Reilly AI Agents Course

<p align="center">
   <img src="images/cover.png" alt="Build Production-Ready AI Agents cover" width="360">
</p>

**O'Reilly Live Learning Course** | 4 Hours | LangGraph - CrewAI - MCP - Azure AI Foundry

[![Website TechTrainerTim.com](https://img.shields.io/badge/Website-TechTrainerTim.com-0a66c2)](https://techtrainertim.com)
[![LinkedIn timothywarner](https://img.shields.io/badge/LinkedIn-timothywarner-0a66c2?logo=linkedin)](https://www.linkedin.com/in/timothywarner/)
[![GitHub timothywarner-org](https://img.shields.io/badge/GitHub-timothywarner--org-181717?logo=github)](https://github.com/timothywarner-org)
[![O'Reilly Author Page](https://img.shields.io/badge/O'Reilly-Author%20Page-cf2f1d)](https://learning.oreilly.com/search/?query=Tim%20Warner)

**Contact:** [Website](https://techtrainertim.com) | [LinkedIn](https://www.linkedin.com/in/timothywarner/) | [GitHub](https://github.com/timothywarner-org) | [O'Reilly](https://learning.oreilly.com/search/?query=Tim%20Warner)

---

## What It Demonstrates

The **Contoso HR Agent** is an automated resume screening and HR policy Q&A system that screens candidates for a Microsoft Certified Trainer (MCT) position. It showcases five pillars of production-ready AI agent design:

| Pillar | What It Shows | Where to Look |
|--------|---------------|---------------|
| **Interactive Chat** | Web chat UI backed by a CrewAI ChatConcierge agent grounded in ChromaDB policy retrieval; past-session context (last 6 turns from last 2 sessions) injected into each prompt | `web/chat.html`, `engine.py /api/chat` |
| **Event-Driven Autonomy** | File watcher polls `data/incoming/` -- drop a resume and the full pipeline runs automatically | `watcher/resume_watcher.py` |
| **Memory and State** | LangGraph `SqliteSaver` checkpoints + SQLite candidate store + server-side chat session JSON | `memory/`, `data/hr.db`, `data/checkpoints.db` |
| **Parallel LLM Reasoning** | LangGraph StateGraph fan-out/fan-in: `policy_expert` and `resume_analyst` run **concurrently**, then fan-in to `decision_maker` | `pipeline/graph.py`, `pipeline/agents.py` |
| **MCP Tool Calling** | FastMCP 2 SSE server exposes tools, resources, and prompts to external AI clients | `mcp_server/server.py` (port 8091) |

---

## System Architecture

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#0078D4', 'primaryTextColor': '#FFFFFF', 'primaryBorderColor': '#005A9E', 'secondaryColor': '#E8E8E8', 'tertiaryColor': '#50B0F0', 'lineColor': '#767676', 'fontFamily': 'Segoe UI, sans-serif', 'fontSize': '14px'}}}%%
flowchart LR
    subgraph Browser["Browser"]
        direction TB
        ChatUI["chat.html\nChat + Upload"]
        CandUI["candidates.html\nCandidate Grid"]
        RunsUI["runs.html\nPipeline Trace"]
        MetaUI["meta.html\nMemory Stores"]
        RAIUI["rai.html\nResponsible AI"]
    end

    subgraph FastAPI["FastAPI :8090"]
        direction TB
        ChatAPI["/api/chat\n/api/chat/sessions"]
        UploadAPI["/api/upload"]
        CandAPI["/api/candidates\n/api/candidates/{id}\n/api/stats"]
        MetaAPI["/api/meta\nLive store snapshot"]
        HealthAPI["/api/health"]
    end

    subgraph Agents["CrewAI Agents"]
        direction TB
        Concierge["ChatConcierge\n'Alex'\nChat + Q&A"]
        Pipeline["LangGraph Pipeline\nparallel fan-out/fan-in"]
    end

    subgraph Storage["Data Stores"]
        direction TB
        SQLite[("SQLite\nhr.db")]
        Chroma[("ChromaDB\n146 chunks\n8 docs")]
        Checkpoints[("Checkpoints\ncheckpoints.db")]
        ChatMem[("Chat Sessions\nJSON files")]
    end

    Azure(["Azure AI Foundry\ngpt-5.4-1\ntext-embedding-ada-002-1"])
    MCP["FastMCP :8091\nSSE Server"]
    Watcher["File Watcher\ndata/incoming/"]
    Incoming[/"Resume files\n.txt .md .pdf .docx"/]

    ChatUI -- "chat messages" --> ChatAPI
    ChatUI -- "file upload" --> UploadAPI
    CandUI -- "read results" --> CandAPI
    RunsUI -- "trace data" --> CandAPI
    MetaUI -- "store snapshot" --> MetaAPI

    ChatAPI --> Concierge
    UploadAPI -- "saves to\ndata/incoming/" --> Incoming
    Incoming -- "polls every 3s" --> Watcher
    Watcher --> Pipeline

    Concierge --> Chroma
    Concierge --> Azure
    Pipeline --> SQLite
    Pipeline --> Chroma
    Pipeline --> Checkpoints
    Pipeline --> Azure
    ChatAPI --> ChatMem

    CandAPI --> SQLite
    MetaAPI --> SQLite
    MetaAPI --> Chroma
    MetaAPI --> Checkpoints
    MetaAPI --> ChatMem

    MCP -. "tools + resources" .-> Pipeline
    MCP -. "tools + resources" .-> SQLite

    style Browser fill:#E8E8E8,stroke:#767676,color:#000000
    style FastAPI fill:#0078D4,stroke:#005A9E,color:#FFFFFF
    style Agents fill:#50B0F0,stroke:#0078D4,color:#000000
    style Storage fill:#107C10,stroke:#0B5A0B,color:#FFFFFF
    style Azure fill:#C08000,stroke:#8B5E00,color:#FFFFFF
    style MCP fill:#E8E8E8,stroke:#767676,color:#000000
    style Watcher fill:#E8E8E8,stroke:#767676,color:#000000
    style Incoming fill:#E8E8E8,stroke:#767676,color:#000000
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Azure AI Foundry account with a chat deployment and an embedding deployment (the reference env uses `gpt-5.4-1` and `text-embedding-ada-002-1`; substitute your own deployment names in `.env`)
- Optional: [Brave Search API key](https://api.search.brave.com/register) (free tier, 2000 queries/month)
- Optional: Node.js (for MCP Inspector)

### Setup

```bash
# 1. Clone and enter the project
git clone https://github.com/timothywarner-org/agents2.git
cd agents2/contoso-hr-agent

# 2. Create venv, install dependencies, seed ChromaDB
uv venv && uv sync && uv run hr-seed

# 3. Configure credentials
cp .env.example .env
# Edit .env and set:
#   AZURE_AI_FOUNDRY_ENDPOINT=https://your-account.cognitiveservices.azure.com/
#   AZURE_AI_FOUNDRY_KEY=your-key
#   AZURE_AI_FOUNDRY_CHAT_MODEL=gpt-5.4-1
#   AZURE_AI_FOUNDRY_EMBEDDING_MODEL=text-embedding-ada-002-1

# 4. Start everything (FastAPI + file watcher)
./scripts/start.sh          # Linux / macOS
.\scripts\start.ps1         # Windows PowerShell

# 5. Open the UI
#    Chat:           http://localhost:8090/chat.html
#    Candidates:     http://localhost:8090/candidates.html
#    Pipeline Runs:  http://localhost:8090/runs.html
#    Memory:         http://localhost:8090/meta.html
#    Responsible AI: http://localhost:8090/rai.html
```

### Individual Services

```bash
uv run hr-engine            # FastAPI only (port 8090)
uv run hr-watcher           # File watcher only
uv run hr-mcp               # FastMCP 2 server (port 8091)
uv run hr-seed --reset      # Clear and re-seed ChromaDB
```

---

## LangGraph Pipeline Flow (Parallel Fan-Out / Fan-In)

The pipeline runs once per resume. LangGraph owns **when** and **state**. CrewAI owns **who** and **what**. Each node wraps exactly one `Crew.kickoff()` call.

**Key teaching point:** After `intake`, the `policy_expert` and `resume_analyst` nodes run **concurrently** (parallel fan-out). Both must complete before `decision_maker` begins (fan-in). This pattern demonstrates how LangGraph supports parallel branches for independent work, reducing total pipeline latency.

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#0078D4', 'primaryTextColor': '#FFFFFF', 'primaryBorderColor': '#005A9E', 'secondaryColor': '#E8E8E8', 'tertiaryColor': '#50B0F0', 'lineColor': '#767676', 'fontFamily': 'Segoe UI, sans-serif', 'fontSize': '14px'}}}%%
flowchart TD
    Start([Resume Submitted]) --> Intake

    subgraph Node1["Node 1: intake"]
        Intake["Validate\nResumeSubmission"]
    end

    Intake -- "fan-out" --> PE_Agent
    Intake -- "fan-out" --> RA_Agent

    subgraph Parallel["Parallel Execution"]
        direction LR

        subgraph Node2["Node 2: policy_expert"]
            PE_Agent["PolicyExpertAgent\nCrewAI"]
            PE_Tool["query_hr_policy\nChromaDB RAG"]
            PE_Agent --> PE_Tool
        end

        subgraph Node3["Node 3: resume_analyst"]
            RA_Agent["ResumeAnalystAgent\nCrewAI"]
            RA_Tool["brave_web_search\nBrave API"]
            RA_Agent --> RA_Tool
        end
    end

    PE_Agent -- "fan-in" --> DM_Agent
    RA_Agent -- "fan-in" --> DM_Agent

    subgraph Node4["Node 4: decision_maker"]
        DM_Agent["DecisionMakerAgent\nCrewAI"]
        DM_Note["Pure reasoning\nNo external tools"]
        DM_Agent -.- DM_Note
    end

    subgraph Node5["Node 5: notify"]
        Notify["Assemble\nEvaluationResult\nLog summary"]
    end

    DM_Agent -- "HRDecision\n4 dispositions" --> Notify

    Notify --> Done([Pipeline Complete])

    subgraph DataStores["Persistent Storage"]
        direction LR
        DB[("SQLite\nhr.db\ncandidates +\nevaluations")]
        VDB[("ChromaDB\n146 chunks\n8 policy docs")]
        CP[("Checkpoints\ncheckpoints.db\nLangGraph state")]
    end

    Notify -- "write result" --> DB
    PE_Tool -- "semantic\nsearch" --> VDB
    Node1 -- "checkpoint" --> CP
    Node2 -- "checkpoint" --> CP
    Node3 -- "checkpoint" --> CP
    Node4 -- "checkpoint" --> CP
    Node5 -- "checkpoint" --> CP

    style Node1 fill:#E8E8E8,stroke:#767676,color:#000000
    style Parallel fill:#F3F2F1,stroke:#0078D4,color:#000000
    style Node2 fill:#0078D4,stroke:#005A9E,color:#FFFFFF
    style Node3 fill:#50B0F0,stroke:#0078D4,color:#000000
    style Node4 fill:#C08000,stroke:#8B5E00,color:#FFFFFF
    style Node5 fill:#107C10,stroke:#0B5A0B,color:#FFFFFF
    style DataStores fill:#E8E8E8,stroke:#767676,color:#000000
    style Start fill:#5DB85D,stroke:#107C10,color:#FFFFFF
    style Done fill:#5DB85D,stroke:#107C10,color:#FFFFFF
```

### Data Model Chain

Each node produces a Pydantic v2 model that feeds the next:

```
ResumeSubmission  (input: candidate name, resume text, file path)
  -> PolicyContext     (ChromaDB retrieval: relevant policy chunks + sources)
  -> CandidateEval     (skills_match_score, experience_score, strengths, red_flags)
  -> HRDecision        (disposition + reasoning + next_steps + overall_score)
  -> EvaluationResult  (final composite written to SQLite + served by API)
```

### Four Dispositions

| Disposition | Meaning |
|-------------|---------|
| **Strong Match** | Candidate exceeds MCT requirements; recommend immediate interview |
| **Possible Match** | Candidate meets most requirements; some gaps to discuss |
| **Needs Review** | Candidate has potential but significant gaps; needs committee review |
| **Not Qualified** | Candidate does not meet minimum requirements for the MCT role |

---

## Web UI (Five Pages)

All five pages share a global navigation bar: **Chat | Candidates | Pipeline Runs | Memory | Responsible AI**.

| Page | URL | Purpose |
|------|-----|---------|
| **Chat** | `/chat.html` | Chat with the ChatConcierge agent ("Alex"), upload resumes, "New chat" and "Clear history" buttons, Past Sessions panel in right sidebar with click-to-restore |
| **Candidates** | `/candidates.html` | Evaluation grid with detail modal for each candidate |
| **Pipeline Runs** | `/runs.html` | Pipeline Trace viewer -- split-panel view showing full pipeline execution per run, including the parallel `policy_expert` and `resume_analyst` branches |
| **Memory** | `/meta.html` | Live snapshot of every persistent store the agent owns (hr.db, checkpoints.db, ChromaDB, chat_sessions/, outgoing/) -- path, size, row/file count, mtime, ingested doc list. Refresh button re-runs the snapshot. Backed by `/api/meta` |
| **Responsible AI** | `/rai.html` | Static reference page mapping Microsoft's 6 RAI principles (fairness, reliability and safety, privacy and security, inclusiveness, transparency, accountability) onto this pipeline, plus the Azure AI services that could be wired up to reinforce each pillar |

---

## API Endpoints

| Method | Route | Purpose |
|--------|-------|---------|
| POST | `/api/chat` | Send a chat message to the ChatConcierge agent |
| POST | `/api/upload` | Upload a resume file to `data/incoming/` |
| GET | `/api/candidates` | List all evaluated candidates |
| GET | `/api/candidates/{id}` | Get full evaluation for one candidate |
| GET | `/api/stats` | Aggregate evaluation statistics |
| GET | `/api/meta` | Live snapshot of every persistent store (paths, sizes, counts, mtimes) -- powers the Memory page |
| GET | `/api/health` | Health check |
| GET | `/api/chat/history/{id}` | Retrieve chat history for a session |
| DELETE | `/api/chat/history/{id}` | Delete chat history for a session |
| GET | `/api/chat/sessions` | List all chat sessions |

---

## Demo Walkthrough

Follow these five steps to see every pillar in action:

### Step 1 -- Chat with the Concierge

Open `http://localhost:8090/chat.html` and ask a policy question:

> "What are the minimum qualifications for the MCT trainer position?"

The ChatConcierge agent retrieves policy chunks from ChromaDB and responds with grounded answers -- no hallucination. Use the Past Sessions sidebar to restore earlier conversations.

### Step 2 -- Upload a Resume

Use the upload button in `chat.html` to submit one of the sample resumes (e.g., `RESUME_Sarah_Chen_AZ-104_Trainer-v3.txt`). The file lands in `data/incoming/`.

### Step 3 -- Watch the Pipeline Run

The file watcher detects the new resume within 3 seconds and triggers the full LangGraph pipeline. Watch the terminal for Rich-formatted logs as each agent runs:

1. **intake** validates the submission
2. **policy_expert** and **resume_analyst** run **in parallel** (fan-out)
   - policy_expert retrieves relevant HR policies from ChromaDB
   - resume_analyst scores the candidate (optionally searches the web via Brave)
3. **decision_maker** renders a disposition with reasoning (fan-in)
4. **notify** assembles the final result and writes to SQLite

### Step 4 -- Review Results and Traces

Open `http://localhost:8090/candidates.html` to see the evaluation grid. Click any candidate for the full detail modal. Open `http://localhost:8090/runs.html` to inspect the pipeline trace for each run, including the parallel branches.

### Step 5 -- Peek at Agent Memory

Open `http://localhost:8090/meta.html` to see every persistent store the agent owns -- `hr.db`, `checkpoints.db`, the ChromaDB collection, server-side chat sessions, and the outgoing result archive -- with path, size, row/file count, and last-modified time per store. Run a pipeline, click Refresh, watch the counts change. This is the fastest way to show learners that "memory" in an agent isn't a single store; it's five layered ones.

### Step 6 -- Map the Pipeline onto Responsible AI

Open `http://localhost:8090/rai.html` for a static reference page mapping Microsoft's six Responsible AI principles (fairness, reliability and safety, privacy and security, inclusiveness, transparency, accountability) onto specific nodes and data stores in this pipeline, plus the Azure AI services that could be wired up to enforce each principle (Content Safety, AI Foundry Evaluations, Defender for Cloud, Purview, and friends).

### Step 7 -- Explore MCP

Start the MCP server with `uv run hr-mcp` and use [MCP Inspector](https://github.com/modelcontextprotocol/inspector) to call tools like `list_candidates`, `query_policy`, and `trigger_resume_evaluation`. This shows how external AI clients can interact with the pipeline programmatically.

---

## Engine Startup Output

When the engine starts, it prints four URIs:

```
  Web UI:  http://localhost:8090/chat.html
  API:     http://localhost:8090/api/
  Docs:    http://localhost:8090/docs
  MCP SSE: http://localhost:8091/sse
```

Ports 8090 (engine) and 8091 (MCP) are force-killed on every startup to avoid "address already in use" errors.

---

## Project Structure

```
agents2/
├── README.md                          # This file (course-level overview)
├── CLAUDE.md                          # Claude Code guidance for this repo
├── AGENTS.md                          # Repository guidelines for AI agents
├── contoso-hr-agent/                  # Primary demo project
│   ├── src/contoso_hr/
│   │   ├── pipeline/
│   │   │   ├── graph.py               # LangGraph StateGraph, parallel fan-out/fan-in,
│   │   │   │                          #   HRState, 5 node functions, create_hr_graph()
│   │   │   ├── agents.py             # 4 CrewAI agents (ChatConcierge, PolicyExpert,
│   │   │   │                          #   ResumeAnalyst, DecisionMaker)
│   │   │   ├── tasks.py              # CrewAI Task factories
│   │   │   ├── prompts.py            # System prompts for all 4 agents
│   │   │   └── tools.py              # query_hr_policy (ChromaDB), brave_web_search
│   │   ├── knowledge/
│   │   │   ├── vectorizer.py          # Ingest policy docs -> Azure embeddings -> ChromaDB
│   │   │   └── retriever.py           # query_policy_knowledge() -> PolicyContext
│   │   ├── memory/
│   │   │   ├── sqlite_store.py        # candidates + evaluations tables
│   │   │   └── checkpoints.py         # LangGraph SqliteSaver wrapper
│   │   ├── mcp_server/
│   │   │   └── server.py              # FastMCP 2 SSE server (port 8091)
│   │   ├── watcher/
│   │   │   └── resume_watcher.py      # Polls data/incoming/ every 3 seconds
│   │   ├── util/
│   │   │   └── port_utils.py          # force_kill_port() for clean startup
│   │   ├── engine.py                  # FastAPI server (port 8090), web UI + REST API
│   │   ├── config.py                  # Azure AI Foundry config, LLM/embedding factories
│   │   ├── models.py                  # Pydantic v2 data contracts (full model chain)
│   │   └── logging_setup.py           # Rich-formatted structured logging
│   ├── web/
│   │   ├── chat.html                  # Chat UI + resume upload + Past Sessions sidebar
│   │   ├── chat.js                    # Chat client logic + localStorage
│   │   ├── candidates.html            # Evaluation grid + detail modal
│   │   ├── candidates.js              # Candidate grid client logic
│   │   ├── runs.html                  # Pipeline Trace viewer (split-panel, parallel branches)
│   │   ├── runs.js                    # Pipeline trace client logic
│   │   ├── meta.html                  # Memory page -- live snapshot of all 5 stores via /api/meta
│   │   ├── rai.html                   # Responsible AI page -- 6 principles + Azure service map
│   │   └── style.css                  # Shared styles
│   ├── sample_resumes/                # 13 trainer candidate resumes (3 quality tiers)
│   ├── sample_knowledge/              # 8 HR policy documents (PDF, DOCX, PPTX, MD)
│   ├── data/                          # Runtime data (gitignored)
│   │   ├── incoming/                  # Resume drop folder (watcher polls here)
│   │   ├── processed/                 # Resumes after pipeline completes
│   │   ├── outgoing/                  # JSON evaluation results
│   │   ├── chroma/                    # ChromaDB vector store (146 chunks, 8 docs)
│   │   ├── chat_sessions/             # Server-side chat history JSON
│   │   ├── hr.db                      # SQLite candidate + evaluation store
│   │   └── checkpoints.db             # LangGraph state checkpoints
│   ├── scripts/                       # Setup and launch scripts (sh + ps1)
│   ├── tests/                         # pytest test suite
│   ├── pyproject.toml                 # uv project config + CLI entry points
│   ├── .env.example                   # Environment variable template
│   └── .mcp.json                      # MCP client configuration
├── oreilly-agent-mvp/                 # LEGACY reference (issue triage pipeline) -- not active
├── copilot-studio/                    # Copilot Studio demo assets
├── claude-agent/                      # Claude Code agent configuration
├── docs/                              # Course materials and supporting assets
└── images/                            # Course images
```

---

## Sample Resume Corpus

The 13 sample resumes in `contoso-hr-agent/sample_resumes/` span three quality tiers to exercise every disposition path:

| Tier | Expected Disposition | Resumes | Why |
|------|---------------------|---------|-----|
| **Strong** | Strong Match | Sarah Chen (AZ-104), Alice Zhang (Azure), Rachel Torres (DevOps), David Park (M365 Security), James Okafor (Security), Tomoko Sato (Educator) | Active MCT, deep cert stacks, 4.5+ learner ratings, curriculum authorship |
| **Mid** | Possible Match / Needs Review | Bob Martinez (M365), Carol Okonkwo (Data), Priya Kapoor (AI Engineer), Marcus Johnson (Cloud Engineer) | Some certs but gaps in training delivery, MCT status, or specialization |
| **Weak** | Not Qualified | David Kim (Finance PM), Kevin Walsh (Marketing), Alex Rivera (Tech Professional) | No MCT, no relevant certs, no training delivery experience |

---

## Azure AI Foundry Deployment

The Contoso HR Agent connects to Azure AI Foundry for all LLM and embedding calls. The reference deployment uses:

| Resource | Value |
|----------|-------|
| **Resource name** | `scribe-foundry-resource` |
| **Resource group** | `scribe-rg` |
| **Region** | East US 2 |
| **Chat deployment** | `gpt-5.4-1` (model `gpt-5.4`, version `2026-03-05`) |
| **Embedding deployment** | `text-embedding-ada-002-1` (model `text-embedding-ada-002`) |
| **API version** | `2024-05-01-preview` |

### Required Environment Variables

```bash
AZURE_AI_FOUNDRY_ENDPOINT=https://scribe-foundry-resource.cognitiveservices.azure.com/
AZURE_AI_FOUNDRY_KEY=your-api-key
AZURE_AI_FOUNDRY_CHAT_MODEL=gpt-5.4-1
AZURE_AI_FOUNDRY_EMBEDDING_MODEL=text-embedding-ada-002-1
```

### Finding Your Credentials

```bash
# Via Azure CLI
az cognitiveservices account show \
  --name <your-foundry-account> -g <your-resource-group> \
  --query properties.endpoint -o tsv

az cognitiveservices account keys list \
  --name <your-foundry-account> -g <your-resource-group> \
  --query key1 -o tsv
```

### Teardown

```bash
# Delete everything when done.
# IMPORTANT: substitute your own RG name. Never run this against a shared resource group.
az group delete --name <your-resource-group> --yes --no-wait
```

---

## Legacy Reference

The `oreilly-agent-mvp/` directory contains an earlier iteration of the course demo -- a GitHub issue triage pipeline with PM/Dev/QA agents. It is retained as reference material only and is **not** the active project. All learner-facing work uses `contoso-hr-agent/`.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `uv sync` fails | Verify Python 3.11+ is installed (`python --version`). Install uv: `pip install uv` or see [uv docs](https://docs.astral.sh/uv/). |
| Azure key not working | Check `.env` for typos. Endpoint must end with `/`. Verify deployment names match. |
| Port already in use | Start scripts auto-kill ports 8090/8091. If stuck, manually kill the process. |
| ChromaDB empty | Run `uv run hr-seed --reset` to clear and re-seed from `sample_knowledge/`. |
| No web search results | Set `BRAVE_API_KEY` in `.env`. The agent gracefully skips web search if unset. |

See [contoso-hr-agent/README.md](contoso-hr-agent/README.md) for the full troubleshooting guide.

---

## Resources

- [Contoso HR Agent docs](contoso-hr-agent/README.md) -- full project README with detailed architecture
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [CrewAI Documentation](https://docs.crewai.com/)
- [Azure AI Foundry Documentation](https://learn.microsoft.com/en-us/azure/ai-studio/)
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/)

---

## License and Usage

MIT License -- feel free to use this code in your own projects.

**Course Materials:** (c) 2026 Tim Warner / O'Reilly Media
**Code:** Open source, use freely

---

## About the Instructor

**Tim Warner** teaches cloud, DevOps, and AI at O'Reilly, Pluralsight, and LinkedIn Learning.

- [TechTrainerTim.com](https://TechTrainerTim.com)
- [LinkedIn](https://linkedin.com/in/timothywarner)
- [GitHub](https://github.com/timothywarner-org)
