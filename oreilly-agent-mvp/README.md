# O'Reilly AI Agents MVP

**Issue Triage + Implementation Draft Pipeline**

A minimal but real demonstration of production-minded AI agents using:
- **LangGraph** for stateful orchestration
- **CrewAI** for multi-agent role definitions (PM, Dev, QA)
- **MCP (Model Context Protocol)** for GitHub connectivity

> **Note:** This demo teaches orchestration and agent roles. It is not competing with GitHub Copilot's coding agent or similar tools. The focus is on understanding the patterns and architecture.

---

## Quickstart (Windows PowerShell)

### 1. Clone and Setup

```powershell
# Clone the repository
git clone <your-repo-url>
cd oreilly-agent-mvp

# Run setup script (creates venv, installs dependencies)
.\scripts\setup.ps1
```

### 2. Configure Environment

```powershell
# Copy the example environment file
Copy-Item .env.example .env

# Edit .env and add your API key (choose ONE provider)
notepad .env
```

**Required:** Set at least one of these:
- `ANTHROPIC_API_KEY` - Get from [console.anthropic.com](https://console.anthropic.com/)
- `OPENAI_API_KEY` - Get from [platform.openai.com](https://platform.openai.com/api-keys)
- `AZURE_OPENAI_*` - Get from your Azure Portal

### 3. Run the Pipeline

```powershell
# Run once with a mock issue
.\scriptsun_once.ps1

# Or run with a specific mock file
.\scriptsun_once.ps1 mock_issues/issue_002.json

# Check results in outgoing/
Get-ChildItem outgoing/
```

### 4. Start the Folder Watcher (Optional)

```powershell
# Start watching incoming/ for new issues
.\scriptsun_watcher.ps1

# In another terminal, drop an issue file
Copy-Item mock_issues\issue_003.json incoming
# Watch the pipeline process it automatically!
```

---

## Project Structure

```
oreilly-agent-mvp/
├── README.md                 # This file
├── pyproject.toml           # Python dependencies
├── .env.example             # Environment template
├── .gitignore
├── .mcp.json                # Claude Code MCP config template
├── .vscode/
│   ├── mcp.json            # VS Code MCP config for GitHub
│   └── settings.json       # Recommended VS Code settings
├── src/agent_mvp/
│   ├── config.py           # Configuration management
│   ├── models.py           # Pydantic models (Issue, Results)
│   ├── logging_setup.py    # Structured logging
│   ├── issue_sources/      # Issue loading (file, mock)
│   ├── pipeline/
│   │   ├── graph.py        # LangGraph orchestration
│   │   ├── crew.py         # CrewAI agent definitions
│   │   ├── prompts.py      # Agent prompt templates
│   │   └── run_once.py     # CLI for single runs
│   ├── watcher/
│   │   ├── folder_watcher.py   # Polls incoming/
│   │   └── process_file.py     # File processing logic
│   └── util/
│       ├── fs.py           # File system utilities
│       └── json_schema.py  # Issue validation
├── mock_issues/            # Pre-made test issues
├── incoming/               # Drop issues here (watcher)
├── processed/              # Processed issues moved here
├── outgoing/               # Pipeline results
├── scripts/
│   ├── setup.ps1          # Setup script
│   ├── run_once.ps1       # Run pipeline once
│   └── run_watcher.ps1    # Start folder watcher
└── tests/                  # Pytest tests
```

---

## How It Works

### Pipeline Flow

```
Issue JSON -> [Load] -> [PM Agent] -> [Dev Agent] -> [QA Agent] -> Result JSON
```

### Agent Roles

| Agent | Role | Output |
|-------|------|--------|
| **PM** | Analyzes issue, creates acceptance criteria and plan | Summary, criteria, steps, assumptions |
| **Dev** | Implements the plan with code and tests | File drafts, implementation notes |
| **QA** | Reviews implementation against criteria | Pass/Fail/Needs-Human verdict, findings |

### Two Ways to Run

1. **CLI Mode**: Run once with `--source mock` or `--source file`
2. **Watcher Mode**: Auto-process files dropped in `incoming/`

---

## Configuration

### LLM Provider Selection

Set `LLM_PROVIDER` in `.env`:

| Provider | Value | Required Keys |
|----------|-------|---------------|
| Anthropic | `anthropic` | `ANTHROPIC_API_KEY` |
| OpenAI | `openai` | `OPENAI_API_KEY` |
| Azure OpenAI | `azure` | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT` |

### Key Settings

```bash
LLM_TEMPERATURE=0.2        # Low for deterministic outputs
WATCH_POLL_SECONDS=3       # Folder watcher interval
LOG_LEVEL=INFO             # DEBUG for verbose output
```

---

## Issue JSON Schema

Issues must follow this format:

```json
{
  "issue_id": "owner/repo#123",
  "repo": "owner/repo",
  "issue_number": 123,
  "title": "Issue title",
  "body": "Description text",
  "labels": ["bug", "priority:high"],
  "url": "https://github.com/owner/repo/issues/123",
  "source": "mock"
}
```

**Required fields:** `issue_id`, `repo`, `issue_number`, `title`, `url`

**Source values:** `mock`, `github-mcp`, `manual`

---

## MCP Integration (GitHub)

This project demonstrates MCP connectivity without runtime coupling:

### For VS Code / Copilot Chat

1. Sign in to GitHub in VS Code
2. The `.vscode/mcp.json` configures the GitHub MCP server
3. Use AI chat to fetch issues
4. Save the result as JSON in `incoming/`

### For Claude Code

1. Set `GITHUB_TOKEN` in your environment
2. See `.mcp.json` for configuration template
3. Use Claude Code to interact with GitHub issues

### Instructor Flow (Class Demo)

1. Open VS Code with Copilot Chat
2. Ask: "Fetch the details of issue #123 from microsoft/vscode"
3. Copy the structured response
4. Create a JSON file in `incoming/` with the issue data
5. The watcher automatically processes it!

---

## Troubleshooting

### "ANTHROPIC_API_KEY not set"
- Copy `.env.example` to `.env`
- Add your API key
- Make sure `LLM_PROVIDER` matches your key

### "Model not found" errors
- Check `LLM_MODEL` matches your provider
- Anthropic: `claude-sonnet-4-20250514`, `claude-3-5-haiku-20241022`
- OpenAI: `gpt-4o`, `gpt-4o-mini`

### Watcher processes same file twice
- This should not happen - files are marked as seen immediately
- Check file permissions on `processed/` folder
- Try restarting the watcher

### Import errors
- Make sure you activated the venv: `.\.venv\Scripts\Activate.ps1`
- Re-run: `pip install -e ".[dev]"`

---

## Running Tests

```powershell
# Activate venv
.\.venv\Scripts\Activate.ps1

# Run all tests
pytest

# Run with coverage
pytest --cov=agent_mvp
```

---

## Architecture Notes

### Why LangGraph?
- Stateful orchestration with clear node transitions
- Easy to visualize and debug
- Built-in support for checkpointing (optional)

### Why CrewAI?
- Clean agent role definitions
- Familiar PM/Dev/QA metaphor
- Can be extended with tools (not in MVP)

---

## Further Reading

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [CrewAI Documentation](https://docs.crewai.com/)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [VS Code MCP Servers](https://code.visualstudio.com/docs/copilot/chat/mcp-servers)

---

## License

MIT License - See LICENSE file for details.

---

*Built for O'Reilly training on AI agents and orchestration patterns.*
