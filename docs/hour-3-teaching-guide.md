# Hour 3 Teaching Guide: Agent Roles & Prompt Engineering

**Goal:** Students understand how prompts control agent behavior and modify them to see real changes.

**Time:** 60 minutes

---

## 🎬 Opening (3 minutes)

**What We're Doing This Hour:**
1. Deep dive into what each agent actually does
2. Dissect the prompts that make them work
3. YOU will modify a prompt and see what changes
4. Fetch a real GitHub issue (if time permits)

**Key Message:** "Prompts are code. Small tweaks = big behavior changes. You're going to break stuff (safely)."

---

## 🎭 Deep Dive: The Three Agents (12 minutes)

### The PM Agent: Requirements Translator

**Show:** `src/agent_mvp/pipeline/prompts.py` (Lines 1-30)

```bash
code src/agent_mvp/pipeline/prompts.py
```

**Read aloud (Lines 8-18):**
```python
PM_SYSTEM_PROMPT = """You are a Product Manager analyzing a GitHub issue.

Your job is to:
1. Summarize the request clearly
2. Define measurable acceptance criteria
3. Create an implementation plan with specific steps
4. Document any assumptions you're making

Be practical and focused on delivering value.
Output MUST be valid JSON matching this schema: {...}
"""
```

**Ask:** "What's the PM's ONE job?"
- **Answer:** Turn vague requests into clear requirements

**Point out:**
- "Summarize" → Forces PM to distill the issue
- "Measurable acceptance criteria" → Makes it testable
- "Implementation plan" → Gives Dev a roadmap
- "Output MUST be valid JSON" → Makes it machine-readable

**Show an example PM output:**
```bash
cat outgoing/result_*.json | jq .pm_output
```

**Say:** "Notice how structured this is. That's the prompt at work."

---

### The Dev Agent: Code Generator

**Show:** `src/agent_mvp/pipeline/prompts.py` (Lines 70-95)

**Read aloud (Lines 78-88):**
```python
DEV_SYSTEM_PROMPT = """You are a Senior Developer implementing a feature.

Your job is to:
1. Write clean, working code based on the PM's plan
2. Create tests that verify the acceptance criteria
3. Document any implementation decisions

Focus on practical, maintainable solutions.
Don't over-engineer, but don't cut corners.
Output MUST be valid JSON with code files and notes.
"""
```

**Ask:** "What's different between PM and Dev prompts?"
- PM is about PLANNING
- Dev is about BUILDING

**Point out:**
- "Clean, working code" → Quality matters
- "Create tests" → Not optional
- "Don't over-engineer" → Keeps it practical
- "Don't cut corners" → But don't skip steps either

**Show an example Dev output:**
```bash
cat outgoing/result_*.json | jq .dev_output.files
```

**Say:** "Dev created actual code files. That's the prompt telling it to return structured data."

---

### The QA Agent: Code Reviewer

**Show:** `src/agent_mvp/pipeline/prompts.py` (Lines 130-155)

**Read aloud (Lines 138-148):**
```python
QA_SYSTEM_PROMPT = """You are a QA Engineer reviewing an implementation.

Your job is to:
1. Check if the code meets acceptance criteria
2. Look for bugs, edge cases, and security issues
3. Verify tests are comprehensive
4. Provide a clear verdict: APPROVED, NEEDS_WORK, or REJECTED

Be thorough but fair. Focus on real issues, not nitpicking.
Output MUST be valid JSON with verdict and findings.
"""
```

**Ask:** "Why three verdict options instead of just pass/fail?"
- APPROVED → Ship it
- NEEDS_WORK → Close but needs fixes
- REJECTED → Start over

**Point out:**
- "Real issues, not nitpicking" → Keeps feedback useful
- "Check if code meets acceptance criteria" → Ties back to PM
- "Comprehensive tests" → Quality gate

**Key Point:** "These three prompts create a mini-SDLC. PM designs, Dev builds, QA verifies."

---

## 🔬 Hands-On: Prompt Dissection (15 minutes)

### Activity: Annotate the PM Prompt

**Show:** `src/agent_mvp/pipeline/prompts.py` (Lines 1-50)

**Say:** "Let's break down EVERY piece of the PM prompt together."

**Go line-by-line:**

```python
PM_SYSTEM_PROMPT = """You are a Product Manager analyzing a GitHub issue.
```
**Ask:** "Why 'Product Manager' not just 'AI'?"
- **Answer:** Role gives context. PM thinks differently than a developer.

```python
Your job is to:
1. Summarize the request clearly
```
**Ask:** "Why summarize if we already have the issue?"
- **Answer:** Forces understanding. Paraphrasing shows comprehension.

```python
2. Define measurable acceptance criteria
```
**Ask:** "What makes criteria 'measurable'?"
- **Answer:** You can write a test for it. "Works" is not measurable. "Returns 200 OK" is.

```python
3. Create an implementation plan with specific steps
```
**Ask:** "Why 'specific steps' not just 'a plan'?"
- **Answer:** Vague = useless. "Add dark mode" vs "1. Create theme context, 2. Add toggle component..."

```python
Be practical and focused on delivering value.
```
**Say:** "This is a 'don't overthink it' instruction. Keeps PM from goldplating."

```python
Output MUST be valid JSON matching this schema: {...}
```
**Say:** "This is CRITICAL. Without this, we'd get natural language and have to parse it."

**Key Takeaway:** "Every word has a purpose. If you remove 'measurable', you'll get vague criteria."

---

## ✏️ Hands-On: Modify a Prompt (20 minutes)

### Setup (5 min)

**Say:** "Everyone pick ONE agent to modify. We're going to change its personality."

**Options:**
- **Easy:** Make QA stricter or more lenient
- **Medium:** Change PM to focus on security
- **Hard:** Make Dev prioritize performance over readability

**Have everyone:**
1. Copy `prompts.py` to `prompts_original.py` (backup)
2. Open `prompts.py` in their editor

```bash
cp src/agent_mvp/pipeline/prompts.py src/agent_mvp/pipeline/prompts_original.py
code src/agent_mvp/pipeline/prompts.py
```

---

### Example 1: Make QA Stricter

**Say:** "Let's make QA more demanding. Find the QA system prompt."

**Original (Lines 138-150):**
```python
QA_SYSTEM_PROMPT = """You are a QA Engineer reviewing an implementation.

Your job is to:
1. Check if the code meets acceptance criteria
2. Look for bugs, edge cases, and security issues
3. Verify tests are comprehensive
4. Provide a clear verdict: APPROVED, NEEDS_WORK, or REJECTED

Be thorough but fair. Focus on real issues, not nitpicking.
"""
```

**Modified:**
```python
QA_SYSTEM_PROMPT = """You are a SENIOR QA Engineer with 15 years experience reviewing implementations.

Your job is to:
1. Rigorously verify code meets ALL acceptance criteria
2. Look for bugs, edge cases, security issues, AND performance problems
3. Verify tests cover edge cases, not just happy paths
4. Check for accessibility, localization, and error handling
5. Provide a clear verdict: APPROVED, NEEDS_WORK, or REJECTED

Be extremely thorough. Quality over speed. If you have ANY doubts, choose NEEDS_WORK.
"""
```

**Say:** "Notice what changed:"
- Added "SENIOR" and "15 years" → Sets higher bar
- Added "performance problems" → New concern
- Added "edge cases, not just happy paths" → Raises test bar
- Added "accessibility, localization" → More concerns
- "If you have ANY doubts" → Makes it harder to approve

---

### Example 2: Make PM Focus on Security

**Original (Lines 8-20):**
```python
PM_SYSTEM_PROMPT = """You are a Product Manager analyzing a GitHub issue.

Your job is to:
1. Summarize the request clearly
2. Define measurable acceptance criteria
3. Create an implementation plan with specific steps
4. Document any assumptions you're making

Be practical and focused on delivering value.
"""
```

**Modified:**
```python
PM_SYSTEM_PROMPT = """You are a Security-Focused Product Manager analyzing a GitHub issue.

Your job is to:
1. Summarize the request clearly
2. Define measurable acceptance criteria (including security requirements)
3. Create an implementation plan that addresses potential security risks
4. Document any assumptions, especially around authentication and data handling
5. Identify what data is being processed and how it should be protected

Always consider: What could go wrong? Who could abuse this? What data is at risk?
Be practical but security-first.
"""
```

**Say:** "Now PM will think about security in EVERY issue, even simple ones."

---

### Run and Compare (10 min)

**Have everyone:**
1. Save their modified prompt
2. Run the pipeline with the SAME mock issue they used in Hour 2

```bash
agent-menu
# Select: 2 (Mock issue)
# Choose: 1 (same as before)
# Process: y
```

3. Compare the new output to the old one

```bash
# Old output
cat outgoing/result_YYYY-MM-DD_HH-MM-SS.json | jq .qa_output.verdict

# New output (will be newer timestamp)
ls -lt outgoing/
cat outgoing/result_YYYY-MM-DD_HH-MM-SS.json | jq .qa_output.verdict
```

**Ask:** "What changed? Is the verdict different?"

**Likely outcomes:**
- Stricter QA → More "NEEDS_WORK" verdicts
- Security PM → More security-related acceptance criteria
- Performance Dev → Code includes optimization comments

**Key Point:** "Same input, different prompt, different output. Prompts ARE the behavior."

---

## 🔗 GitHub Integration (10 minutes)

### Setup GitHub Token

**Say:** "Let's fetch a REAL issue from our repo and see how agents handle messier data."

**Check who has GitHub tokens:**
```bash
cat .env | grep GITHUB_TOKEN
```

**If some don't have tokens:**
- Pair them up with someone who does
- OR skip to demo mode (you do it on screen share)

### Fetch and Process

**Everyone with tokens runs:**
```bash
agent-menu
# Select: 1 (GitHub)
# Enter issue: 1 (or any open issue in timothywarner-org/agents2)
# Process: y
```

**While it runs, explain:**
- "Notice it's fetching from GitHub API using your token"
- "The issue gets transformed to our schema"
- "Then it flows through the same pipeline"

### Compare Real vs. Mock

**Show both outputs side-by-side:**
```bash
# Mock issue (clean, structured)
cat outgoing/result_*mock*.json | jq .issue.description

# GitHub issue (messy, might have markdown, links, @mentions)
cat outgoing/result_*github*.json | jq .issue.description
```

**Ask:** "How did the agents handle the messy real data?"

**Key observation:** "Good prompts are robust. They handle both clean and messy inputs."

---

## 🤔 Discussion: Prompt Engineering Lessons (5 minutes)

### Question 1: "What happens if we remove the JSON schema requirement?"

**Good answers:**
- Agents return natural language
- We'd have to parse it manually
- More errors, less reliable

**Say:** "Structured output is not optional in production systems."

---

### Question 2: "Could we make prompts TOO detailed?"

**Good answers:**
- Yes! Too prescriptive = inflexible
- LLM might focus on rules instead of solving the problem
- Longer prompts = higher cost

**Say:** "There's a sweet spot. Enough guidance, not a straightjacket."

---

### Question 3: "Should we test prompts?"

**Answer:** "YES! Like code, prompts need tests."

**Example test cases:**
- Does PM always return valid JSON?
- Does QA catch obvious bugs?
- Does Dev include tests in output?

**Say:** "In production, you'd have a test suite that runs prompts against known inputs."

---

## 🎯 Wrap-Up (5 minutes)

**What We Accomplished:**
- ✅ Understood each agent's role deeply
- ✅ Dissected prompts line-by-line
- ✅ Modified prompts and saw behavior change
- ✅ Processed real GitHub issues

**What's Next (Hour 4):**
- How LangGraph orchestrates the flow
- How to ADD agents or change the flow
- Extension ideas YOU pick
- Production tips

**Challenge for Hour 4:**
"Think about what 4th agent you'd add. Design Lead? Security Analyst? Documentation Writer?"

---

## 📝 Teaching Tips

### If Prompt Changes Don't Show Results

**Likely causes:**
1. They edited the wrong file (check: `grep "SENIOR" src/agent_mvp/pipeline/prompts.py`)
2. They didn't save the file
3. The change was too subtle

**Fix:** Show a DRAMATIC change on your screen (e.g., "You are a HARSH critic who NEVER approves anything")

---

### If GitHub API Fails

**Common issues:**
1. Token expired: Get a new one from github.com/settings/tokens
2. Rate limiting: Wait 60 seconds, try again
3. Issue doesn't exist: Use issue #1 (should always exist)

**Backup plan:** Use your token and screen share the fetch

---

### If Students Want to Go Deeper

**Advanced challenges:**
1. "Add a new field to PMOutput model and update prompt to populate it"
2. "Make agents use different LLM models (PM = Haiku, Dev = Sonnet)"
3. "Add a token counter to track cost per agent"

---

### Time Management

- If prompt modification runs long: Skip GitHub integration, use demo
- If running short: Add a "swap agents" exercise (PM prompt in Dev role)
- If GitHub API is slow: Pre-fetch an issue before class starts

---

## 📚 Quick Reference: Key Files & Lines

| File | Lines | What to Show |
|------|-------|--------------|
| `prompts.py` | 8-20 | PM system prompt |
| `prompts.py` | 78-90 | Dev system prompt |
| `prompts.py` | 138-150 | QA system prompt |
| `prompts.py` | 35-55 | format_pm_prompt (how context is added) |
| `integrations/github_issue_fetcher.py` | 20-60 | GitHub API call |

---

## 🎨 Visual Aid: Prompt Structure

Draw this on whiteboard/screen:

```
┌─────────────────────────────────────┐
│ System Prompt                       │
│ (Who you are, what your job is)    │
├─────────────────────────────────────┤
│ User Prompt                         │
│ (The specific task/issue)           │
├─────────────────────────────────────┤
│ Output Schema                       │
│ (The structure you must return)    │
└─────────────────────────────────────┘
```

**Say:** "Every agent gets this sandwich: Role, Task, Format."

---

**You got this! The prompt is the product. 🎯**
