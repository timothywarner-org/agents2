// Contoso HR Agent — Chat UI
// Chat history is persisted in localStorage under the session_id key.
// The session_id is also sent to the server so the backend can rebuild
// LLM context from data/chat_sessions/{session_id}.json across restarts.

const API_BASE = '';
let sessionId = localStorage.getItem('hr_session_id') || generateId();
localStorage.setItem('hr_session_id', sessionId);
let recentUploads = [];

// ---------------------------------------------------------------------------
// Chat history — localStorage persistence
// Key: "hr_history_{sessionId}"  Value: [{role, text, time}]
// ---------------------------------------------------------------------------

function loadHistory() {
  try {
    return JSON.parse(localStorage.getItem(`hr_history_${sessionId}`)) || [];
  } catch { return []; }
}

function saveHistory(history) {
  try {
    // Cap at 200 messages to avoid hitting localStorage limits
    const trimmed = history.slice(-200);
    localStorage.setItem(`hr_history_${sessionId}`, JSON.stringify(trimmed));
  } catch { /* storage full — silently skip */ }
}

function appendToHistory(role, text) {
  const history = loadHistory();
  history.push({ role, text, time: new Date().toISOString() });
  saveHistory(history);
}

// Clear history for the current session only (stays on same session ID).
function clearHistory() {
  localStorage.removeItem(`hr_history_${sessionId}`);
  fetch(`${API_BASE}/api/chat/history/${sessionId}`, { method: 'DELETE' }).catch(() => {});
}

// Start a brand-new blank session without touching the current one.
function newSession() {
  sessionId = generateId();
  localStorage.setItem('hr_session_id', sessionId);

  // Reset the message pane — keep only the static welcome message (first child)
  const container = document.getElementById('messages');
  while (container.children.length > 1) {
    container.removeChild(container.lastChild);
  }

  // Restore default suggestions
  document.getElementById('suggestions').innerHTML = `
    <button class="suggestion-btn" onclick="sendSuggestion(this)">Is MCT required for trainer roles?</button>
    <button class="suggestion-btn" onclick="sendSuggestion(this)">What Azure certs does Contoso value?</button>
    <button class="suggestion-btn" onclick="sendSuggestion(this)">How does the evaluation pipeline work?</button>
    <button class="suggestion-btn" onclick="sendSuggestion(this)">What makes a Strong Match candidate?</button>
    <button class="suggestion-btn" onclick="sendSuggestion(this)">How do I submit a resume for evaluation?</button>
    <button class="suggestion-btn" onclick="sendSuggestion(this)">What is Contoso's EEO policy?</button>
    <button class="suggestion-btn" onclick="sendSuggestion(this)">What does Contoso policy say about trainer bonuses and compensation?</button>
    <button class="suggestion-btn" onclick="sendSuggestion(this)">What learner-satisfaction score must trainers maintain per Contoso policy?</button>
  `;

  // Update session label and refresh past sessions list
  const label = document.getElementById('session-id-label');
  if (label) label.textContent = sessionId;
  loadPastSessions();
}

// Switch to a previously saved session.
function switchSession(id) {
  sessionId = id;
  localStorage.setItem('hr_session_id', id);
  location.reload();
}

// ---------------------------------------------------------------------------
// Restore previous session on page load
// Falls back to server-side JSON if localStorage has no history for this id.
// ---------------------------------------------------------------------------

async function restoreSession() {
  let history = loadHistory();

  // If localStorage is empty, try fetching from the server (covers the case
  // where the user switched sessions or cleared localStorage manually).
  if (!history.length) {
    try {
      const res = await fetch(`${API_BASE}/api/chat/history/${sessionId}`);
      if (res.ok) {
        const data = await res.json();
        if (data.history && data.history.length) {
          history = data.history.map(m => ({
            role: m.role === 'assistant' ? 'bot' : m.role,
            text: m.content,
            time: new Date().toISOString(),
          }));
          saveHistory(history);
        }
      }
    } catch { /* server unavailable — stay blank */ }
  }

  if (!history.length) return;

  const container = document.getElementById('messages');
  const divider = document.createElement('div');
  divider.style.cssText = 'text-align:center;font-size:11px;color:var(--contoso-gray-dark);padding:8px 0 4px;';
  divider.textContent = '— previous session restored —';
  container.appendChild(divider);

  history.forEach(({ role, text, time }) => {
    renderMessage(role, text, new Date(time));
  });
  container.scrollTop = container.scrollHeight;
}

// ---------------------------------------------------------------------------
// Past sessions panel
// ---------------------------------------------------------------------------

async function loadPastSessions() {
  const list = document.getElementById('past-sessions-list');
  const section = document.getElementById('past-sessions-section');
  if (!list || !section) return;

  try {
    const res = await fetch(`${API_BASE}/api/chat/sessions`);
    if (!res.ok) return;
    const data = await res.json();
    const sessions = (data.sessions || []).filter(s => s.message_count > 0);

    if (!sessions.length) {
      section.style.display = 'none';
      return;
    }

    section.style.display = 'block';
    list.innerHTML = sessions.map(s => {
      const isActive = s.session_id === sessionId;
      const preview = s.last_message_preview || '(no messages)';
      const timeLabel = formatRelativeTime(s.last_updated * 1000);
      return `
        <div class="session-item ${isActive ? 'active' : ''}" onclick="${isActive ? '' : `switchSession('${s.session_id}')`}" title="${escapeHtml(preview)}">
          <div class="session-item-preview">${escapeHtml(preview.length > 40 ? preview.slice(0, 40) + '…' : preview)}</div>
          <div class="session-item-meta">
            <span>${s.message_count} msgs</span>
            <span>${timeLabel}</span>
          </div>
          ${isActive ? '<span class="session-item-badge">current</span>' : ''}
        </div>
      `;
    }).join('');
  } catch { /* server unavailable */ }
}

function formatRelativeTime(ms) {
  const diff = Date.now() - ms;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

// ---------------------------------------------------------------------------
// Messaging
// ---------------------------------------------------------------------------

async function sendMessage(text) {
  const input = document.getElementById('chat-input');
  const message = (text || input.value).trim();
  if (!message) return;

  input.value = '';
  autoResize(input);
  clearSuggestions();

  renderMessage('user', message);
  appendToHistory('user', message);
  setLoading(true);

  try {
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, session_id: sessionId }),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    renderMessage('bot', data.reply, undefined, data.provenance);
    appendToHistory('bot', data.reply);

    if (data.suggestions && data.suggestions.length) {
      showSuggestions(data.suggestions);
    }
  } catch (err) {
    const errMsg = '⚠️ Connection error. Please check the server is running.';
    renderMessage('bot', errMsg);
    console.error('Chat error:', err);
  } finally {
    setLoading(false);
  }
}

function sendSuggestion(btn) {
  sendMessage(btn.textContent);
}

function handleKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
}

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

function setLoading(loading) {
  const btn = document.getElementById('send-btn');
  const input = document.getElementById('chat-input');
  btn.disabled = loading;
  input.disabled = loading;
  loading ? appendTypingIndicator() : removeTypingIndicator();
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

function renderMessage(role, text, timestamp, provenance) {
  const container = document.getElementById('messages');
  const isBot = role === 'bot';
  const time = timestamp || new Date();

  const div = document.createElement('div');
  div.className = `msg ${role}`;
  div.innerHTML = `
    <div class="msg-avatar">${isBot ? 'HR' : 'You'}</div>
    <div>
      <div class="msg-bubble">${escapeHtml(text).replace(/\n/g, '<br>')}</div>
      <div class="msg-time">${formatTime(time)}</div>
    </div>
  `;
  container.appendChild(div);

  if (isBot && provenance && (provenance.sources?.length || provenance.grounding?.tools_invoked?.length)) {
    div.querySelector('div:last-child').appendChild(renderProvenance(provenance));
  }

  container.scrollTop = container.scrollHeight;
}

// Render the collapsible sources + grounding block under an assistant reply.
// Sources are collapsed by default — a single chip "N sources" opens them.
// We deliberately do NOT show an LLM-generated confidence percentage;
// "grounding signals" are observable retrieval facts, which is honest.
function renderProvenance(prov) {
  const wrap = document.createElement('div');
  wrap.className = 'provenance';

  const sourceCount = (prov.sources || []).length;
  const g = prov.grounding || {};
  const topSim = (g.top_similarity != null) ? g.top_similarity.toFixed(2) : '—';
  const matched = g.chunks_above_threshold ?? 0;
  const total = g.retrieved_chunks ?? sourceCount;
  const tools = (g.tools_invoked || []).join(', ') || '(no tools used)';

  // Chip + grounding line. Chip is hidden when there are zero sources.
  const chipHtml = sourceCount > 0
    ? `<button class="provenance-chip" type="button">
         <span class="prov-icon">▸</span>
         <span>${sourceCount} source${sourceCount === 1 ? '' : 's'}</span>
       </button>`
    : '';

  wrap.innerHTML = `
    ${chipHtml}
    <div class="provenance-grounding">
      <span class="prov-label">Grounding signals:</span>
      <span class="prov-stat">${matched}/${total} chunks matched</span>
      <span class="prov-sep">•</span>
      <span class="prov-stat">top similarity ${topSim}</span>
      <span class="prov-sep">•</span>
      <span class="prov-stat">tools: ${escapeHtml(tools)}</span>
      <a href="rai.html" class="prov-rai-link" title="Why no confidence score?">why no confidence %?</a>
    </div>
    <div class="provenance-panel" hidden></div>
  `;

  if (sourceCount > 0) {
    const chip = wrap.querySelector('.provenance-chip');
    const panel = wrap.querySelector('.provenance-panel');
    panel.innerHTML = prov.sources.map((s, i) => renderSource(s, i)).join('');

    chip.addEventListener('click', () => {
      const open = !panel.hidden;
      panel.hidden = open;
      chip.querySelector('.prov-icon').textContent = open ? '▸' : '▾';
    });
  }

  if (prov.disclaimer) {
    const dis = document.createElement('div');
    dis.className = 'provenance-disclaimer';
    dis.textContent = prov.disclaimer;
    wrap.appendChild(dis);
  }

  return wrap;
}

function renderSource(src, idx) {
  const score = (src.score != null) ? `<span class="src-score">sim ${src.score.toFixed(2)}</span>` : '';
  const typeBadge = src.type === 'web' ? 'web' : 'policy';
  const preview = escapeHtml(src.preview || '');
  const fullText = escapeHtml(src.full_text || src.preview || '');
  const hasMore = src.full_text && src.full_text.length > (src.preview || '').length;
  const linkOpen = src.type === 'web' ? `<a href="${escapeHtml(src.name)}" target="_blank" rel="noopener">` : '';
  const linkClose = src.type === 'web' ? '</a>' : '';

  return `
    <div class="source-card" data-idx="${idx}">
      <div class="source-head">
        <span class="src-type src-type-${typeBadge}">${typeBadge}</span>
        <span class="src-name" title="${escapeHtml(src.name)}">${linkOpen}${escapeHtml(src.name)}${linkClose}</span>
        ${score}
      </div>
      <div class="source-preview">${preview}${hasMore ? '…' : ''}</div>
      ${hasMore ? `
        <button class="source-expand" type="button" onclick="toggleSourceFull(this)">show full chunk</button>
        <div class="source-full" hidden>${fullText}</div>
      ` : ''}
    </div>
  `;
}

function toggleSourceFull(btn) {
  const card = btn.closest('.source-card');
  const full = card.querySelector('.source-full');
  const isHidden = full.hidden;
  full.hidden = !isHidden;
  btn.textContent = isHidden ? 'hide full chunk' : 'show full chunk';
}

// Keep appendMessage as alias used by upload flow
function appendMessage(role, text) { renderMessage(role, text); }

function appendTypingIndicator() {
  const container = document.getElementById('messages');
  const div = document.createElement('div');
  div.className = 'msg bot';
  div.id = 'typing-indicator';
  div.innerHTML = `
    <div class="msg-avatar">HR</div>
    <div>
      <div class="msg-bubble" style="display:flex;align-items:center;gap:8px">
        <div class="spinner"></div>
        <span style="color:#666;font-size:13px">Thinking...</span>
      </div>
    </div>
  `;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function removeTypingIndicator() {
  const el = document.getElementById('typing-indicator');
  if (el) el.remove();
}

function showSuggestions(items) {
  const container = document.getElementById('suggestions');
  container.innerHTML = items.map(s =>
    `<button class="suggestion-btn" onclick="sendSuggestion(this)">${escapeHtml(s)}</button>`
  ).join('');
}

function clearSuggestions() {
  document.getElementById('suggestions').innerHTML = '';
}

// ---------------------------------------------------------------------------
// File Upload
// ---------------------------------------------------------------------------

function handleDragOver(e) {
  e.preventDefault();
  document.getElementById('drop-zone').classList.add('drag-over');
}

function handleDragLeave() {
  document.getElementById('drop-zone').classList.remove('drag-over');
}

function handleDrop(e) {
  e.preventDefault();
  document.getElementById('drop-zone').classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) uploadFile(file);
}

function handleFileSelect(e) {
  const file = e.target.files[0];
  if (file) uploadFile(file);
  e.target.value = '';
}

async function uploadFile(file) {
  const allowed = ['.txt', '.md', '.pdf', '.docx'];
  const ext = '.' + file.name.split('.').pop().toLowerCase();
  if (!allowed.includes(ext)) {
    showUploadStatus('error', `❌ Unsupported type: ${ext}. Use .txt, .md, .pdf, or .docx`);
    return;
  }

  showUploadStatus('loading', `Uploading ${file.name}...`);

  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch(`${API_BASE}/api/upload`, { method: 'POST', body: formData });
    const data = await res.json();

    if (data.status === 'queued') {
      showUploadStatus('success', `✅ ${file.name} queued!`);
      addRecentUpload(file.name, data.candidate_id);
      const botMsg = `📄 Resume received: ${file.name}\n\nThe AI pipeline is evaluating it now (Policy Expert → Resume Analyst → Decision Maker). Results appear on the Candidates page — it auto-refreshes every 10s.`;
      renderMessage('bot', botMsg);
      appendToHistory('bot', botMsg);
    } else {
      showUploadStatus('error', `❌ ${data.message}`);
    }
  } catch (err) {
    showUploadStatus('error', `❌ Upload failed: ${err.message}`);
    console.error('Upload error:', err);
  }
}

function showUploadStatus(type, message) {
  const el = document.getElementById('upload-status');
  el.className = `upload-status ${type}`;
  if (type === 'loading') {
    el.innerHTML = `<div class="spinner"></div> <span>${message}</span>`;
  } else {
    el.textContent = message;
  }
  if (type !== 'loading') setTimeout(() => { el.style.display = 'none'; }, 5000);
}

function addRecentUpload(filename, candidateId) {
  recentUploads.unshift({ filename, candidateId, time: new Date() });
  if (recentUploads.length > 5) recentUploads.pop();

  const section = document.getElementById('recent-uploads-section');
  const list = document.getElementById('recent-uploads-list');
  section.style.display = 'block';
  list.innerHTML = recentUploads.map(u => `
    <div class="upload-item">
      <span title="${escapeHtml(u.filename)}">📄 ${escapeHtml(u.filename.length > 22 ? u.filename.slice(0,22) + '…' : u.filename)}</span>
      <span class="badge badge-unknown" style="font-size:10px">${formatTime(u.time)}</span>
    </div>
  `).join('');
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatTime(d) {
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function generateId() {
  return Math.random().toString(36).slice(2, 10);
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

document.getElementById('welcome-time').textContent = formatTime(new Date());
restoreSession().then(() => loadPastSessions());
