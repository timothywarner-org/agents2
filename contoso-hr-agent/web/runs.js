// Contoso HR Agent — Pipeline Runs page
// Displays a list of evaluation runs on the left and a detailed
// pipeline trace on the right, showing the parallel fan-out architecture.

const API_BASE = '';
// allRuns holds normalized rows with kind='pipeline' or 'chat'. Selection uses
// composite key kind + ':' + id so chat run_ids can never collide with
// candidate_ids in the active-row check.
let allRuns = [];
let selectedKey = null;
let runFilter = 'all';   // 'all' | 'pipeline' | 'chat'

// ---------------------------------------------------------------------------
// Load + render run list
// ---------------------------------------------------------------------------

async function loadRuns() {
  try {
    // Two sources, fetched in parallel. If chat-runs endpoint isn't deployed
    // yet (older server), gracefully degrade to pipeline-only.
    const [pipeRes, chatRes] = await Promise.all([
      fetch(`${API_BASE}/api/candidates?limit=100`).then(r => r.ok ? r.json() : []),
      fetch(`${API_BASE}/api/chat-runs?limit=100`).then(r => r.ok ? r.json() : { runs: [] }).catch(() => ({ runs: [] })),
    ]);

    const pipelineRuns = (pipeRes || []).map(r => ({
      kind: 'pipeline',
      id: r.candidate_id,
      title: r.candidate_name || 'Unknown',
      subtitle: r.filename || '',
      decision: r.decision || 'unknown',
      score: r.overall_score || 0,
      duration_seconds: r.duration_seconds,
      timestamp_utc: r.timestamp_utc,
      timestamp_ms: parseTimestampMs(r.timestamp_utc),
      raw: r,
    }));

    const chatRuns = (chatRes.runs || []).map(r => ({
      kind: 'chat',
      id: r.run_id,
      title: truncate(r.user_message || '', 60),
      subtitle: `session ${(r.session_id || '').slice(0, 8)}`,
      decision: null,
      score: null,
      duration_seconds: r.latency_ms != null ? r.latency_ms / 1000 : null,
      timestamp_utc: r.created_at,
      timestamp_ms: parseTimestampMs(r.created_at),
      raw: r,
    }));

    allRuns = [...pipelineRuns, ...chatRuns].sort(
      (a, b) => (b.timestamp_ms || 0) - (a.timestamp_ms || 0)
    );

    const visible = filteredRuns();
    const countEl = document.getElementById('run-count');
    countEl.textContent = `${visible.length} run${visible.length !== 1 ? 's' : ''} — auto-refreshes every 10s`;

    renderRunList();

    if (!selectedKey && visible.length > 0) {
      selectRun(visible[0].kind, visible[0].id);
    }
  } catch { /* server unavailable */ }
}

function filteredRuns() {
  if (runFilter === 'all') return allRuns;
  return allRuns.filter(r => r.kind === runFilter);
}

function setRunFilter(kind, btn) {
  runFilter = kind;
  document.querySelectorAll('.run-filter-btn').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  const visible = filteredRuns();
  document.getElementById('run-count').textContent =
    `${visible.length} run${visible.length !== 1 ? 's' : ''} — auto-refreshes every 10s`;
  renderRunList();
}

function renderRunList() {
  const container = document.getElementById('run-list');
  const visible = filteredRuns();
  if (!visible.length) {
    container.innerHTML = `
      <div style="padding:24px;text-align:center;color:var(--contoso-gray-dark);font-size:13px">
        No runs yet${runFilter !== 'all' ? ` for filter "${runFilter}"` : ' — drop a resume or chat with Alex to start'}.
      </div>`;
    return;
  }

  container.innerHTML = visible.map(run => {
    const key = `${run.kind}:${run.id}`;
    const isActive = key === selectedKey;
    const ts = formatTimestamp(run.timestamp_utc);
    const dur = run.duration_seconds != null ? `${run.duration_seconds.toFixed(1)}s` : '—';
    const kindBadge = `<span class="run-kind-badge ${run.kind}">${run.kind}</span>`;

    if (run.kind === 'pipeline') {
      const cls = decisionClass(run.decision);
      const shortFile = (run.subtitle || '').length > 28 ? run.subtitle.slice(0, 28) + '…' : run.subtitle;
      return `
        <div class="run-item ${isActive ? 'active' : ''}" onclick="selectRun('pipeline', '${run.id}')">
          <div class="run-item-top">
            <div>
              <div class="run-item-name">${kindBadge}${escapeHtml(run.title)}</div>
              <div class="run-item-file" title="${escapeHtml(run.subtitle)}">${escapeHtml(shortFile)}</div>
            </div>
            <span class="badge badge-${cls}" style="flex-shrink:0">${escapeHtml(run.decision)}</span>
          </div>
          <div class="run-item-meta">
            <span class="run-item-score">${run.score}/100</span>
            <span class="run-item-time">${ts} · ${dur}</span>
          </div>
        </div>`;
    }

    // Chat run rendering
    return `
      <div class="run-item chat-run ${isActive ? 'active' : ''}" onclick="selectRun('chat', '${run.id}')">
        <div class="run-item-top">
          <div>
            <div class="run-item-name">${kindBadge}${escapeHtml(run.title)}</div>
            <div class="run-item-file">${escapeHtml(run.subtitle)}</div>
          </div>
        </div>
        <div class="run-item-meta">
          <span class="run-item-time">${ts} · ${dur}</span>
        </div>
      </div>`;
  }).join('');
}

function parseTimestampMs(ts) {
  if (!ts) return 0;
  // SQLite default CURRENT_TIMESTAMP is 'YYYY-MM-DD HH:MM:SS' (UTC, no zone).
  // Date() parses ISO with 'T' fine but the space form is locale-dependent
  // in some browsers, so normalize.
  const normalized = ts.includes('T') ? ts : ts.replace(' ', 'T') + 'Z';
  const t = Date.parse(normalized);
  return isNaN(t) ? 0 : t;
}

function truncate(s, n) {
  if (!s) return '';
  return s.length > n ? s.slice(0, n) + '…' : s;
}

// ---------------------------------------------------------------------------
// Select a run and load its full trace
// ---------------------------------------------------------------------------

async function selectRun(kind, id) {
  selectedKey = `${kind}:${id}`;
  renderRunList(); // update active state

  const panel = document.getElementById('trace-panel');
  panel.innerHTML = `
    <div class="trace-empty">
      <div class="spinner"></div>
      <span style="font-size:13px;color:var(--contoso-gray-dark)">Loading trace…</span>
    </div>`;

  try {
    if (kind === 'pipeline') {
      const res = await fetch(`${API_BASE}/api/candidates/${id}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      renderTrace(await res.json());
    } else {
      const res = await fetch(`${API_BASE}/api/chat-runs/${id}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      renderChatTrace(await res.json());
    }
  } catch (err) {
    panel.innerHTML = `<div class="trace-empty"><div class="icon">⚠️</div><span>Failed to load trace</span></div>`;
  }
}

// Render the trace view for a single chat turn. Smaller and flatter than the
// 5-node pipeline trace — a chat run has at most 1-2 tool calls and one
// LLM completion, so we show: user message → tools invoked + sources → reply.
function renderChatTrace(r) {
  const panel = document.getElementById('trace-panel');
  const prov = r.provenance || {};
  const sources = prov.sources || [];
  const grounding = prov.grounding || {};
  const tools = (grounding.tools_invoked || []).join(', ') || '(no tools used)';
  const topSim = (grounding.top_similarity != null) ? grounding.top_similarity.toFixed(2) : '—';
  const latency = r.latency_ms != null ? `${(r.latency_ms / 1000).toFixed(1)}s` : '—';
  const ts = formatTimestamp(r.created_at);

  const sourcesHtml = sources.length === 0
    ? '<div style="font-size:12px;color:var(--contoso-gray-dark);padding:8px 0">No sources retrieved — Alex answered without invoking a knowledge tool.</div>'
    : sources.map(s => {
        const typeBadge = s.type === 'web' ? 'web' : 'policy';
        const score = (s.score != null) ? ` · sim ${s.score.toFixed(2)}` : '';
        return `
          <div style="background:white;border:1px solid var(--border);border-left:3px solid var(--contoso-blue);border-radius:4px;padding:8px 10px;margin-bottom:6px">
            <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.4px;color:var(--contoso-blue);font-weight:600;margin-bottom:4px">
              ${typeBadge} · ${escapeHtml(s.name)}${score}
            </div>
            <div style="font-size:12px;line-height:1.5;white-space:pre-wrap;overflow-wrap:anywhere">${escapeHtml(s.full_text || s.preview || '')}</div>
          </div>`;
      }).join('');

  panel.innerHTML = `
    <div class="trace-header">
      <div>
        <div class="trace-title">Chat turn</div>
        <div class="trace-subtitle">session ${escapeHtml((r.session_id || '').slice(0, 12))} · run ${escapeHtml((r.run_id || '').slice(0, 8))}</div>
      </div>
      <div class="trace-meta">
        <div class="trace-meta-item">
          <div class="value">${latency}</div>
          <div class="label">Latency</div>
        </div>
        <div class="trace-meta-item">
          <div class="value">${sources.length}</div>
          <div class="label">Sources</div>
        </div>
        <div class="trace-meta-item">
          <div class="value">${topSim}</div>
          <div class="label">Top sim</div>
        </div>
      </div>
    </div>

    <div class="pipeline">
      ${nodeHtml('intake', '💬', 'User message', ts, `
        <div style="font-size:13px;line-height:1.5;white-space:pre-wrap;overflow-wrap:anywhere">${escapeHtml(r.user_message || '')}</div>
      `)}
      ${connector()}
      ${nodeHtml('policy', '🔎', 'Tools + retrieval', tools, sourcesHtml)}
      ${connector()}
      ${nodeHtml('decision', '🤖', 'Assistant reply', 'ChatConcierge "Alex"', `
        <div style="font-size:13px;line-height:1.6;white-space:pre-wrap;overflow-wrap:anywhere">${escapeHtml(r.assistant_reply || '')}</div>
      `)}
    </div>

    <div style="margin-top:16px;padding:8px 10px;background:#FFF8E1;border-left:3px solid #F0AD4E;border-radius:3px;font-size:11px;color:var(--contoso-gray-dark);line-height:1.4">
      Grounding signals reflect retrieval quality, not answer correctness.
      LLM-generated confidence scores are deliberately not surfaced — see the Responsible AI page for context.
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Render pipeline trace
// ---------------------------------------------------------------------------

function renderTrace(r) {
  const panel = document.getElementById('trace-panel');
  const eval_ = r.candidate_eval;
  const dec   = r.hr_decision;
  const cls   = decisionClass(dec.decision);
  const dur   = r.duration_seconds ? `${r.duration_seconds.toFixed(1)}s` : '—';

  panel.innerHTML = `
    <!-- Trace header -->
    <div class="trace-header">
      <div>
        <div class="trace-title">${escapeHtml(r.candidate_name)}</div>
        <div class="trace-subtitle">${escapeHtml(r.filename)} &nbsp;·&nbsp; run ${escapeHtml(r.run_id.slice(0, 8))}</div>
      </div>
      <div class="trace-meta">
        <div class="trace-meta-item">
          <div class="value">${dur}</div>
          <div class="label">Duration</div>
        </div>
        <div class="trace-meta-item">
          <div class="value">${dec.overall_score}/100</div>
          <div class="label">Score</div>
        </div>
        <div class="trace-meta-item">
          <span class="decision-pill pill-${cls}">${escapeHtml(dec.decision)}</span>
        </div>
      </div>
    </div>

    <!-- Pipeline diagram -->
    <div class="pipeline">

      <!-- Node 1: Intake -->
      ${nodeHtml('intake', '📥', 'Intake', 'Node 1', `
        ${dataRow('Candidate', escapeHtml(r.candidate_name))}
        ${dataRow('File', escapeHtml(r.filename))}
        ${dataRow('Candidate ID', escapeHtml(r.candidate_id))}
        ${dataRow('Timestamp', escapeHtml(formatTimestamp(r.timestamp_utc)))}
      `)}

      ${connector()}

      <!-- Nodes 2+3: Parallel fan-out -->
      <div class="parallel-section">
        <div class="parallel-label">⚡ parallel fan-out — these two agents run concurrently</div>
        <div class="parallel-nodes">

          <!-- Policy Expert -->
          ${nodeHtml('policy', '📋', 'Policy Expert', 'Node 2 · ChromaDB', `
            ${dataRow('Policy summary', '')}
            <div style="font-size:12px;line-height:1.5;color:#333;margin-top:4px">
              ${escapeHtml(r.policy_context_summary || 'Standard Contoso MCT trainer policy applies.')}
            </div>
          `)}

          <!-- Resume Analyst -->
          ${nodeHtml('analyst', '🔍', 'Resume Analyst', 'Node 3 · Brave Search', `
            ${dataRow('Skills match', `<span class="score-pill">${eval_.skills_match_score}/100</span>`)}
            ${dataRow('Experience', `<span class="score-pill">${eval_.experience_score}/100</span>`)}
            ${eval_.recommended_role ? dataRow('Best-fit role', escapeHtml(eval_.recommended_role)) : ''}
            ${eval_.strengths.length ? `
              <div class="data-key" style="margin-top:6px">Strengths</div>
              <ul class="bullet-list">${eval_.strengths.map(s => `<li>${escapeHtml(s)}</li>`).join('')}</ul>` : ''}
            ${eval_.red_flags.length ? `
              <div class="data-key" style="margin-top:6px">Red flags</div>
              <ul class="bullet-list">${eval_.red_flags.map(f => `<li class="red">${escapeHtml(f)}</li>`).join('')}</ul>` : ''}
          `)}

        </div>
      </div>

      ${connector()}

      <!-- Node 4: Decision Maker -->
      ${nodeHtml('decision', '⚖️', 'Decision Maker', 'Node 4 · pure reasoning', `
        ${dataRow('Disposition', `<span class="decision-pill pill-${cls}">${escapeHtml(dec.decision)}</span>`)}
        ${dataRow('Overall score', `<span class="score-pill">${dec.overall_score}/100</span>`)}
        <div class="reasoning-block">${escapeHtml(dec.reasoning)}</div>
        ${dec.next_steps.length ? `
          <div class="data-key" style="margin-top:8px">Next steps</div>
          <ul class="bullet-list">${dec.next_steps.map(s => `<li>${escapeHtml(s)}</li>`).join('')}</ul>` : ''}
      `)}

      ${connector()}

      <!-- Node 5: Notify -->
      ${nodeHtml('notify', '✅', 'Notify', 'Node 5 · no LLM', `
        ${dataRow('Duration', dur)}
        ${dataRow('Saved to', 'SQLite hr.db + data/outgoing/')}
        ${dataRow('Run ID', escapeHtml(r.run_id.slice(0, 16) + '…'))}
      `)}

    </div>
  `;
}

// ---------------------------------------------------------------------------
// HTML helpers
// ---------------------------------------------------------------------------

function nodeHtml(type, icon, label, badge, bodyHtml) {
  return `
    <div class="pipeline-node node-${type}">
      <div class="node-header">
        <span class="node-icon">${icon}</span>
        <span class="node-label">${label}</span>
        <span class="node-badge">${badge}</span>
      </div>
      <div class="node-body">${bodyHtml}</div>
    </div>`;
}

function connector() {
  return `<div class="connector"><div class="connector-arrow"></div></div>`;
}

function dataRow(key, val) {
  return `<div class="data-row">
    <span class="data-key">${key}</span>
    <span class="data-val">${val}</span>
  </div>`;
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function decisionClass(decision) {
  if (decision === 'Strong Match')   return 'strong';
  if (decision === 'Possible Match') return 'possible';
  if (decision === 'Needs Review')   return 'review';
  return 'nq';
}

function formatTimestamp(ts) {
  try {
    return new Date(ts).toLocaleString([], {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch { return ts; }
}

function escapeHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ---------------------------------------------------------------------------
// Init + auto-refresh
// ---------------------------------------------------------------------------

loadRuns();
setInterval(loadRuns, 10000);
