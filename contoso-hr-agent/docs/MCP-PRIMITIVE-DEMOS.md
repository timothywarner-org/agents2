# MCP Primitive Demos — Client Matrix and Stage Reference

> Pull this up on a second monitor during workshops. When someone asks
> "why doesn't sampling work in my VS Code?", the answer is on this page.

## The five MCP primitives, and where each one actually works

| Primitive | What it does | MCP Inspector | VS Code / Copilot Chat | Claude Desktop |
|---|---|:---:|:---:|:---:|
| **Tools** | Server-side functions the LLM can call | works | works | works |
| **Resources** | Read-only data the LLM can pull | works | works | works |
| **Prompts** | Reusable message templates (slash menu) | works | works | works |
| **Sampling** | Server asks the *client's* LLM to generate text | works (mock) | broken as of early 2026 | works |
| **Elicitation** | Server pauses, asks the user a structured-form question | works | inconsistent | works |

**The two demo-fragile primitives are sampling and elicitation.** That is a
client-landscape problem, not a server problem. This server is built to
demo cleanly in every client by either falling back gracefully or returning
a clear diagnostic when the client lacks support.

## What each primitive looks like to the watching human

### Tools (every client)
Tools appear in the slash menu (or equivalent) and execute when invoked.
Output streams back into the chat or the Inspector's "Tools" panel. Nothing
fancy.

### Resources (every client)
Resources show up in a side panel listing — `schema://candidate`,
`stats://evaluations`, `candidate://{id}`, `policy://{topic}`. Click to read.

### Prompts (every client)
In VS Code/Copilot Chat, type `/` and the prompts appear as slash commands
with their `title=` shown. Each prompt's argument form opens a modal with
labeled fields when `Annotated[..., Field(description=...)]` is used.

### Sampling — best demo: MCP Inspector

When `ctx.sample()` fires in **MCP Inspector**, a sampling panel lights up
showing the request the server sent. Inspector doesn't have a real LLM
attached, so it shows you a textbox where you (the demo presenter) can
type a mock LLM response. Click send, and the server resumes the tool with
your text. This is the **best teaching moment** for sampling because the
audience watches the protocol pause and resume on screen.

```
┌─ MCP Inspector: Sampling Request ──────────────────────────┐
│ System: You are a senior HR analyst at Contoso…           │
│ User:   Write a concise 3-5 sentence executive summary…   │
│ ─────────────────────────────────────────────────────────  │
│ Mock response: [                                       ]   │
│                [ Send to server ]                          │
└────────────────────────────────────────────────────────────┘
```

### Sampling — VS Code / Copilot Chat (the unhappy path)

As of early 2026, the Copilot Chat MCP client does not implement sampling.
Calling `ctx.sample()` raises an error. **This server handles that for you:**
the `generate-eval-summary` tool falls back to a direct Azure AI Foundry
call using the same prompt, and prefixes the response with a visible
header:

```
[via server-fallback — client did not support sampling
 (McpError); same prompt sent directly to gpt-5.4-1]

Alice Zhang is a Strong Match (overall 88/100)…
```

When demoing in VS Code, the audience sees the `[via server-fallback]`
header and you say: **"That header is your teaching moment. The server
*wanted* to ask Copilot's LLM to write this summary using the sampling
primitive — but Copilot Chat doesn't expose its model that way yet. So
the server fell back to calling Azure AI Foundry directly. Same prompt,
different driver. In MCP Inspector or Claude Desktop, this would say
`[via client-sampled]` instead."**

### Elicitation — best demo: MCP Inspector

When `ctx.elicit()` fires in **MCP Inspector**, a modal appears *inside
the Inspector tab* with the message text and form fields rendered from
the Pydantic schema you passed as `response_type`. Three buttons at the
bottom: Accept, Decline, Cancel.

```
┌─ MCP Inspector: Elicitation Request ───────────────────────┐
│ Ready to evaluate alice_zhang.txt?                         │
│ Preview: Alice Zhang, MCT, 8 years…                        │
│                                                            │
│ ☐ confirmed                                                │
│   Required. Check this box to confirm…                     │
│                                                            │
│ priority: [ normal ▾ ]                                     │
│   Pipeline-log priority hint…                              │
│                                                            │
│ requester_notes: [                       ]                 │
│   Optional. Free-text note attached to…                    │
│                                                            │
│            [ Decline ] [ Cancel ]      [ Accept ]          │
└────────────────────────────────────────────────────────────┘
```

The labels under each field come from `Field(description=...)` on the
Pydantic model. **This is exactly the win we got from doing the same on
prompts** — no bare snake_case field names.

### Elicitation — VS Code / Copilot Chat (inconsistent)

Elicitation support in VS Code's MCP client has been in flux across
Insiders builds in late 2025 / early 2026. Behavior you may see:
- A modal appears in the chat sidebar (working build)
- The form is auto-accepted with default values (partial support)
- The tool returns an error (no support yet)

**This server handles all three cases.** If `ctx.elicit()` raises, the
tool returns a diagnostic dict with `status: "elicitation_unsupported"`
and a clear `client_error` field. The pipeline does not run.

## Demo-day playbook

### The 5-minute "all five primitives" demo

1. **Start Inspector + VS Code side by side** with this server running.
2. **Resources:** In Inspector, click `stats://evaluations` — show the JSON
   with current candidate counts.
3. **Prompts:** In VS Code, type `/score-trainer-resume` — show the modal
   with the labeled `resume_text` and `role` fields.
4. **Tools:** In Inspector, call `list-candidates` — show the returned
   array.
5. **Sampling — the contrast:**
   - In **Inspector**, call `generate-eval-summary` with a real
     `candidate_id`. The sampling panel pops up. **Type your own mock
     summary**, click send. The tool returns it with the
     `[via client-sampled]` header. *Audience gasps.*
   - Switch to **VS Code**. Call the same tool. You see the
     `[via server-fallback]` header. **This is the teaching moment.**
6. **Elicitation — the showcase:**
   - In **Inspector**, call `demo-elicitation-showcase` — no args needed.
     The committee-preferences form appears. Fill it in, accept. Tool
     echoes back the captured preferences.
   - This tool is **deliberately fast and side-effect-free** — perfect
     for a workshop where waiting 30-120 seconds for the real
     `confirm-and-evaluate` would kill the energy.

### What's running in the terminal during all this

The server writes Rich-formatted breadcrumb panels to stderr every time
a sampling or elicitation primitive fires. Examples:

```
╭─ ELICITATION → sent ─────────────────────────────────────╮
│ Tool: confirm_and_evaluate                               │
│ Filename: alice_zhang.txt                                │
│ Preview: Alice Zhang, MCT, 8 years…                      │
│ Form fields: confirmed (bool), priority (low/normal/…    │
╰──────────────────────────────────────────────────────────╯

╭─ ELICITATION → user clicked 'accept' ────────────────────╮
│ Result: accept                                           │
│ Data: EvalConfirmationForm(confirmed=True, priority=…    │
╰──────────────────────────────────────────────────────────╯

╭─ SAMPLING → request sent ────────────────────────────────╮
│ Tool: generate_eval_summary                              │
│ Candidate: Alice Zhang (a1b2c3d4)                        │
│ Prompt length: 612 chars                                 │
│ Asking client to generate summary via ctx.sample()…      │
╰──────────────────────────────────────────────────────────╯

╭─ SAMPLING → client unsupported, using server fallback ──╮
│ Client returned: McpError: client does not support…     │
│ Falling back to direct Azure AI Foundry call (same      │
│ prompt)…                                                 │
╰──────────────────────────────────────────────────────────╯
```

**Demo move:** tab to the terminal mid-demo to show these. The audience
sees the protocol activity laid out in real time. The breadcrumbs are
written to **stderr only** so they're safe in stdio mode (where stdout
is owned by JSON-RPC).

## FAQ — questions audiences actually ask

### "Why don't sampling and elicitation just work everywhere?"
Both were added late in the MCP spec evolution, and client implementations
are catching up at different rates. Tools/Resources/Prompts shipped first
and are universally supported. Sampling and Elicitation are newer and the
client implementations vary. This will improve over the next 6-12 months.

### "Is the server-side fallback for sampling 'cheating'?"
No — it's the right engineering pattern when a protocol primitive isn't
universally supported. The fallback uses the *exact same prompt* as the
sampling path, so the demonstration of "what the LLM is being asked to
do" is identical. The only difference is *which LLM driver* executes it.

### "What's the security model for sampling? Can the server steal my LLM?"
Sampling is opt-in per request, and most clients gate it with a user
permission prompt (Inspector and Claude Desktop both do). The client
can refuse, modify, or audit the sampling request. The server never
gets direct API access to the client's LLM credentials — the client
relays the request and returns the response.

### "Why use elicitation instead of just a tool parameter?"
Elicitation is for **mid-tool-execution** prompts where the server needs
information it didn't have when the tool was called. Example: the
`confirm_and_evaluate` tool *could* have a `confirmed: bool` parameter,
but that would mean the LLM (not the user) decides to confirm. Elicitation
puts the human in the loop. It's also the right primitive for follow-up
questions like "you mentioned three roles — which one should I optimize
for?" mid-tool.

## Reference — the tools in this server

| Tool | Primitive demonstrated | Demo cost | Best client |
|---|---|---|---|
| `get-candidate` | Tools | instant | any |
| `list-candidates` | Tools | instant | any |
| `query-policy` | Tools (with async offload) | ~3s | any |
| `trigger-resume-evaluation` | Tools (long-running) | 30-120s | any |
| `confirm-and-evaluate` | **Elicitation + Tools** | form + 30-120s | Inspector, Claude Desktop |
| `demo-elicitation-showcase` | **Elicitation (cheap)** | form, ~5s | Inspector, Claude Desktop |
| `generate-eval-summary` | **Sampling (with fallback)** | ~3-5s | Inspector best; falls back gracefully elsewhere |

## When you find this doc stale

The MCP client landscape moves fast. Re-check the matrix at the top of
this doc when:
- A new VS Code Stable release ships
- Anthropic ships a new MCP client version
- A workshop attendee reports that something "just works now"

Last verified: 2026-05-13.
