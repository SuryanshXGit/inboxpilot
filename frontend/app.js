/**
 * INBOXPILOT 2.0 — FRONTEND APPLICATION CONTROLLER
 * Complete reactive client connecting to the FastAPI backend.
 */

(function () {
  'use strict';

  // State keys
  const TOKEN_KEY = 'inboxpilot_v2_token';
  const USER_KEY = 'inboxpilot_v2_user';
  const THEME_KEY = 'inboxpilot_v2_theme';

  // API Base Resolution
  const API_BASE = (() => {
    const override = new URLSearchParams(location.search).get('api');
    if (override !== null) return override.replace(/\/+$/, '');
    if (location.protocol === 'file:') return 'http://127.0.0.1:8000';
    if (['localhost', '127.0.0.1'].includes(location.hostname)) {
      return location.port === '8000' ? '' : 'http://127.0.0.1:8000';
    }
    if (typeof window.INBOXPILOT_API_BASE === 'string' && window.INBOXPILOT_API_BASE.trim()) {
      return window.INBOXPILOT_API_BASE.trim().replace(/\/+$/, '');
    }
    return '';
  })();

  // App State
  let authToken = localStorage.getItem(TOKEN_KEY) || '';
  let currentUser = null;
  try {
    currentUser = JSON.parse(localStorage.getItem(USER_KEY) || 'null');
  } catch {}

  let activeView = 'command-center';
  let activeInboxCategory = 'all';
  let activeInboxFilter = 'all';
  let activeTaskView = 'list';
  let activeThreadId = null;
  let calendarDate = new Date();
  let selectedDateStr = calendarDate.toISOString().split('T')[0];

  // Helper DOM shortcuts
  const $ = (id) => document.getElementById(id);
  const $$ = (sel) => document.querySelectorAll(sel);

  function escapeHtml(s) {
    return String(s || '').replace(/[&<>"']/g, (c) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
  }

  function showToast(msg, isError = false) {
    const toast = $('toastNotification');
    if (!toast) return;
    toast.textContent = msg;
    toast.style.borderColor = isError ? 'var(--accent-red)' : 'var(--border-strong)';
    toast.classList.add('show');
    clearTimeout(window._toastTimer);
    window._toastTimer = setTimeout(() => toast.classList.remove('show'), 3500);
  }

  async function api(path, options = {}) {
    const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
    if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

    try {
      const res = await fetch(API_BASE + path, { ...options, headers });
      if (res.status === 401 && authToken) {
        logout();
        showToast('Session expired. Please sign in again.', true);
        return null;
      }
      return res;
    } catch (err) {
      console.warn('Network request failed:', path, err);
      showToast('Backend unavailable. Operating in local mode.', true);
      return null;
    }
  }

  // =========================================================================
  // AUTHENTICATION & SESSION MANAGEMENT
  // =========================================================================

  function setSession(token, user) {
    authToken = token;
    currentUser = user;
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
    updateUserUI();
    showApp();
  }

  function logout() {
    authToken = '';
    currentUser = null;
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    showLanding();
    showToast('Signed out successfully.');
  }

  function updateUserUI() {
    if (!currentUser) return;
    const name = currentUser.display_name || currentUser.email.split('@')[0];
    const initial = name.slice(0, 2).toUpperCase();

    $('sidebarUserName').textContent = name;
    $('sidebarAvatar').textContent = initial;
    $('dropdownName').textContent = name;
    $('dropdownEmail').textContent = currentUser.email;
    $('avatarMenuBtn').textContent = initial;

    if ($('stEmail')) $('stEmail').value = currentUser.email;
    if ($('stDisplayName')) $('stDisplayName').value = currentUser.display_name || '';
  }

  function showLanding() {
    $('landingPage').style.display = 'flex';
    $('appShell').style.display = 'none';
  }

  function showApp() {
    $('landingPage').style.display = 'none';
    $('appShell').style.display = 'flex';
    switchView('command-center');
    refreshAllData();
  }

  // =========================================================================
  // VIEW NAVIGATION
  // =========================================================================

  function switchView(viewName) {
    activeView = viewName;
    $$('.section').forEach((sec) => sec.classList.remove('active'));
    $$('.nav-item').forEach((item) => {
      item.classList.toggle('active', item.dataset.view === viewName);
    });

    const target = $(`view-${viewName}`);
    if (target) target.classList.add('active');

    const titles = {
      'command-center': 'Command Center',
      'inbox': 'Smart Inbox',
      'assistant': 'AI Personal Assistant',
      'tasks': 'Tasks & Projects',
      'calendar': 'Calendar & Schedule',
      'knowledge': 'Knowledge Hub',
      'followups': 'Follow-ups Management',
      'automations': 'Automation Studio',
      'analytics': 'Productivity Analytics',
      'settings': 'Settings & Privacy',
    };
    if ($('pageTitle')) $('pageTitle').textContent = titles[viewName] || 'Command Center';

    // View specific initializations
    if (viewName === 'command-center') loadCommandCenter();
    else if (viewName === 'inbox') loadInboxThreads();
    else if (viewName === 'tasks') loadTasks();
    else if (viewName === 'calendar') renderCalendar();
    else if (viewName === 'knowledge') loadKnowledge();
    else if (viewName === 'followups') loadFollowups();
    else if (viewName === 'automations') loadAutomations();
    else if (viewName === 'analytics') loadAnalytics();
  }

  function refreshAllData() {
    loadCommandCenter();
    loadInboxThreads();
    loadTasks();
    loadAnalytics();
  }

  // =========================================================================
  // 1. COMMAND CENTER
  // =========================================================================

  async function loadCommandCenter() {
    const res = await api('/api/v1/productivity/briefing');
    if (!res || !res.ok) return;
    const briefing = await res.json();

    $('briefingGreeting').textContent = briefing.summary_greeting;
    $('briefingAdvice').textContent = briefing.focus_advice ? `💡 Recommended Focus: ${briefing.focus_advice}` : '';

    // Urgent items
    const urgentEl = $('briefingUrgentList');
    if (urgentEl) {
      urgentEl.innerHTML = briefing.urgent_priorities.length
        ? briefing.urgent_priorities.map((item) => `
            <div class="briefing-item" role="button" onclick="window.InboxPilot.openThreadById('${item.id}')">
              <strong style="color:var(--accent-red);">${escapeHtml(item.title)}</strong>
              <small>${escapeHtml(item.reason || item.snippet)}</small>
            </div>
          `).join('')
        : '<p class="subtle">No urgent email blockers right now.</p>';
    }

    // Today's tasks
    const taskEl = $('briefingTaskList');
    if (taskEl) {
      taskEl.innerHTML = briefing.todays_tasks.length
        ? briefing.todays_tasks.map((t) => `
            <div class="briefing-item">
              <strong>${escapeHtml(t.title)}</strong>
              <small style="color:var(--accent-yellow);">Due: ${escapeHtml(t.due_at || 'Today')}</small>
            </div>
          `).join('')
        : '<p class="subtle">All objectives clear for today.</p>';
    }

    // Meetings
    const meetEl = $('briefingMeetingList');
    if (meetEl) {
      meetEl.innerHTML = briefing.todays_meetings.length
        ? briefing.todays_meetings.map((m) => `
            <div class="briefing-item">
              <strong>${escapeHtml(m.title)}</strong>
              <small>${escapeHtml(m.time)} · ${escapeHtml(m.location)}</small>
            </div>
          `).join('')
        : '<p class="subtle">No meetings on the agenda today.</p>';
    }

    // Load Deadline Radar
    const radarRes = await api('/api/v1/productivity/deadline-radar');
    if (radarRes && radarRes.ok) {
      const radar = await radarRes.json();
      $('deadlineRadarList').innerHTML = radar.length
        ? radar.map((r) => `
            <div class="task-item-row">
              <span class="badge ${r.urgency === 'urgent' || r.urgency === 'high' ? 'red' : 'yellow'}">${r.urgency.toUpperCase()}</span>
              <div class="task-text">${escapeHtml(r.title)}</div>
              <div class="task-due">${escapeHtml(r.due_date)}</div>
            </div>
          `).join('')
        : '<p class="subtle">No impending deadlines detected.</p>';
    }
  }

  // =========================================================================
  // 2. SMART INBOX
  // =========================================================================

  async function loadInboxThreads() {
    let url = `/api/v1/emails/threads?page_size=30`;
    if (activeInboxCategory !== 'all') url += `&category=${encodeURIComponent(activeInboxCategory)}`;
    if (activeInboxFilter === 'unread') url += `&unread=true`;
    if (activeInboxFilter === 'starred') url += `&starred=true`;
    if (activeInboxFilter === 'high') url += `&priority=HIGH`;

    const searchVal = $('globalSearch')?.value.trim();
    if (searchVal) url += `&search=${encodeURIComponent(searchVal)}`;

    const res = await api(url);
    if (!res || !res.ok) return;
    const data = await res.json();

    // Update badges
    $('navInboxBadge').textContent = data.unread_count || '0';
    $('metricInboxTotal').textContent = data.total_count || '0';
    $('metricInboxHigh').textContent = `${data.priority_count || 0} high priority`;

    // Category pills breakdown
    if (data.categories_breakdown) {
      const b = data.categories_breakdown;
      $('catAllCount').textContent = data.total_count;
      $('catPrimaryCount').textContent = b['Primary'] || 0;
      $('catWorkCount').textContent = b['Work'] || 0;
      $('catFinanceCount').textContent = b['Finance'] || 0;
      $('catEducationCount').textContent = b['Education'] || 0;
      $('catUpdatesCount').textContent = b['Updates'] || 0;
      $('catSpamCount').textContent = b['Spam/Suspicious'] || 0;
    }

    $('inboxStatusSummary').textContent = `${data.total_count} total threads · ${data.unread_count} unread`;

    // Render rows
    const list = $('threadList');
    if (!data.threads.length) {
      list.innerHTML = `<div class="card" style="text-align:center; padding:48px;">
        <h3>No emails found in this category.</h3>
        <p class="subtle">Connect an email provider or click "Sync Now" to refresh messages.</p>
      </div>`;
      return;
    }

    list.innerHTML = data.threads.map((t) => `
      <div class="thread-row ${t.is_unread ? 'unread' : ''}" onclick="window.InboxPilot.openThreadById('${t.id}')">
        <span class="thread-star ${t.is_starred ? 'starred' : ''}" onclick="event.stopPropagation(); window.InboxPilot.toggleStar('${t.id}')">
          ${t.is_starred ? '★' : '☆'}
        </span>
        <div class="thread-sender">${escapeHtml(t.snippet.split(' ')[0] || 'Sender')}</div>
        <div class="thread-content-preview">
          <span class="thread-subject">${escapeHtml(t.subject)}</span>
          <span class="thread-snippet">${escapeHtml(t.snippet)}</span>
        </div>
        <div class="thread-meta-tags">
          <span class="tag-priority-${t.priority.toLowerCase()}">${t.priority}</span>
          <span class="tag-category">${escapeHtml(t.category)}</span>
        </div>
        <div class="thread-time">${t.latest_at ? t.latest_at.slice(11, 16) : ''}</div>
      </div>
    `).join('');

    // Also update Command Center Preview
    const previewList = $('priorityEmailPreviewList');
    if (previewList) {
      previewList.innerHTML = data.threads.slice(0, 4).map((t) => `
        <div class="task-item-row" onclick="window.InboxPilot.openThreadById('${t.id}')" style="cursor:pointer;">
          <span class="tag-priority-${t.priority.toLowerCase()}">${t.priority}</span>
          <div class="task-text">${escapeHtml(t.subject)}</div>
          <div class="task-due">${escapeHtml(t.category)}</div>
        </div>
      `).join('');
    }
  }

  async function openThreadDetail(threadId) {
    activeThreadId = threadId;
    const res = await api(`/api/v1/emails/threads/${threadId}`);
    if (!res || !res.ok) return;
    const data = await res.json();
    const thread = data.thread;
    const messages = data.messages;

    $('modalThreadSubject').textContent = thread.subject;
    $('modalThreadCategory').textContent = thread.category;
    $('modalThreadPriority').textContent = thread.priority;
    $('modalThreadPriority').className = `badge ${thread.priority === 'HIGH' ? 'red' : 'yellow'}`;

    // Security warning banner
    const isPhishing = messages.some((m) => m.is_phishing);
    const banner = $('threadSecurityBanner');
    if (isPhishing) {
      banner.hidden = false;
      const reasons = messages.flatMap((m) => m.phishing_indicators || []);
      $('threadSecurityReason').innerHTML = reasons.length
        ? `<strong>Risk Indicators:</strong><ul>${reasons.map((r) => `<li>${escapeHtml(r)}</li>`).join('')}</ul>`
        : 'Suspicious domain and urgent payment/credential demand detected.';
    } else {
      banner.hidden = true;
    }

    // Hide AI output initially
    $('threadAiOutput').hidden = true;
    $('replyDraftBox').hidden = true;

    // Messages
    const stream = $('threadMessagesStream');
    stream.innerHTML = messages.map((m) => `
      <div class="message-card">
        <div class="message-header">
          <div><strong>${escapeHtml(m.sender_name)}</strong> &lt;${escapeHtml(m.sender_email)}&gt;</div>
          <div class="subtle">${escapeHtml(m.received_at)}</div>
        </div>
        <div class="message-body">${escapeHtml(m.body_text)}</div>
      </div>
    `).join('');

    $('threadModal').hidden = false;
  }

  // =========================================================================
  // AI EMAIL ACTIONS (Summarize, Extract Tasks, Draft Reply)
  // =========================================================================

  async function summarizeActiveThread() {
    if (!activeThreadId) return;
    $('aiOutputTitle').textContent = '✦ AI Thread Summary & Decisions';
    $('aiOutputContent').innerHTML = '<p>Analyzing thread context with Groq AI...</p>';
    $('threadAiOutput').hidden = false;

    const res = await api(`/api/v1/emails/threads/${activeThreadId}/summarize`, { method: 'POST' });
    if (!res || !res.ok) {
      $('aiOutputContent').innerHTML = '<p class="subtle">Could not generate summary at this moment.</p>';
      return;
    }
    const data = await res.json();
    $('aiOutputContent').innerHTML = `
      <p style="margin-bottom:12px;"><strong>Overview:</strong> ${escapeHtml(data.overview)}</p>
      ${data.key_points && data.key_points.length ? `<strong>Key Points:</strong><ul>${data.key_points.map((p) => `<li>${escapeHtml(p)}</li>`).join('')}</ul>` : ''}
      ${data.decisions && data.decisions.length ? `<strong>Decisions Made:</strong><ul>${data.decisions.map((d) => `<li>${escapeHtml(d)}</li>`).join('')}</ul>` : ''}
      ${data.next_steps && data.next_steps.length ? `<strong>Next Steps:</strong><ul>${data.next_steps.map((n) => `<li>${escapeHtml(n)}</li>`).join('')}</ul>` : ''}
    `;
  }

  async function extractTasksFromActiveThread() {
    if (!activeThreadId) return;
    $('aiOutputTitle').textContent = '☑ Extracted Action Items';
    $('aiOutputContent').innerHTML = '<p>Extracting actionable tasks and deadlines...</p>';
    $('threadAiOutput').hidden = false;

    const res = await api(`/api/v1/emails/threads/${activeThreadId}/extract-tasks`, { method: 'POST' });
    if (!res || !res.ok) {
      $('aiOutputContent').innerHTML = '<p class="subtle">No tasks extracted.</p>';
      return;
    }
    const data = await res.json();
    const tasks = data.tasks || [];
    if (!tasks.length) {
      $('aiOutputContent').innerHTML = '<p>No concrete action items were found in this conversation.</p>';
      return;
    }

    $('aiOutputContent').innerHTML = `
      <p style="margin-bottom:8px;">Review extracted items and click <strong>Approve Task</strong> to add them to your tasks list:</p>
      <div style="display:flex; flex-direction:column; gap:8px;">
        ${tasks.map((t, idx) => `
          <div class="task-item-row" style="background:var(--bg-card);">
            <div style="flex:1;">
              <strong>${escapeHtml(t.title)}</strong>
              <div class="subtle">${escapeHtml(t.description)} · Due: ${escapeHtml(t.due_date || 'None')} · Priority: ${t.priority.toUpperCase()} · Confidence: ${Math.round(t.confidence * 100)}%</div>
            </div>
            <button type="button" class="btn-primary" style="padding:4px 10px; font-size:12px;" onclick="window.InboxPilot.approveTask('${escapeHtml(t.title)}', '${escapeHtml(t.description)}', '${escapeHtml(t.due_date || '')}', '${t.priority}')">
              ✓ Approve Task
            </button>
          </div>
        `).join('')}
      </div>
    `;
  }

  async function draftReplyForActiveThread() {
    if (!activeThreadId) return;
    const tone = $('replyToneSelect').value || 'professional';
    $('replyDraftBox').hidden = false;
    $('replyDraftText').value = 'Generating contextual reply draft with Groq...';

    const res = await api(`/api/v1/emails/threads/${activeThreadId}/reply-draft`, {
      method: 'POST',
      body: JSON.stringify({ tone, user_notes: '' }),
    });
    if (!res || !res.ok) {
      $('replyDraftText').value = 'Could not generate draft.';
      return;
    }
    const data = await res.json();
    $('replyDraftText').value = data.reply_body;
  }

  // =========================================================================
  // 3. AI PERSONAL ASSISTANT
  // =========================================================================

  async function sendAssistantQuery(queryText) {
    if (!queryText.trim()) return;
    const history = $('assistantChatHistory');

    // Add user bubble
    const userBubble = document.createElement('div');
    userBubble.className = 'chat-bubble user';
    userBubble.innerHTML = `
      <div class="bubble-avatar">You</div>
      <div class="bubble-content"><p>${escapeHtml(queryText)}</p></div>
    `;
    history.appendChild(userBubble);
    $('assistantQueryInput').value = '';
    history.scrollTop = history.scrollHeight;

    // Add typing assistant bubble
    const botBubble = document.createElement('div');
    botBubble.className = 'chat-bubble assistant';
    botBubble.innerHTML = `
      <div class="bubble-avatar">🤖</div>
      <div class="bubble-content"><p>Thinking and cross-referencing your emails and tasks...</p></div>
    `;
    history.appendChild(botBubble);
    history.scrollTop = history.scrollHeight;

    const res = await api('/api/v1/assistant/query', {
      method: 'POST',
      body: JSON.stringify({ query: queryText, include_emails: true, include_tasks: true, include_calendar: true }),
    });

    if (!res || !res.ok) {
      botBubble.querySelector('.bubble-content').innerHTML = '<p>Could not retrieve assistant response at this moment.</p>';
      return;
    }

    const data = await res.json();
    let citationsHtml = '';
    if (data.sources && data.sources.length) {
      citationsHtml = `<div class="citation-box"><strong>Sources referenced:</strong><ul>${data.sources.map((s) => `<li>${escapeHtml(s.title || s.subject || 'Context record')}</li>`).join('')}</ul></div>`;
    }

    let actionsHtml = '';
    if (data.suggested_actions && data.suggested_actions.length) {
      actionsHtml = `<div class="citation-box"><strong>Suggested Next Actions:</strong><ul>${data.suggested_actions.map((a) => `<li>${escapeHtml(a)}</li>`).join('')}</ul></div>`;
    }

    botBubble.querySelector('.bubble-content').innerHTML = `<p>${escapeHtml(data.answer)}</p>${citationsHtml}${actionsHtml}`;
    history.scrollTop = history.scrollHeight;
  }

  // =========================================================================
  // 4. TASKS & KANBAN
  // =========================================================================

  async function loadTasks() {
    const res = await api('/api/v1/tasks');
    if (!res || !res.ok) return;
    const tasks = await res.json();

    $('navTaskBadge').textContent = tasks.filter((t) => t.status !== 'completed').length;
    $('metricTasksTotal').textContent = tasks.length;
    $('metricTasksCompleted').textContent = `${tasks.filter((t) => t.status === 'completed').length} completed`;
    $('tasksListCount').textContent = `${tasks.length} total tasks`;

    // Render List View
    const listEl = $('tasksAllList');
    listEl.innerHTML = tasks.length
      ? tasks.map((t) => `
          <div class="task-item-row">
            <input type="checkbox" class="task-checkbox" ${t.status === 'completed' ? 'checked' : ''} onchange="window.InboxPilot.toggleTask('${t.id}', this.checked)"/>
            <div class="task-text ${t.status === 'completed' ? 'completed' : ''}">${escapeHtml(t.title)}</div>
            <div class="task-due">${escapeHtml(t.due_at || '')}</div>
            <span class="badge ${t.priority === 'urgent' || t.priority === 'high' ? 'red' : 'yellow'}">${t.priority}</span>
            <button type="button" class="btn-ghost" style="padding:4px 8px;" onclick="window.InboxPilot.deleteTask('${t.id}')">✕</button>
          </div>
        `).join('')
      : '<p class="subtle">No tasks created yet. Click "+ New Task" above.</p>';

    // Render Kanban View
    const kbRes = await api('/api/v1/tasks/kanban');
    if (kbRes && kbRes.ok) {
      const kb = await kbRes.json();
      $('kbTodoCount').textContent = kb.todo.length;
      $('kbProgressCount').textContent = kb.in_progress.length;
      $('kbBlockedCount').textContent = kb.blocked.length;
      $('kbCompletedCount').textContent = kb.completed.length;

      const renderCol = (arr) => arr.map((t) => `
        <div class="kanban-card">
          <h4>${escapeHtml(t.title)}</h4>
          <p>${escapeHtml(t.description || t.due_at || '')}</p>
          <div style="display:flex; justify-content:space-between; align-items:center; margin-top:4px;">
            <span class="badge ${t.priority === 'urgent' || t.priority === 'high' ? 'red' : 'yellow'}">${t.priority}</span>
            <small class="subtle">${escapeHtml(t.due_at || '')}</small>
          </div>
        </div>
      `).join('');

      $('kbTodoCards').innerHTML = renderCol(kb.todo);
      $('kbProgressCards').innerHTML = renderCol(kb.in_progress);
      $('kbBlockedCards').innerHTML = renderCol(kb.blocked);
      $('kbCompletedCards').innerHTML = renderCol(kb.completed);
    }
  }

  // =========================================================================
  // 5. CALENDAR
  // =========================================================================

  async function renderCalendar() {
    const year = calendarDate.getFullYear();
    const month = calendarDate.getMonth();
    const monthNames = ['January','February','March','April','May','June','July','August','September','October','November','December'];
    $('calendarMonthTitle').textContent = `${monthNames[month]} ${year}`;

    const res = await api('/api/v1/calendar/events');
    const events = (res && res.ok) ? await res.json() : [];

    const firstDay = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const grid = $('calendarMonthGrid');
    grid.innerHTML = '';

    // Blank cells before first day
    for (let i = 0; i < firstDay; i++) {
      grid.appendChild(document.createElement('div'));
    }

    const todayStr = new Date().toISOString().split('T')[0];

    for (let day = 1; day <= daysInMonth; day++) {
      const dStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
      const dayCell = document.createElement('div');
      dayCell.className = `calendar-day-cell ${dStr === todayStr ? 'today' : ''} ${dStr === selectedDateStr ? 'selected' : ''}`;
      dayCell.onclick = () => {
        selectedDateStr = dStr;
        renderCalendar();
      };

      const dayEvents = events.filter((e) => (e.starts_at || '').startsWith(dStr));
      const dotsHtml = dayEvents.slice(0, 3).map((e) => `<span class="dot-event ${e.priority || 'medium'}"></span>`).join('');

      dayCell.innerHTML = `
        <span class="day-number">${day}</span>
        <div class="day-dots">${dotsHtml}</div>
      `;
      grid.appendChild(dayCell);
    }

    // Render selected day's events
    const dayEvents = events.filter((e) => (e.starts_at || '').startsWith(selectedDateStr));
    $('calendarDayHeading').textContent = `Events for ${selectedDateStr}`;
    $('calendarDayCount').textContent = `${dayEvents.length} events scheduled`;

    $('calendarDayEventsList').innerHTML = dayEvents.length
      ? dayEvents.map((e) => `
          <div class="calendar-event-item">
            <strong>${escapeHtml(e.title)}</strong>
            <small>${escapeHtml(e.starts_at.slice(11, 16) || '')} · ${escapeHtml(e.location || 'Online')}</small>
          </div>
        `).join('')
      : '<p class="subtle">No events scheduled for this day.</p>';
  }

  // =========================================================================
  // 6. KNOWLEDGE HUB, FOLLOW-UPS, AUTOMATIONS, ANALYTICS
  // =========================================================================

  async function loadKnowledge() {
    const q = $('knowledgeSearchInput')?.value.trim();
    let url = '/api/v1/knowledge';
    if (q) url += `?search=${encodeURIComponent(q)}`;

    const res = await api(url);
    if (!res || !res.ok) return;
    const items = await res.json();

    $('knowledgeGrid').innerHTML = items.length
      ? items.map((it) => `
          <div class="knowledge-card">
            <span class="badge" style="align-self:flex-start;">${escapeHtml(it.category)}</span>
            <h3>${escapeHtml(it.title)}</h3>
            <p>${escapeHtml(it.content)}</p>
            <div class="tags-wrap">${(it.tags || []).map((tag) => `<span class="tag-chip">#${escapeHtml(tag)}</span>`).join('')}</div>
          </div>
        `).join('')
      : '<p class="subtle">No knowledge items saved yet.</p>';
  }

  async function loadFollowups() {
    const res = await api('/api/v1/follow-ups');
    if (!res || !res.ok) return;
    const items = await res.json();

    $('followupsCount').textContent = `${items.length} items`;
    $('navFollowupBadge').textContent = items.filter((f) => f.status === 'pending').length;

    $('followupsList').innerHTML = items.length
      ? items.map((f) => `
          <div class="followup-row">
            <div class="followup-main">
              <strong>${escapeHtml(f.recipient)} — ${escapeHtml(f.subject)}</strong>
              <p>Expected by: <span style="color:var(--accent-yellow); font-weight:600;">${escapeHtml(f.expected_by)}</span> · ${escapeHtml(f.suggested_action)}</p>
            </div>
            <div class="followup-actions">
              <button type="button" class="btn-secondary" onclick="window.InboxPilot.snoozeFollowup('${f.id}')">Snooze</button>
              <button type="button" class="btn-primary" onclick="window.InboxPilot.resolveFollowup('${f.id}')">✓ Received Reply</button>
            </div>
          </div>
        `).join('')
      : '<p class="subtle">All conversations currently up to date.</p>';
  }

  async function loadAutomations() {
    const res = await api('/api/v1/automations/workflows');
    if (!res || !res.ok) return;
    const workflows = await res.json();

    $('workflowsList').innerHTML = workflows.map((wf) => `
      <div class="workflow-card">
        <div class="workflow-head">
          <h3>${escapeHtml(wf.name)}</h3>
          <span class="badge ${wf.is_active ? 'green' : ''}">${wf.is_active ? 'ACTIVE' : 'PAUSED'}</span>
        </div>
        <div class="workflow-steps">
          <div class="wf-step"><span class="wf-step-badge">TRIGGER</span> ${escapeHtml(wf.trigger_type)}</div>
          <div class="wf-step"><span class="wf-step-badge">ACTION</span> ${wf.actions.length} action(s) configured</div>
        </div>
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <button type="button" class="btn-secondary" onclick="window.InboxPilot.testWorkflow('${wf.id}')">⚡ Test Run</button>
          <button type="button" class="btn-ghost" onclick="window.InboxPilot.toggleWorkflow('${wf.id}')">${wf.is_active ? 'Pause' : 'Enable'}</button>
        </div>
      </div>
    `).join('');

    // Load runs history
    const runsRes = await api('/api/v1/automations/runs');
    if (runsRes && runsRes.ok) {
      const runs = await runsRes.json();
      $('workflowRunsList').innerHTML = runs.length
        ? runs.map((r) => `
            <div class="task-item-row" style="font-size:13px;">
              <span class="badge green">SUCCESS</span>
              <div style="flex:1;">${escapeHtml(r.result_summary)}</div>
              <small class="subtle">${r.started_at ? r.started_at.slice(11, 16) : ''}</small>
            </div>
          `).join('')
        : '<p class="subtle">No execution runs logged yet.</p>';
    }
  }

  async function loadAnalytics() {
    const res = await api('/api/v1/analytics/overview');
    if (!res || !res.ok) return;
    const an = await res.json();

    $('anEmailsProcessed').textContent = an.emails_processed;
    $('anTasksCompleted').textContent = an.tasks_completed;
    $('anPendingFollowups').textContent = an.pending_follow_ups;
    $('anHoursReclaimed').textContent = an.time_saved_hours.toFixed(1);
    $('metricTimeSaved').textContent = `${an.time_saved_hours.toFixed(1)} hrs`;

    // Render Category Distribution Chart
    const catContainer = $('anCategoryChart');
    if (catContainer && an.categories_breakdown) {
      const total = an.emails_processed || 1;
      catContainer.innerHTML = Object.entries(an.categories_breakdown).map(([cat, count]) => {
        const pct = Math.round((count / total) * 100);
        return `
          <div style="margin-bottom:10px;">
            <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:4px;">
              <strong>${escapeHtml(cat)}</strong>
              <span>${count} (${pct}%)</span>
            </div>
            <div style="height:8px; background:var(--bg-secondary); border-radius:4px; overflow:hidden;">
              <div style="height:100%; width:${pct}%; background:var(--brand-primary); border-radius:4px;"></div>
            </div>
          </div>
        `;
      }).join('');
    }

    // Render Weekly Velocity Chart
    const weekContainer = $('anWeeklyChart');
    if (weekContainer && an.weekly_trend) {
      weekContainer.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:flex-end; height:140px; padding-top:20px;">
          ${an.weekly_trend.map((w) => `
            <div style="display:flex; flex-direction:column; align-items:center; gap:6px; flex:1;">
              <div style="height:${Math.min(100, w.emails * 4)}px; width:18px; background:var(--brand-primary); border-radius:4px;" title="${w.emails} emails"></div>
              <small style="font-size:11px; color:var(--text-muted);">${w.day}</small>
            </div>
          `).join('')}
        </div>
      `;
    }
  }

  // =========================================================================
  // GLOBAL EXPORTS & EVENT LISTENERS
  // =========================================================================

  window.InboxPilot = {
    openThreadById: openThreadDetail,
    toggleStar: async (threadId) => {
      await api(`/api/v1/emails/threads/${threadId}/star`, { method: 'POST' });
      loadInboxThreads();
    },
    approveTask: async (title, desc, due, prio) => {
      const res = await api('/api/v1/tasks/approve-extracted', {
        method: 'POST',
        body: JSON.stringify({ title, description: desc, due_at: due, priority: prio, confidence: 0.95 }),
      });
      if (res && res.ok) {
        showToast('Task approved and created successfully!');
        loadTasks();
      }
    },
    toggleTask: async (taskId, checked) => {
      await api(`/api/v1/tasks/${taskId}`, {
        method: 'PUT',
        body: JSON.stringify({ status: checked ? 'completed' : 'todo' }),
      });
      loadTasks();
    },
    deleteTask: async (taskId) => {
      await api(`/api/v1/tasks/${taskId}`, { method: 'DELETE' });
      loadTasks();
      showToast('Task deleted.');
    },
    snoozeFollowup: async (fuId) => {
      await api(`/api/v1/follow-ups/${fuId}`, {
        method: 'PATCH',
        body: JSON.stringify({ expected_by: 'Next Week' }),
      });
      loadFollowups();
      showToast('Follow-up snoozed to next week.');
    },
    resolveFollowup: async (fuId) => {
      await api(`/api/v1/follow-ups/${fuId}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: 'replied' }),
      });
      loadFollowups();
      showToast('Marked as response received.');
    },
    toggleWorkflow: async (wfId) => {
      await api(`/api/v1/automations/workflows/${wfId}/toggle`, { method: 'POST' });
      loadAutomations();
    },
    testWorkflow: async (wfId) => {
      const res = await api(`/api/v1/automations/workflows/${wfId}/test`, { method: 'POST' });
      if (res && res.ok) {
        showToast('Workflow execution test succeeded!');
        loadAutomations();
      }
    },
  };

  // DOM Event Bindings
  document.addEventListener('DOMContentLoaded', () => {
    // Check initial auth state
    if (authToken && currentUser) {
      updateUserUI();
      showApp();
    } else {
      showLanding();
    }

    // Landing navigation buttons
    $('landingLoginBtn')?.addEventListener('click', () => {
      $('authModal').hidden = false;
      $('tabLoginBtn').click();
    });
    $('landingRegisterBtn')?.addEventListener('click', () => {
      $('authModal').hidden = false;
      $('tabRegisterBtn').click();
    });
    $('heroStartBtn')?.addEventListener('click', () => {
      if (authToken) showApp();
      else {
        $('authModal').hidden = false;
        $('tabRegisterBtn').click();
      }
    });
    $('heroDemoBtn')?.addEventListener('click', async () => {
      // Auto sign in as demo user
      const demoEmail = 'alex.demo@inboxpilot.io';
      const demoPass = 'DemoPassword123!';
      let res = await api('/api/v1/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email: demoEmail, password: demoPass }),
      });
      if (!res || !res.ok) {
        res = await api('/api/v1/auth/register', {
          method: 'POST',
          body: JSON.stringify({ email: demoEmail, password: demoPass, display_name: 'Alex (Demo)' }),
        });
      }
      if (res && res.ok) {
        const data = await res.json();
        setSession(data.access_token, data.user);
        showToast('Welcome to InboxPilot 2.0 interactive demo!');
      }
    });
    $('pricingBetaBtn')?.addEventListener('click', () => {
      $('authModal').hidden = false;
      $('tabRegisterBtn').click();
    });
    $('footerAppBtn')?.addEventListener('click', () => showApp());

    // Navigation links in app
    $$('.nav-item').forEach((item) => {
      item.addEventListener('click', () => switchView(item.dataset.view));
    });
    $$('[data-go]').forEach((el) => {
      el.addEventListener('click', () => switchView(el.dataset.go));
    });

    $('brandHomeBtn')?.addEventListener('click', () => showLanding());

    // Mobile sidebar toggle
    $('mobileSidebarToggle')?.addEventListener('click', () => {
      $('appSidebar').classList.toggle('open');
    });
    $('sidebarToggle')?.addEventListener('click', () => {
      $('appSidebar').classList.toggle('collapsed');
    });

    // Theme toggle
    $('themeToggleBtn')?.addEventListener('click', () => {
      const current = document.documentElement.getAttribute('data-theme') || 'dark';
      const next = current === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      localStorage.setItem(THEME_KEY, next);
    });

    // Profile menu toggle
    $('avatarMenuBtn')?.addEventListener('click', (e) => {
      e.stopPropagation();
      const menu = $('profileDropdown');
      menu.hidden = !menu.hidden;
    });
    document.addEventListener('click', () => {
      if ($('profileDropdown')) $('profileDropdown').hidden = true;
    });
    $('logoutActionBtn')?.addEventListener('click', logout);

    // Auth modal tabs
    $('tabLoginBtn')?.addEventListener('click', () => {
      $('tabLoginBtn').classList.add('active');
      $('tabRegisterBtn').classList.remove('active');
      $('displayNameField').hidden = true;
      $('authModalTitle').textContent = 'Sign In to InboxPilot';
      $('authSubmitBtn').textContent = 'Sign In →';
    });
    $('tabRegisterBtn')?.addEventListener('click', () => {
      $('tabRegisterBtn').classList.add('active');
      $('tabLoginBtn').classList.remove('active');
      $('displayNameField').hidden = false;
      $('authModalTitle').textContent = 'Create InboxPilot Account';
      $('authSubmitBtn').textContent = 'Get Started Free →';
    });
    $('closeAuthModal')?.addEventListener('click', () => $('authModal').hidden = true);

    // Auth Form submit
    $('authForm')?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const isRegister = $('tabRegisterBtn').classList.contains('active');
      const email = $('authEmail').value.trim();
      const password = $('authPassword').value;
      const display_name = $('authDisplayName')?.value.trim();

      const path = isRegister ? '/api/v1/auth/register' : '/api/v1/auth/login';
      const body = isRegister ? { email, password, display_name } : { email, password };

      $('authErrorMsg').hidden = true;
      const res = await api(path, { method: 'POST', body: JSON.stringify(body) });
      if (!res || !res.ok) {
        const err = res ? await res.json() : { detail: 'Request failed' };
        $('authErrorMsg').textContent = err.detail || 'Authentication failed.';
        $('authErrorMsg').hidden = false;
        return;
      }
      const data = await res.json();
      $('authModal').hidden = true;
      setSession(data.access_token, data.user);
      showToast(isRegister ? 'Account created! Welcome to InboxPilot.' : 'Signed in successfully.');
    });

    // Close modals
    $('closeThreadModal')?.addEventListener('click', () => $('threadModal').hidden = true);
    $('closeAiOutput')?.addEventListener('click', () => $('threadAiOutput').hidden = true);
    $('cancelReplyBtn')?.addEventListener('click', () => $('replyDraftBox').hidden = true);
    $('confirmSendReplyBtn')?.addEventListener('click', () => {
      showToast('Reply draft approved! (Simulated send in demo mode)');
      $('replyDraftBox').hidden = true;
      $('threadModal').hidden = true;
    });

    // AI thread actions
    $('aiSummarizeBtn')?.addEventListener('click', summarizeActiveThread);
    $('aiExtractTasksBtn')?.addEventListener('click', extractTasksFromActiveThread);
    $('aiDraftReplyBtn')?.addEventListener('click', draftReplyForActiveThread);

    // Assistant form
    $('assistantForm')?.addEventListener('submit', (e) => {
      e.preventDefault();
      sendAssistantQuery($('assistantQueryInput').value);
    });
    $$('.query-chip').forEach((chip) => {
      chip.addEventListener('click', () => sendAssistantQuery(chip.dataset.query));
    });

    // Inbox category filtering
    $$('#inboxCategoryTabs .cat-pill').forEach((btn) => {
      btn.addEventListener('click', () => {
        $$('#inboxCategoryTabs .cat-pill').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        activeInboxCategory = btn.dataset.category;
        loadInboxThreads();
      });
    });

    // Inbox status filters
    $$('.toolbar-filters .filter-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        $$('.toolbar-filters .filter-btn').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        activeInboxFilter = btn.dataset.filter;
        loadInboxThreads();
      });
    });

    $('syncInboxBtn')?.addEventListener('click', async () => {
      showToast('Synchronizing messages with provider...');
      await loadInboxThreads();
      showToast('Inbox is up to date.');
    });

    // Task view switch
    $$('[data-taskview]').forEach((btn) => {
      btn.addEventListener('click', () => {
        $$('[data-taskview]').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        activeTaskView = btn.dataset.taskview;
        $('tasksListView').style.display = activeTaskView === 'list' ? 'block' : 'none';
        $('tasksKanbanView').style.display = activeTaskView === 'kanban' ? 'block' : 'none';
      });
    });

    // Quick Add modal
    $('topbarAddBtn')?.addEventListener('click', () => $('quickAddModal').hidden = false);
    $('createTaskBtn')?.addEventListener('click', () => $('quickAddModal').hidden = false);
    $('closeQuickAddModal')?.addEventListener('click', () => $('quickAddModal').hidden = true);
    $('cancelQuickAdd')?.addEventListener('click', () => $('quickAddModal').hidden = true);

    $('quickAddForm')?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const title = $('qaTitle').value.trim();
      const desc = $('qaDescription').value.trim();
      const due = $('qaDue').value.trim();
      const priority = $('qaPriority').value;

      const res = await api('/api/v1/tasks', {
        method: 'POST',
        body: JSON.stringify({ title, description: desc, due_at: due, priority }),
      });
      if (res && res.ok) {
        showToast('Task created successfully!');
        $('quickAddModal').hidden = true;
        $('quickAddForm').reset();
        loadTasks();
      }
    });

    // Connect account modal
    $('connectAccountBtn')?.addEventListener('click', () => $('connectAccountModal').hidden = false);
    $('stAddAccountBtn')?.addEventListener('click', () => $('connectAccountModal').hidden = false);
    $('closeConnectModal')?.addEventListener('click', () => $('connectAccountModal').hidden = true);
    $('cancelConnectModal')?.addEventListener('click', () => $('connectAccountModal').hidden = true);

    $('connectAccountForm')?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const provider = $('connProvider').value;
      const email_address = $('connEmail').value.trim();

      const res = await api('/api/v1/emails/accounts', {
        method: 'POST',
        body: JSON.stringify({ provider, email_address }),
      });
      if (res && res.ok) {
        showToast('Inbox connected and synchronized!');
        $('connectAccountModal').hidden = true;
        loadInboxThreads();
      }
    });

    // Calendar navigation
    $('calPrevBtn')?.addEventListener('click', () => {
      calendarDate.setMonth(calendarDate.getMonth() - 1);
      renderCalendar();
    });
    $('calNextBtn')?.addEventListener('click', () => {
      calendarDate.setMonth(calendarDate.getMonth() + 1);
      renderCalendar();
    });
    $('calTodayBtn')?.addEventListener('click', () => {
      calendarDate = new Date();
      selectedDateStr = calendarDate.toISOString().split('T')[0];
      renderCalendar();
    });

    // Search inputs
    $('globalSearch')?.addEventListener('input', (e) => {
      if (activeView === 'inbox') loadInboxThreads();
    });
    $('knowledgeSearchInput')?.addEventListener('input', loadKnowledge);

    // Profile settings
    $('settingsProfileForm')?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const disp = $('stDisplayName').value.trim();
      const tone = $('stAiTone').value;
      const res = await api('/api/v1/auth/profile', {
        method: 'PUT',
        body: JSON.stringify({ display_name: disp, preferences: { default_tone: tone } }),
      });
      if (res && res.ok) {
        const u = await res.json();
        currentUser = u;
        localStorage.setItem(USER_KEY, JSON.stringify(u));
        updateUserUI();
        showToast('Preferences updated successfully.');
      }
    });

    // Password change
    $('settingsPasswordForm')?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const current_password = $('stCurrentPass').value;
      const new_password = $('stNewPass').value;
      const res = await api('/api/v1/auth/change-password', {
        method: 'POST',
        body: JSON.stringify({ current_password, new_password }),
      });
      if (res && res.ok) {
        showToast('Password successfully changed.');
        $('settingsPasswordForm').reset();
      } else {
        const err = res ? await res.json() : { detail: 'Password change failed' };
        showToast(err.detail || 'Password change failed.', true);
      }
    });

    // Data export
    $('stExportBtn')?.addEventListener('click', async () => {
      const res = await api('/api/v1/auth/export');
      if (!res || !res.ok) return;
      const data = await res.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `inboxpilot-export-${new Date().toISOString().split('T')[0]}.json`;
      a.click();
      URL.revokeObjectURL(url);
      showToast('Personal data export downloaded.');
    });

    // Delete account
    $('stDeleteAccountBtn')?.addEventListener('click', async () => {
      if (!confirm('Are you ABSOLUTELY sure? This will permanently delete your account, connected inboxes, tasks, and notes.')) return;
      const res = await api('/api/v1/auth/me', { method: 'DELETE' });
      if (res && res.ok) {
        logout();
        showToast('Account permanently deleted.');
      }
    });

    // Focus mode toggle
    $('focusModeBtn')?.addEventListener('click', async () => {
      const res = await api('/api/v1/productivity/focus');
      if (res && res.ok) {
        const data = await res.json();
        alert(`🎯 DEEP WORK FOCUS MODE\n\n${data.recommendation}\n\nTop Objectives:\n${data.focus_items.map((it) => `• ${it.title} (Priority: ${it.priority.toUpperCase()})`).join('\n')}`);
      }
    });
  });
})();
