<<<<<<< HEAD

# **O'Reilly Live Learning: Build Production-Ready AI Agents**
[TechTrainerTim.com](https://TechTrainerTim.com)

---

## Overview

This project demonstrates production-ready AI agent patterns for issue triage and implementation pipelines. It leverages:

- **LangGraph** for stateful, node-based orchestration
- **CrewAI** for multi-agent collaboration (PM, Dev, QA roles)
- **Event-driven** and CLI workflows for flexible automation

---

## Architecture

- **oreilly-agent-mvp/**
	- `src/agent_mvp/`
		- `pipeline/` — Orchestration logic (LangGraph, CrewAI agents, prompt templates)
		- `issue_sources/` — Load issues from files, GitHub MCP, or mock data
		- `util/` — File handling, schema validation, logging
		- `watcher/` — Folder watcher for event-driven execution
		- `models.py` — Pydantic models for all pipeline data contracts
		- `config.py` — Environment-driven configuration (supports Anthropic, OpenAI, Azure)
		- `logging_setup.py` — Rich, color-coded structured logging
	- `incoming/`, `outgoing/`, `processed/` — File-based workflow triggers and outputs

---

## Key Workflows

- **Run pipeline once:**
	`python -m agent_mvp.pipeline.run_once`
	or use the script: `agent-mvp`

- **Event-driven (watcher):**
	`python -m agent_mvp.watcher.folder_watcher`
	or use the script: `agent-watcher`

- **Process a new issue:**
	Place a JSON issue file in `incoming/` and run the watcher or pipeline script.

- **Add a new agent:**
	Extend `pipeline/` and update orchestration logic.

---

## Setup

1. **Clone the repo** and open in VS Code.
2. **Create a Python 3.11+ virtual environment** (recommended: `.venv`).
3. **Install dependencies:**
	 ```
	 pip install -e .[dev]
	 ```
4. **Configure environment:**
	 Copy `.env.example` to `.env` and set your LLM provider credentials (Anthropic, OpenAI, or Azure).
5. **(Optional) GitHub MCP integration:**
	 Configure `.mcp.json` and set your `GITHUB_TOKEN` for advanced workflows.

---

## Patterns & Conventions

- **No business logic in `__init__.py`** — only imports and metadata.
- **All agent roles (PM, Dev, QA) are modular and orchestrated via LangGraph.**
- **Structured, color-coded logging** for demos and debugging.
- **Secrets** are never committed; always use environment variables.

---

## Topics

ai, agents, langgraph, crewai, python, orchestration, multi-agent, pipeline, issue-triage

---

## License

MIT License

---
||||||| 97a100d
# agents2
O'Reilly Live Learning: Build Production-Ready AI Agents
=======
# agents2

Production-ready AI agent patterns for issue triage and implementation pipelines, featuring LangGraph orchestration and CrewAI multi-agent collaboration.

- **Live Learning Project**: O'Reilly Live Learning
- **Tech stack**: Python, LangGraph, CrewAI, event-driven pipeline
- **Key features**: Issue triage, multi-agent collaboration (PM, Dev, QA), event-driven processing, modular pipeline
- **Docs & details**: [TechTrainerTim.com](https://TechTrainerTim.com)

---

## Topics
- ai
- agents
- langgraph
- crewai
- python
- orchestration
- multi-agent
- pipeline
- issue-triage

---
MIT License
>>>>>>> 562761653e0260a38827d83f1739ff13a7aaacf4
