const messages=[{name:'PEC Events Team',initial:'PE',subject:'Venue availability — Friday',preview:'The seminar hall is available. Please confirm your booking.',priority:'HIGH',body:'Hi Alex, the seminar hall is available on Friday. Please confirm whether you would like to reserve it for your tech club event.'},{name:'NovaTech Sponsorship',initial:'NT',subject:'Sponsorship proposal follow-up',preview:'Could you share the final sponsorship deck by tomorrow?',priority:'MEDIUM',body:'Hello, our team would love to review your final sponsorship deck. Could you send it over by tomorrow?'},{name:'Volunteer Coordinator',initial:'VC',subject:'Volunteer availability for the event',preview:'Seven volunteers have confirmed their shifts so far.',priority:'LOW',body:'Quick update: seven volunteers have confirmed. We are awaiting three more responses.'}];
let tasks=[{text:'Confirm event venue booking',due:'Today',done:false},{text:'Send sponsorship deck',due:'Tomorrow',done:false},{text:'Prepare volunteer schedule',due:'Friday',done:false},{text:'Review event checklist',due:'Friday',done:true}];
const STATE_KEY = 'inboxpilot_ember_data';
const TOKEN_KEY = 'inboxpilot_token';
const SYNC_META_KEY = 'inboxpilot_sync_meta';
const API_BASE = (() => {
  const override = new URLSearchParams(location.search).get('api');
  if (override !== null) return override.replace(/\/+$/, '');
  // Served by FastAPI at /inboxpilot/ -> same origin. Opened from a separate
  // static dev server -> talk to the local FastAPI port instead.
  return location.pathname.startsWith('/inboxpilot') ? '' : 'http://127.0.0.1:8000';
})();
let authToken = '';
try { authToken = localStorage.getItem(TOKEN_KEY) || ''; } catch {}
const today = new Date();
const seedEvents = [
  {time:'10:30', name:'Club planning check-in', place:'Conference Room · 30 min', priority:'low'},
  {time:'13:00', name:'Sponsor call', place:'Online · 45 min', priority:'medium'},
  {time:'16:15', name:'Venue confirmation deadline', place:'Action needed', priority:'high'}
];
let events = seedEvents.map(event => ({...event, date:localISO(today)}));
let approvalState = 'pending';
let notes = [];
let addType = 'task';
let editingEvent = null;
let storedState;

try {
  storedState = JSON.parse(localStorage.getItem(STATE_KEY));
  if (Array.isArray(storedState?.tasks)) tasks = storedState.tasks;
  if (Array.isArray(storedState?.events)) {
    events = storedState.events.map(event => ({
      ...event,
      date: event.date || localISO(today),
      priority: event.priority || seedEvents.find(sample => sample.name === event.name)?.priority || 'medium'
    }));
  }
  if (Array.isArray(storedState?.messages)) messages.splice(0, messages.length, ...storedState.messages);
  if (Array.isArray(storedState?.notes)) notes = storedState.notes;
  if (['pending','approved','rejected'].includes(storedState?.approvalState)) approvalState = storedState.approvalState;
} catch {
  // The workspace still works in memory when browser storage is unavailable.
}

let syncTimer;
let localRevision = 0;
let pushInFlight = null;
let syncMeta = {
  dirty: false,
  owner: '',
  baseUpdatedAt: null,
  lastLocalChangeAt: null,
  lastSyncedAt: null
};
try {
  syncMeta = {...syncMeta, ...JSON.parse(localStorage.getItem(SYNC_META_KEY) || '{}')};
} catch {}
localRevision = Number(syncMeta.localRevision) || 0;

function saveSyncMeta() {
  syncMeta.localRevision = localRevision;
  try { localStorage.setItem(SYNC_META_KEY, JSON.stringify(syncMeta)); } catch {}
}

function markLocalChange() {
  localRevision += 1;
  syncMeta.dirty = true;
  syncMeta.lastLocalChangeAt = new Date().toISOString();
  saveSyncMeta();
}

function setSyncStatus(text, kind = 'ok') {
  const pill = document.getElementById('syncStatus');
  if (!pill) return;
  pill.textContent = text;
  pill.dataset.kind = kind;
}

function storeLocalState() {
  try {
    localStorage.setItem(STATE_KEY, JSON.stringify({tasks, events, messages, notes, approvalState}));
    return true;
  } catch {
    return false;
  }
}

function currentState() {
  return {tasks, events, messages, notes, approval_state: approvalState};
}

function persist() {
  const stored = storeLocalState();
  markLocalChange();
  if (!authToken) {
    setSyncStatus(
      stored ? '● Local only' : '⚠ Changes available until you close this tab',
      stored ? 'ok' : 'error'
    );
    return;
  }
  setSyncStatus('… Syncing to backend', 'ok');
  clearTimeout(syncTimer);
  syncTimer = setTimeout(() => { pushRemoteState(); }, 500);
}

async function apiFetch(path, options = {}) {
  const headers = {'Content-Type': 'application/json', ...(options.headers || {})};
  if (authToken) headers.Authorization = `Bearer ${authToken}`;
  return fetch(API_BASE + path, {...options, headers});
}

async function describeApiError(response) {
  try {
    const data = await response.json();
    if (typeof data.detail === 'string') return data.detail;
    if (Array.isArray(data.detail)) {
      return data.detail.map(item => {
        const field = Array.isArray(item.loc) ? item.loc.filter(part => part !== 'body').join('.') : '';
        return field ? `${field}: ${item.msg}` : item.msg;
      }).join('; ');
    }
  } catch {}
  return `HTTP ${response.status}`;
}

function applyRemoteWorkspace(remote) {
  applyState(remote);
  storeLocalState();
  syncMeta.baseUpdatedAt = remote?.updated_at || null;
  syncMeta.lastSyncedAt = new Date().toISOString();
  syncMeta.dirty = false;
  saveSyncMeta();
}

async function pushRemoteState() {
  if (!authToken) return false;
  if (pushInFlight) {
    try { await pushInFlight; } catch {}
    if (!authToken) return false;
  }

  const revision = localRevision;
  const snapshot = currentState();
  setSyncStatus('… Syncing to backend', 'ok');

  pushInFlight = (async () => {
    try {
      const response = await apiFetch('/api/v1/workspace', {
        method: 'PUT',
        body: JSON.stringify(snapshot),
        cache: 'no-store',
      });
      if (response.status === 401) {
        clearAuth();
        setSyncStatus('⚠ Sign in again to sync', 'error');
        return false;
      }
      if (!response.ok) {
        const detail = await describeApiError(response);
        setSyncStatus('⚠ Sync failed — ' + detail.slice(0, 120), 'error');
        return false;
      }
      const saved = await response.json().catch(() => null);
      if (saved?.updated_at) syncMeta.baseUpdatedAt = saved.updated_at;
      syncMeta.lastSyncedAt = new Date().toISOString();
      if (revision === localRevision) {
        syncMeta.dirty = false;
        storeLocalState();
        setSyncStatus('✓ Synced to backend', 'ok');
      } else {
        setSyncStatus('… Syncing newer changes', 'ok');
        clearTimeout(syncTimer);
        syncTimer = setTimeout(() => { pushRemoteState(); }, 300);
      }
      saveSyncMeta();
      return true;
    } catch {
      setSyncStatus('⚠ Backend unavailable — saved locally', 'error');
      return false;
    } finally {
      pushInFlight = null;
    }
  })();

  return pushInFlight;
}

async function pullRemoteState() {
  if (!authToken) return null;
  try {
    const response = await apiFetch('/api/v1/workspace', {cache: 'no-store'});
    if (response.status === 401) {
      clearAuth();
      setSyncStatus('⚠ Sign in again to sync', 'error');
      return null;
    }
    if (!response.ok) {
      setSyncStatus(`⚠ Could not load workspace (HTTP ${response.status})`, 'error');
      return null;
    }
    return await response.json();
  } catch {
    setSyncStatus('⚠ Backend unavailable — using local data', 'error');
    return null;
  }
}

function clearAuth() {
  authToken = '';
  try { localStorage.removeItem(TOKEN_KEY); } catch {}
  if (typeof prefs !== 'undefined') {
    prefs.demoSignedIn = false;
    savePrefs();
  }
  updateConnectionState();
  setSyncStatus('● Local only', 'ok');
}

function updateConnectionState() {
  const indicator = document.getElementById('connectionState');
  if (!indicator) return;
  indicator.textContent = authToken ? '● Backend connected' : '● Local only';
  indicator.title = authToken ? 'Workspace syncs to the FastAPI backend' : 'Sign in to sync this workspace with the backend';
}

function applyState(state) {
  if (!state || typeof state !== 'object') return;
  if (Array.isArray(state.tasks)) {
    tasks = state.tasks.map(task => ({
      ...task,
      text: String(task.text ?? ''),
      due: String(task.due ?? 'No due date'),
      done: Boolean(task.done)
    }));
  }
  if (Array.isArray(state.events)) {
    events = state.events.map(event => ({
      ...event,
      name: String(event.name ?? 'Untitled event'),
      time: String(event.time ?? ''),
      place: String(event.place ?? ''),
      date: event.date || localISO(today),
      priority: eventPriority(event)
    }));
  }
  if (Array.isArray(state.messages)) messages.splice(0, messages.length, ...state.messages);
  if (Array.isArray(state.notes)) notes = state.notes;
  if (['pending','approved','rejected'].includes(state.approval_state)) approvalState = state.approval_state;
}

function renderAll() {
  renderMail();
  renderTasks();
  renderCalendar();
  renderApproval();
  renderNotes();
}

async function syncAfterLogin() {
  const email = (prefs.email || '').toLowerCase();
  const previousOwner = syncMeta.owner;
  const switchedAccount = Boolean(previousOwner && previousOwner !== email);
  if (switchedAccount) {
    syncMeta.dirty = false;
    syncMeta.baseUpdatedAt = null;
    syncMeta.lastLocalChangeAt = null;
  }
  syncMeta.owner = email;
  saveSyncMeta();

  const remote = await pullRemoteState();
  if (!remote) {
    renderAll();
    updateConnectionState();
    return;
  }

  if (remote.updated_at) {
    const localIsNewer = Boolean(
      syncMeta.dirty &&
      syncMeta.lastLocalChangeAt &&
      new Date(syncMeta.lastLocalChangeAt) > new Date(remote.updated_at)
    );
    const uploadLocal = localIsNewer && confirm(
      'This device has unsynced workspace changes.\n\n' +
      'Upload them and replace the backend copy?\n' +
      'Choose Cancel to load the backend copy instead.'
    );
    if (uploadLocal) {
      await pushRemoteState();
    } else {
      applyRemoteWorkspace(remote);
      setSyncStatus('✓ Loaded from backend', 'ok');
    }
  } else if (switchedAccount) {
    // Never upload another account's local cache into a new account.
    applyState({tasks: [], events: [], messages: [], notes: [], approval_state: 'pending'});
    storeLocalState();
    setSyncStatus('✓ Loaded from backend', 'ok');
  } else {
    // First save for this account: upload the local workspace.
    await pushRemoteState();
  }

  renderAll();
  updateConnectionState();
}

const $=id=>document.getElementById(id);function safe(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function toast(msg){$('toast').textContent=msg;$('toast').classList.add('show');clearTimeout(window.toastTimer);window.toastTimer=setTimeout(()=>$('toast').classList.remove('show'),3200)}
let activeDialog = null;
let returnFocus = null;

function showDialog(backdrop, initialFocus, trigger = document.activeElement) {
  activeDialog = backdrop;
  returnFocus = trigger;
  document.querySelector('.app').inert = true;
  backdrop.hidden = false;
  backdrop.classList.add('show');
  initialFocus.focus();
}

function hideDialog(backdrop) {
  if (activeDialog !== backdrop) return;
  backdrop.classList.remove('show');
  if (backdrop.id === 'settingsBackdrop') backdrop.hidden = true;
  document.querySelector('.app').inert = false;
  activeDialog = null;
  returnFocus?.focus();
  returnFocus = null;
}

document.addEventListener('keydown', event => {
  if (event.key !== 'Tab' || !activeDialog) return;
  const controls = [...activeDialog.querySelectorAll('button, input, textarea, select, a[href]')]
    .filter(control => !control.disabled && control.getClientRects().length);
  const first = controls[0], last = controls.at(-1);
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last?.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first?.focus();
  }
});

function openModal(title, body) {
  $('modalTitle').textContent = title;
  $('modalText').textContent = body;
  showDialog($('modalBg'), $('closeModal'));
}

function closeModal() {
  hideDialog($('modalBg'));
}

$('closeModal').onclick = closeModal;
$('modalBg').onclick = event => {
  if (event.target === $('modalBg')) closeModal();
};
document.addEventListener('keydown', event => {
  if (event.key === 'Escape') closeModal();
});

function renderMail(){const html=messages.map((m,i)=>`<div class="inbox-row" role="button" tabindex="0" data-email="${i}"><div class="initial">${safe(m.initial)}</div><div class="mail-text"><strong>${safe(m.name)}</strong><div class="subject">${safe(m.subject)}</div><small>${safe(m.preview)}</small></div><div class="mail-side"><span>${safe(m.when || ['9:42 AM','Yesterday','Yesterday'][i] || 'New')}</span><span class="priority ${eventPriority(m)}">${safe(m.priority)}</span></div></div>`).join('');$('inboxAll').innerHTML=html;$('inboxCount').textContent=messages.length;$('messagesMetric').textContent=messages.length;$('inboxTotal').textContent=messages.length+' messages';$('highPriorityCount').textContent=messages.filter(message=>eventPriority(message)==='high').length+' high priority';document.querySelectorAll('[data-email]').forEach(el=>{const show=()=>{const m=messages[+el.dataset.email];openModal(m.subject,`${m.name}\n\n${m.body}`)};el.addEventListener('click',show);el.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();show()}})})}
function renderTasks(){const html=tasks.map((t,i)=>`<label class="task ${t.done?'done':''}"><input type="checkbox" data-task="${i}" ${t.done?'checked':''}><span>${safe(t.text)}</span><small>${safe(t.due)}</small></label>`).join('');$('tasksAll').innerHTML=html;$('workspaceTasks').innerHTML=html;$('workspaceTaskBadge').textContent=tasks.length+' items';$('tasksMetric').textContent=String(tasks.length).padStart(2,'0');document.querySelectorAll('[data-task]').forEach(input=>input.onchange=()=>{tasks[+input.dataset.task].done=input.checked;persist();renderTasks();toast(input.checked?'Task marked complete':'Task reopened')})}
function renderCalendar() {
  const upcoming = events.filter(event => event.date >= localISO(new Date())).sort(compareEvents);
  const preview = upcoming.slice(0, 4).map(renderEventSummary).join('');
  $('calendarPreview').innerHTML = preview || '<div class="empty">No upcoming events.</div>';
  $('workspaceCalendar').innerHTML = [...events].sort(compareEvents).map(renderEventSummary).join('')
    || '<div class="empty">No events yet.</div>';
  $('workspaceEventBadge').textContent = events.length + ' events';
  $('eventsMetric').textContent = upcoming.length;
  renderMonthCalendar();
}

function compareEvents(a, b) {
  return a.date.localeCompare(b.date) || (a.time || 'TBD').localeCompare(b.time || 'TBD');
}

function renderEventSummary(event) {
  return `<div class="event">
    <div class="event-time">${safe(event.time || 'All day')}</div>
    <i class="priority-dot ${eventPriority(event)}" title="${eventPriority(event)} priority"></i>
    <div><strong>${safe(event.name)}</strong><small>${safe(displayDate(event.date))}${event.place ? ' · ' + safe(event.place) : ''}</small></div>
  </div>`;
}

function renderApproval(){let html;if(approvalState==='pending'){html=`<div class="approval"><div class="approval-top"><div class="approval-icon">◇</div><div><strong>Draft reply: Venue confirmation</strong><p>InboxPilot has prepared an email. Review it before sending.</p></div></div><div class="draft"><b>To:</b> PEC Events Team<br><b>Subject:</b> Re: Venue availability — Friday<br><br>Hi team, thanks for confirming availability. We'd like to proceed with the seminar hall booking for Friday. Please share the next steps.<br><br>Best,<br>Alex</div><div class="approval-actions"><button class="primary" data-approval="approve">✓ Approve draft</button><button class="outline" data-approval="reject">Reject draft</button></div></div>`}else{html=`<div class="approval"><div class="approved">${approvalState==='approved'?'✓ Draft approved for sending (demo only).':'↺ Draft rejected. No email was sent.'}</div><div class="approval-actions"><button class="outline" data-approval="reset">Reset demo</button></div></div>`}$('workspaceApprovalContent').innerHTML=html;$('approvalPageContent').innerHTML=html;$('workspaceApprovalBadge').textContent=approvalState==='pending'?'1 pending':'0 pending';$('approvalsPageCount').textContent=approvalState==='pending'?'1 pending':'0 pending';$('navApprovalCount').textContent=approvalState==='pending'?'1':'0';$('approvalMetric').textContent=approvalState==='pending'?'01':'00';}
function switchView(id){document.querySelectorAll('.section').forEach(s=>s.classList.toggle('active',s.id===id));document.querySelectorAll('[data-view]').forEach(b=>{const active=b.dataset.view===id;b.classList.toggle('active',active);if(active)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current')});$('crumb').textContent=({dashboard:'Overview',inbox:'Inbox',workspace:'Workspace',approvals:'Approval Needed',tasks:'My Tasks',calendar:'Calendar',library:'Library',plugins:'Plugins'})[id];window.scrollTo({top:0,behavior:'smooth'})}document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>switchView(b.dataset.view));document.querySelectorAll('[data-go]').forEach(b=>b.onclick=()=>switchView(b.dataset.go));document.querySelectorAll('[data-prompt]').forEach(b=>b.onclick=()=>{$('goal').value=b.dataset.prompt;$('goal').focus()});
function stepsFor(goal){const g=goal.toLowerCase();if(/sponsor|deck|proposal/.test(g))return ['Review sponsor-related inbox threads','Identify open questions and outstanding materials','Prepare contextual follow-up draft','Request your approval before sending'];if(/meeting|volunteer|schedule/.test(g))return ['Review meeting and volunteer information','Check sample calendar for scheduling conflicts','Create a follow-up task list','Prepare reminders for your approval'];if(/venue|book|confirm/.test(g))return ['Find venue-related correspondence','Extract availability and next steps','Prepare booking confirmation draft','Ask for approval before sending'];return ['Understand your goal and identify required tools','Organize relevant sample inbox and calendar information','Plan tasks and prepare next steps','Ask for approval before any important action']}
function displayWorkflow(steps,status){const markup=steps.map((s,i)=>`<div class="step ${i===3?'pending':''}"><span class="circle">${i===3?'!':'✓'}</span><span class="step-txt">${safe(s)}</span><span class="status">${i===3?'Approval required':'Planned'}</span></div>`).join('');$('steps').innerHTML=markup;$('workflowStatus').textContent=status;if($('workflowStatusSecondary'))$('workflowStatusSecondary').textContent=status}
function runAgent() {
  const goal = $('goal').value.trim();
  if (!goal) {
    toast('Describe a goal to start');
    $('goal').focus();
    return;
  }
  if (goal.length > 500) {
    toast('Keep your goal under 500 characters');
    return;
  }
  trackDemoRequest(goal);
  displayWorkflow(stepsFor(goal), 'REVIEW READY');
  toast('Action plan ready to review');
}

$('runBtn').onclick=()=>runAgent();$('addTask').onclick=()=>openAdd('task');

function renderNotes(){const html=notes.length?notes.map(n=>`<article class="note-item"><strong>${safe(n.title)}</strong><p>${safe(n.details||'')}</p><small>${safe(n.body||'')}</small></article>`).join(''):'<div class="empty">No notes yet. Use + on Overview to add your first note.</div>';$('workspaceNotes').innerHTML=html;$('workspaceNoteBadge').textContent=notes.length+' notes'}

$('quickAdd').onclick=()=>openAdd('task');
function openAdd(type, index = null) {
  editingEvent = index;
  const editing = index !== null;
  $('addTitle').textContent = editing ? 'Edit event' : 'Add to InboxPilot';
  $('addSubmit').textContent = editing ? 'Save changes' : 'Add to workspace';
  $('addTypes').hidden = editing;
  selectAddType(type);
  if (editing) {
    const event = events[index];
    $('newTitle').value = event.name;
    $('newDetails').value = event.place || '';
    $('eventDate').value = event.date;
    $('eventTime').value = /^\d{2}:\d{2}$/.test(event.time) ? event.time : '';
    $('eventPriority').value = eventPriority(event);
  }
  showDialog($('addBackdrop'), $('newTitle'));
}

function closeAdd() {
  if (activeDialog !== $('addBackdrop')) return;
  hideDialog($('addBackdrop'));
  $('addForm').reset();
  editingEvent = null;
}

$('closeAdd').onclick = $('cancelAdd').onclick = closeAdd;
$('addBackdrop').onclick = event => {
  if (event.target === $('addBackdrop')) closeAdd();
};
document.addEventListener('keydown', event => {
  if (event.key === 'Escape') closeAdd();
});

function selectAddType(type) {
  addType = type;
  document.querySelectorAll('[data-addtype]').forEach(button => {
    const selected = button.dataset.addtype === type;
    button.classList.toggle('selected', selected);
    button.setAttribute('aria-pressed', selected);
  });
  const labels = {
    task: ['Task name', 'Due date / details', 'e.g. Confirm event venue', 'e.g. Tomorrow'],
    event: ['Event name', 'Location / details', 'e.g. Sponsor call', 'e.g. Conference Room'],
    note: ['Note title', 'Category / source', 'e.g. Sponsorship summary', 'e.g. Email / Tech Fest'],
    inbox: ['Email subject', 'Sender name', 'e.g. Final sponsor confirmation', 'e.g. NovaTech Team']
  };
  const [title, details, titlePlaceholder, detailsPlaceholder] = labels[type];
  $('newTitleLabel').textContent = title;
  $('newDetailsLabel').textContent = details;
  $('newTitle').placeholder = titlePlaceholder;
  $('newDetails').placeholder = detailsPlaceholder;
  $('eventFields').hidden = type !== 'event';
  $('eventDate').required = type === 'event';
  if (type === 'event' && !$('eventDate').value) {
    $('eventDate').value = $('calendar').classList.contains('active') ? selectedDateISO : localISO(new Date());
  }
  $('newBody').hidden = $('newBodyLabel').hidden = !['note','inbox'].includes(type);
  $('newBodyLabel').textContent = type === 'inbox' ? 'Message body' : 'Note details';
}
document.querySelectorAll('[data-addtype]').forEach(button => {
  button.onclick = () => selectAddType(button.dataset.addtype);
});

$('addForm').onsubmit = event => {
  event.preventDefault();
  const title = $('newTitle').value.trim();
  const details = $('newDetails').value.trim();
  const body = $('newBody').value.trim();
  if (!title) {
    $('newTitle').focus();
    return;
  }
  const editing = editingEvent !== null;
  if (addType === 'task') {
    tasks.unshift({text:title, due:details || 'No due date', done:false});
    renderTasks();
  } else if (addType === 'event') {
    const date = $('eventDate').value;
    const entry = {name:title, time:$('eventTime').value, place:details, date, priority:$('eventPriority').value};
    if (editing) events[editingEvent] = entry;
    else events.push(entry);
    selectCalendarDate(date);
    renderCalendar();
  } else if (addType === 'note') {
    notes.unshift({title, details, body});
    renderNotes();
  } else {
    const sender = details || 'New sender';
    messages.unshift({name:sender, initial:sender.slice(0,2).toUpperCase(), subject:title,
      preview:body.slice(0,100) || 'New demo inbox item', priority:'MEDIUM', body:body || title, when:'Just now'});
    renderMail();
  }
  persist();
  closeAdd();
  if (editing) $('calendarAddEvent').focus();
  toast(editing ? 'Event updated' : 'Added to ' + ({task:'Tasks',event:'Calendar',note:'Workspace notes',inbox:'Inbox'}[addType]));
};

document.addEventListener('click',e=>{if(e.target.closest('[data-approval=approve]')){approvalState='approved';persist();renderApproval();toast('Approved for sending — demo only, no email sent')}else if(e.target.closest('[data-approval=reject]')){approvalState='rejected';persist();renderApproval();toast('Draft rejected; nothing was sent')}else if(e.target.closest('[data-approval=reset]')){approvalState='pending';persist();renderApproval();toast('Demo approval reset')}});

$('today').textContent = new Intl.DateTimeFormat('en-IN',{weekday:'short',day:'numeric',month:'short',year:'numeric'}).format(today);

// Keyboard shortcut for the planner.
document.addEventListener('keydown',event=>{
  if((event.ctrlKey||event.metaKey)&&event.key==='Enter'&&document.activeElement===$('goal')){event.preventDefault();runAgent();}
});



// InboxPilot V5.1 sidebar state and planned plugin directory
const inboxpilotApp=document.querySelector('.app');
const collapseButton=$('sidebarToggle');
function updateSidebar(collapsed){
  inboxpilotApp.classList.toggle('sidebar-collapsed',collapsed);
  collapseButton.setAttribute('aria-expanded',String(!collapsed));
  collapseButton.setAttribute('aria-label',collapsed?'Expand sidebar':'Collapse sidebar');
  collapseButton.title=collapsed?'Expand sidebar':'Collapse sidebar';
  try{localStorage.setItem('inboxpilot_sidebar_collapsed',String(collapsed))}catch(e){}
}
try{updateSidebar(localStorage.getItem('inboxpilot_sidebar_collapsed')==='true')}catch(e){updateSidebar(false)}
collapseButton.addEventListener('click',()=>updateSidebar(!inboxpilotApp.classList.contains('sidebar-collapsed')));
$('mobileSidebarToggle').addEventListener('click',()=>updateSidebar(!inboxpilotApp.classList.contains('sidebar-collapsed')));

const inboxpilotPlugins=[
 {id:'gmail',icon:'✉',color:'#C84A45',name:'Gmail',category:'Communication',description:'Read important messages, summarize threads and prepare reply drafts.',details:'Planned: OAuth sign-in, Gmail API read access, priority classification and draft creation. Sending messages must always require your approval.'},
 {id:'calendar',icon:'31',color:'#377DCE',name:'Google Calendar',category:'Productivity',description:'Find free time, schedule meetings and track deadlines.',details:'Planned: Google Calendar OAuth, event listing, conflict checking and event creation after user confirmation.'},
 {id:'openai',icon:'✳',color:'#277E6E',name:'OpenAI',category:'AI models',description:'Understand goals, plan tasks and prepare suggested actions.',details:'Planned: call OpenAI models securely from a FastAPI backend. API credentials must stay server-side; responses are subject to human approval before consequential actions.'},
 {id:'gemini',icon:'✦',color:'#8C63D5',name:'Google Gemini',category:'AI models',description:'An additional AI model for summaries, reasoning and drafting.',details:'Planned: Gemini API integration as an alternate model provider. Keys belong on the backend, not in browser JavaScript.'},
 {id:'voice',icon:'♫',color:'#D26D34',name:'AI Voice',category:'Accessibility',description:'Give InboxPilot requests by voice and hear spoken responses.',details:'Planned: speech-to-text and text-to-speech integration with microphone permission and clear privacy controls.'},
 {id:'agents',icon:'⟳',color:'#C24E78',name:'Agents SDK',category:'Automation',description:'Split a goal into steps and coordinate tool-based workflows.',details:'Planned: agent orchestration with clear execution logs, scoped tool access and approval gates. Existing workflow planning on this site is still simulated.'},
 {id:'supabase',icon:'▤',color:'#269B6C',name:'Supabase',category:'Data & memory',description:'Keep tasks, notes and searchable knowledge in a database.',details:'Planned: PostgreSQL persistence and pgvector-based semantic search through Supabase. This prototype saves the workspace in your browser.'},
 {id:'reportlab',icon:'▣',color:'#A66B38',name:'PDF Reports',category:'Documents',description:'Turn meeting notes and task summaries into PDF files.',details:'Planned: ReportLab PDF export. The current prototype does not generate PDF files.'}
];
function renderPlugins(query=''){
  const filtered=inboxpilotPlugins.filter(p=>(p.name+' '+p.category+' '+p.description).toLowerCase().includes(query.trim().toLowerCase()));
  $('pluginGrid').innerHTML=filtered.length?filtered.map(p=>`<article class="plugin-card"><div class="plugin-head"><div class="plugin-icon" style="--icon-color:${p.color}" aria-hidden="true">${safe(p.icon)}</div><span class="plugin-pill">PLANNED</span></div><div class="plugin-category">${safe(p.category)}</div><h4>${safe(p.name)}</h4><p>${safe(p.description)}</p><button type="button" class="plugin-details-btn" data-plugin="${safe(p.id)}" aria-label="View ${safe(p.name)} integration details">View details →</button></article>`).join(''):'<div class="plugin-empty">No plugins match your search.</div>';
}
$('pluginSearch').addEventListener('input',e=>renderPlugins(e.target.value));
$('pluginGrid').addEventListener('click',e=>{const button=e.target.closest('[data-plugin]');if(!button)return;const plugin=inboxpilotPlugins.find(x=>x.id===button.dataset.plugin);if(plugin)openModal(plugin.name+' · Planned integration',plugin.details);});
renderPlugins();



const PREF_KEY = 'inboxpilot_ui_prefs_v1';
const backgrounds = [['midnight','Midnight'], ['ocean','Ocean'], ['forest','Forest'], ['violet','Violet']];
const plans = {
  starter: {name:'Starter', limit:5000, detail:'5,000 estimated demo tokens'},
  plus: {name:'Plus', limit:25000, detail:'25,000 estimated demo tokens'}
};
const demoPrefsDefault = {
  theme:'dark', background:'midnight', name:'Guest', demoSignedIn:false, email:'',
  plan:'starter', lockScreen:false, estimatedTokens:0, planRequests:0
};
let prefs = {...demoPrefsDefault};
try {
  prefs = {...prefs, ...JSON.parse(localStorage.getItem(PREF_KEY))};
} catch {
  // Default settings remain usable without storage.
}
if (!['dark','light'].includes(prefs.theme)) prefs.theme = 'dark';
if (!backgrounds.some(([id]) => id === prefs.background)) prefs.background = 'midnight';
if (!Object.hasOwn(plans, prefs.plan)) prefs.plan = 'starter';

function savePrefs() {
  try {
    localStorage.setItem(PREF_KEY, JSON.stringify(prefs));
  } catch {
    toast('Settings will reset when this tab closes');
  }
}

function applyTheme() {
  const root = document.documentElement;
  root.dataset.theme = prefs.theme;
  root.dataset.background = prefs.background;
  const dark = prefs.theme === 'dark';
  const shortcut = $('themeShortcut');
  shortcut.textContent = dark ? '☀' : '☾';
  shortcut.title = dark ? 'Switch to light mode' : 'Switch to dark mode';
  shortcut.setAttribute('aria-label', shortcut.title);
  document.querySelector('meta[name=theme-color]').content = getComputedStyle(root).getPropertyValue('--bg').trim();

  const name = prefs.demoSignedIn ? prefs.name : 'Guest';
  $('menuProfileName').textContent = name;
  $('menuProfileMeta').textContent = prefs.demoSignedIn ? (prefs.email || 'Synced account') : 'Not signed in';
  $('profileButton').textContent = prefs.demoSignedIn
    ? name.split(/\s+/).slice(0,2).map(word => word[0]).join('').toUpperCase()
    : 'IP';
  $('dashboardHeading').textContent = prefs.demoSignedIn ? `Welcome, ${name}` : 'Workspace overview';
  updateConnectionState();
}

function changeAppearance(key, value) {
  prefs[key] = value;
  savePrefs();
  applyTheme();
}

$('themeShortcut').onclick = () => changeAppearance('theme', prefs.theme === 'dark' ? 'light' : 'dark');
const profileMenu = $('profileMenu'), profileButton = $('profileButton');

function closeProfile() {
  profileMenu.hidden = true;
  profileButton.setAttribute('aria-expanded', 'false');
}
profileButton.onclick = () => {
  const open = profileMenu.hidden;
  profileMenu.hidden = !open;
  profileButton.setAttribute('aria-expanded', open);
  if (open) profileMenu.querySelector('button').focus();
};
document.addEventListener('click', event => {
  if (!event.target.closest('.profile-wrap')) closeProfile();
});
document.addEventListener('focusin', event => {
  if (!profileMenu.hidden && !event.target.closest('.profile-wrap')) closeProfile();
});

function openSettings(tab) {
  closeProfile();
  showSettingsTab(tab);
  showDialog($('settingsBackdrop'), document.querySelector(`[data-tab="${tab}"]`), profileButton);
}
function closeSettings() {
  hideDialog($('settingsBackdrop'));
}
$('closeSettings').onclick = closeSettings;
$('settingsBackdrop').onclick = event => {
  if (event.target === $('settingsBackdrop')) closeSettings();
};
document.addEventListener('keydown', event => {
  if (event.key !== 'Escape') return;
  if (!profileMenu.hidden) {
    closeProfile();
    profileButton.focus();
  }
  closeSettings();
});
document.querySelectorAll('[data-settings]').forEach(button => {
  button.onclick = () => openSettings(button.dataset.settings);
});
document.querySelectorAll('[data-tab]').forEach(button => {
  button.onclick = () => showSettingsTab(button.dataset.tab);
});

function showSettingsTab(tab) {
  document.querySelectorAll('[data-tab]').forEach(button => {
    const selected = button.dataset.tab === tab;
    button.classList.toggle('selected', selected);
    button.setAttribute('aria-pressed', selected);
  });
  const content = $('settingsContent');
  const plan = plans[prefs.plan];
  const used = Number(prefs.estimatedTokens) || 0;
  const requests = Number(prefs.planRequests) || 0;

  if (tab === 'account') {
    const signedIn = Boolean(authToken);
    content.innerHTML = `<div class="settings-group">
      <h3>${signedIn ? 'Backend account' : 'Connect to the backend'}</h3>
      <p>${signedIn
        ? `Signed in${prefs.email ? ' as ' + safe(prefs.email) : ''}. Tasks, events, notes, inbox items and approvals sync to the integrated backend.`
        : 'Sign in or create an account to sync this workspace with the integrated backend. Without an account, changes are cached on this device only.'}</p>
      ${signedIn ? `
        <label class="add-label" for="profileNameInput">Display name</label>
        <input class="add-field" id="profileNameInput" maxlength="35" placeholder="Your name" value="${safe(prefs.name === 'Guest' ? '' : prefs.name)}">
        <button class="primary" type="button" id="saveDisplayName">Save display name</button>
        <button class="outline" type="button" id="syncNow">Sync now</button>
        <button class="outline" type="button" id="demoLogout">Sign out</button>
      ` : `
        <form id="profileForm">
          <label class="add-label" for="loginEmail">Email</label>
          <input class="add-field" id="loginEmail" type="email" autocomplete="username" placeholder="you@example.com" required value="${safe(prefs.email || '')}">
          <label class="add-label" for="loginPassword">Password</label>
          <input class="add-field" id="loginPassword" type="password" autocomplete="current-password" placeholder="At least 1 character" required>
          <label class="add-label" for="profileNameInput">Display name (optional)</label>
          <input class="add-field" id="profileNameInput" maxlength="35" placeholder="Your name" value="${safe(prefs.name === 'Guest' ? '' : prefs.name)}">
          <button class="primary" type="submit">Connect to backend</button>
        </form>
      `}</div>`;
    if (signedIn) {
      $('saveDisplayName').onclick = () => {
        const name = $('profileNameInput').value.trim();
        if (!name) {
          $('profileNameInput').focus();
          return;
        }
        prefs.name = name;
        savePrefs();
        applyTheme();
        toast('Display name saved');
      };
      $('syncNow').onclick = async () => {
        $('syncNow').disabled = true;
        const ok = await pushRemoteState();
        $('syncNow').disabled = false;
        toast(ok ? 'Workspace synced to backend' : 'Sync failed — check the sync status');
      };
      $('demoLogout').onclick = () => {
        clearAuth();
        applyTheme();
        showSettingsTab(tab);
        toast('Signed out; workspace remains cached on this device');
      };
    } else {
      $('profileForm').onsubmit = async event => {
        event.preventDefault();
        const email = $('loginEmail').value.trim();
        const password = $('loginPassword').value;
        const name = $('profileNameInput').value.trim();
        if (!email || !password) return;
        const submit = event.submitter;
        if (submit) submit.disabled = true;
        try {
          const response = await fetch(API_BASE + '/api/v1/auth/token', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({email, password}),
          });
          const data = await response.json().catch(() => ({}));
          if (!response.ok) throw new Error(data.detail || 'Sign-in failed');
          authToken = data.access_token;
          try { localStorage.setItem(TOKEN_KEY, authToken); } catch {}
          prefs.email = email.toLowerCase();
          prefs.demoSignedIn = true;
          if (name) prefs.name = name;
          else if (!prefs.name || prefs.name === 'Guest') prefs.name = prefs.email.split('@')[0];
          savePrefs();
          await syncAfterLogin();
          applyTheme();
          showSettingsTab(tab);
          toast('Connected to the backend');
        } catch (error) {
          toast(error.message || 'Could not connect to the backend');
        } finally {
          if (submit) submit.disabled = false;
        }
      };
    }
  } else if (tab === 'appearance') {
    content.innerHTML = `<div class="settings-group">
      <h3>Color mode</h3>
      <div class="choice-row">${[['dark','☾ Dark'],['light','☀ Light']].map(([id,label]) =>
        `<button class="choice ${prefs.theme === id ? 'selected' : ''}" data-mode="${id}" aria-pressed="${prefs.theme === id}">${label}</button>`).join('')}</div>
      <h3>Background theme</h3><p>Choose a palette for your workspace.</p>
      <div class="background-choices">${backgrounds.map(([id,name]) =>
        `<button class="bg-choice ${prefs.background === id ? 'selected' : ''}" data-bg="${id}" aria-pressed="${prefs.background === id}"><span class="bg-swatch swatch-${id}"></span>${name}</button>`).join('')}</div>
      </div>`;
    for (const [attribute, key] of [['mode','theme'], ['bg','background']]) {
      content.querySelectorAll(`[data-${attribute}]`).forEach(button => {
        button.onclick = () => {
          const value = button.dataset[attribute];
          changeAppearance(key, value);
          showSettingsTab(tab);
          content.querySelector(`[data-${attribute}="${value}"]`).focus();
        };
      });
    }
  } else if (tab === 'usage') {
    content.innerHTML = `<div class="settings-group">
      <h3>Token usage</h3><p>Browser estimates for the demo planner.</p>
      <div class="usage-stats"><div><small>Estimated tokens</small><strong>${used.toLocaleString()}</strong></div>
      <div><small>Planning requests</small><strong>${requests.toLocaleString()}</strong></div></div>
      <label class="setting-hint" for="tokenBudget">${plan.name} demo budget · ${used.toLocaleString()} / ${plan.limit.toLocaleString()} tokens</label>
      <progress id="tokenBudget" value="${Math.min(used,plan.limit)}" max="${plan.limit}"></progress>
      <p>Each estimate includes the prompt and an allowance for the planned response.</p>
      <button class="outline" id="clearUsage" type="button">Reset local estimates</button></div>`;
    $('clearUsage').onclick = () => {
      prefs.estimatedTokens = 0;
      prefs.planRequests = 0;
      savePrefs();
      showSettingsTab(tab);
      $('clearUsage').focus();
    };
  } else if (tab === 'subscription') {
    content.innerHTML = `<div class="settings-group"><h3>Demo subscription</h3>
      <p>Switch plans to try a different token budget. Both demo plans are free.</p>
      <div class="plan-options">${Object.entries(plans).map(([id, option]) =>
        `<button class="plan-status ${prefs.plan === id ? 'selected' : ''}" type="button" data-plan="${id}" aria-pressed="${prefs.plan === id}">
          <strong>${option.name}</strong><small>${option.detail}</small><span>${prefs.plan === id ? 'Current plan' : 'Select plan'}</span>
        </button>`).join('')}</div></div>`;
    content.querySelectorAll('[data-plan]').forEach(button => {
      button.onclick = () => {
        prefs.plan = button.dataset.plan;
        savePrefs();
        showSettingsTab(tab);
        content.querySelector(`[data-plan="${prefs.plan}"]`).focus();
        toast(`${plans[prefs.plan].name} demo plan selected`);
      };
    });
  } else {
    content.innerHTML = `<div class="settings-group"><h3>Privacy &amp; security</h3>
      <p>When you're signed in, your profile and workspace sync to the backend. Library files stay on this device.</p>
      <label class="settings-switch"><span><strong>Hide workspace when you leave this tab</strong>
      <small>Show the privacy screen when you switch tabs. Click Show workspace to resume.</small></span>
      <input id="privacyToggle" type="checkbox" ${prefs.lockScreen ? 'checked' : ''}></label>
      <button id="hideWorkspace" class="outline" type="button">Hide workspace now</button>
      <button id="clearUIPreferences" class="outline" type="button">Reset demo settings</button>
      <button id="clearLibrary" class="outline danger-button" type="button">Delete all library files</button></div>`;
    $('privacyToggle').onchange = event => {
      prefs.lockScreen = event.target.checked;
      savePrefs();
    };
    $('hideWorkspace').onclick = showPrivacyScreen;
    $('clearUIPreferences').onclick = () => {
      if (!confirm('Reset the theme, profile, plan, and local usage estimates?')) return;
      prefs = {...demoPrefsDefault};
      savePrefs();
      applyTheme();
      showSettingsTab(tab);
      $('clearUIPreferences').focus();
    };
    $('clearLibrary').onclick = async () => {
      if (!confirm('Delete all files from this device library?')) return;
      try {
        await deleteAllLibraryFiles();
        toast('Library cleared');
      } catch {
        toast('Could not clear the local library');
      }
    };
  }
}

function trackDemoRequest(goal) {
  const estimate = Math.ceil(goal.length / 4) + 80;
  const total = (Number(prefs.estimatedTokens) || 0) + estimate;
  prefs.planRequests = (Number(prefs.planRequests) || 0) + 1;
  prefs.estimatedTokens = total;
  savePrefs();
}

function showPrivacyScreen() {
  if (activeDialog === $('privacyScreen')) return;
  if (activeDialog === $('addBackdrop')) closeAdd();
  if (activeDialog === $('modalBg')) closeModal();
  closeSettings();
  closeProfile();
  showDialog($('privacyScreen'), $('revealWorkspace'), profileButton);
}
$('revealWorkspace').onclick = () => {
  hideDialog($('privacyScreen'));
  $('privacyScreen').hidden = true;
};
document.addEventListener('visibilitychange', () => {
  if (prefs.lockScreen && document.hidden) showPrivacyScreen();
});
applyTheme();


function localISO(date) {
  const year = String(date.getFullYear()).padStart(4, '0');
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}
let selectedDateISO = localISO(today);
let viewMonth = new Date(today.getFullYear(), today.getMonth(), 1);

function parseDate(iso) {
  const [year, month, day] = iso.split('-').map(Number);
  return new Date(year, month - 1, day);
}
function eventPriority(event) {
  const priority = String(event.priority).toLowerCase();
  return ['high','medium','low'].includes(priority) ? priority : 'medium';
}
function displayDate(iso) {
  return parseDate(iso).toLocaleDateString('en-IN', {weekday:'long', day:'numeric', month:'long'});
}
function selectCalendarDate(date) {
  selectedDateISO = date;
  viewMonth = parseDate(date);
  viewMonth.setDate(1);
}

function renderMonthCalendar() {
  $('monthTitle').textContent = viewMonth.toLocaleDateString('en-IN', {month:'long', year:'numeric'});
  const year = viewMonth.getFullYear(), month = viewMonth.getMonth();
  const todayISO = localISO(new Date());
  const length = new Date(year, month + 1, 0).getDate();
  const prioritiesByDate = new Map();
  for (const event of events) {
    if (!prioritiesByDate.has(event.date)) prioritiesByDate.set(event.date, []);
    prioritiesByDate.get(event.date).push(eventPriority(event));
  }
  let output = '<div class="cal-spacer" aria-hidden="true"></div>'.repeat(viewMonth.getDay());
  for (let day = 1; day <= length; day++) {
    const iso = localISO(new Date(year, month, day));
    const priorities = prioritiesByDate.get(iso) || [];
    const dots = ['high','medium','low'].filter(priority => priorities.includes(priority));
    const current = iso === todayISO;
    const selected = iso === selectedDateISO;
    const label = `${displayDate(iso)}, ${priorities.length} ${priorities.length === 1 ? 'event' : 'events'}${dots.length ? ', ' + dots.join(', ') + ' priority' : ''}`;
    output += `<button class="cal-day ${current ? 'is-today' : ''} ${selected ? 'is-selected' : ''}"
      type="button" data-day="${iso}" aria-label="${safe(label)}" aria-pressed="${selected}" ${current ? 'aria-current="date"' : ''}>
      <span>${day}</span><span class="day-dots" aria-hidden="true">${dots.map(priority =>
        `<i class="priority-dot ${priority}"></i>`).join('')}</span></button>`;
  }
  $('monthGrid').innerHTML = output;
  renderSelectedDay();
}

function renderSelectedDay() {
  $('selectedDateTitle').textContent = displayDate(selectedDateISO);
  const chosen = events.map((event,index) => ({...event,index}))
    .filter(event => event.date === selectedDateISO).sort(compareEvents);
  $('selectedDayCount').textContent = `${chosen.length} event${chosen.length === 1 ? '' : 's'}`;
  $('selectedDayEvents').innerHTML = chosen.length ? chosen.map(event => {
    const priority = eventPriority(event);
    const details = [event.time || 'All day', event.place, priority + ' priority'].filter(Boolean).join(' · ');
    return `<div class="day-event"><i class="priority-dot ${priority}"></i>
      <div><strong>${safe(event.name)}</strong><small>${safe(details)}</small></div>
      <button type="button" class="event-action" aria-label="Edit ${safe(event.name)}" data-edit-event="${event.index}">Edit</button>
      <button type="button" class="event-remove" title="Delete event" aria-label="Delete ${safe(event.name)}" data-remove-event="${event.index}">×</button>
      </div>`;
  }).join('') : '<div class="empty">Nothing scheduled for this date.</div>';
}

$('monthGrid').addEventListener('click', event => {
  const button = event.target.closest('[data-day]');
  if (!button) return;
  selectCalendarDate(button.dataset.day);
  renderMonthCalendar();
  $('monthGrid').querySelector('[aria-pressed=true]').focus();
});
function changeMonth(offset) {
  const year = viewMonth.getFullYear(), month = viewMonth.getMonth() + offset;
  const day = Math.min(parseDate(selectedDateISO).getDate(), new Date(year, month + 1, 0).getDate());
  selectCalendarDate(localISO(new Date(year, month, day)));
  renderMonthCalendar();
}
$('calPrev').onclick = () => changeMonth(-1);
$('calNext').onclick = () => changeMonth(1);
$('calToday').onclick = () => {
  selectCalendarDate(localISO(new Date()));
  renderMonthCalendar();
};
$('calendarAddEvent').onclick = () => openAdd('event');
$('selectedDayEvents').addEventListener('click', event => {
  const edit = event.target.closest('[data-edit-event]');
  if (edit) {
    openAdd('event', Number(edit.dataset.editEvent));
    return;
  }
  const remove = event.target.closest('[data-remove-event]');
  if (!remove || !confirm('Delete this event?')) return;
  events.splice(Number(remove.dataset.removeEvent), 1);
  renderCalendar();
  persist();
  $('calendarAddEvent').focus();
  toast('Event deleted');
});

const LIB_DB = 'inboxpilot_library_v1', LIB_STORE = 'files';
let libDbPromise;
let libraryFilter = '';
let libraryRenderVersion = 0;

function dbOpen() {
  if (!libDbPromise) {
    libDbPromise = new Promise((resolve,reject) => {
      const request = indexedDB.open(LIB_DB,1);
      request.onupgradeneeded = () => request.result.createObjectStore(LIB_STORE,{keyPath:'id'});
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    }).catch(error => {
      libDbPromise = undefined;
      throw error;
    });
  }
  return libDbPromise;
}

async function libraryTx(mode, operation) {
  const database = await dbOpen();
  return new Promise((resolve,reject) => {
    const transaction = database.transaction(LIB_STORE,mode);
    const request = operation(transaction.objectStore(LIB_STORE));
    transaction.oncomplete = () => resolve(request.result);
    transaction.onabort = () => reject(transaction.error);
  });
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1048576).toFixed(1)} MB`;
}

async function renderLibrary() {
  const version = ++libraryRenderVersion;
  try {
    const files = await libraryTx('readonly', store => store.getAll());
    if (version !== libraryRenderVersion) return;
    files.sort((a,b) => b.created - a.created);
    $('libraryCount').textContent = files.length;
    $('libraryStorage').textContent = formatBytes(files.reduce((total,file) => total + file.size,0)) + ' stored on this device';
    const filtered = files.filter(file => file.name.toLowerCase().includes(libraryFilter));
    $('libraryFiles').innerHTML = filtered.length ? filtered.map(file => {
      const extension = file.name.includes('.') ? file.name.split('.').pop().toUpperCase().slice(0,4) : 'FILE';
      return `<div class="library-file"><div class="file-type">${safe(extension)}</div>
        <div class="file-info"><strong>${safe(file.name)}</strong><small>${formatBytes(file.size)} · ${new Date(file.created).toLocaleDateString('en-IN')}</small></div>
        <button type="button" class="outline" data-download="${safe(file.id)}" aria-label="Download ${safe(file.name)}">↓</button>
        <button type="button" class="outline danger-button" data-delete-file="${safe(file.id)}" aria-label="Delete ${safe(file.name)}">×</button>
        </div>`;
    }).join('') : `<div class="empty">${libraryFilter ? 'No files match your search.' : 'No files yet. Upload a PDF or another file to get started.'}</div>`;
  } catch {
    if (version === libraryRenderVersion) $('libraryFiles').textContent = 'Browser file storage is unavailable.';
  }
}

async function storeLibraryFiles(files) {
  if (!files.length) return;
  const valid = files.filter(file => file.size <= 50 * 1024 * 1024);
  let saved = 0;
  for (const file of valid) {
    try {
      await libraryTx('readwrite', store => store.put({
        id: crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`,
        name:file.name, size:file.size, type:file.type, created:Date.now(), blob:file
      }));
      saved++;
    } catch {
      break;
    }
  }
  await renderLibrary();
  const messages = [];
  if (saved) messages.push(`${saved} file${saved === 1 ? '' : 's'} saved`);
  if (files.length > valid.length) messages.push(`${files.length - valid.length} over 50 MB`);
  if (valid.length > saved) messages.push('Browser storage could not save every file');
  toast(messages.join(' · '));
}

async function deleteAllLibraryFiles() {
  await libraryTx('readwrite', store => store.clear());
  await renderLibrary();
}

$('uploadFiles').onclick = () => $('fileInput').click();
$('fileInput').onchange = event => {
  const files = [...event.target.files];
  event.target.value = '';
  storeLibraryFiles(files);
};
$('librarySearch').oninput = event => {
  libraryFilter = event.target.value.trim().toLowerCase();
  renderLibrary();
};
const dropzone = $('libraryDropzone');
dropzone.onclick = () => $('fileInput').click();
for (const name of ['dragenter','dragover']) dropzone.addEventListener(name, event => {
  event.preventDefault();
  dropzone.classList.add('dragging');
});
for (const name of ['dragleave','drop']) dropzone.addEventListener(name, event => {
  event.preventDefault();
  dropzone.classList.remove('dragging');
});
dropzone.addEventListener('drop', event => storeLibraryFiles([...event.dataTransfer.files]));
$('libraryFiles').addEventListener('click', async event => {
  const download = event.target.closest('[data-download]');
  const remove = event.target.closest('[data-delete-file]');
  try {
    if (download) {
      const file = await libraryTx('readonly', store => store.get(download.dataset.download));
      if (!file) return;
      const url = URL.createObjectURL(file.blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = file.name;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url),1000);
    } else if (remove && confirm('Remove this file from the library?')) {
      await libraryTx('readwrite', store => store.delete(remove.dataset.deleteFile));
      await renderLibrary();
      $('uploadFiles').focus();
      toast('File deleted');
    }
  } catch {
    toast('Could not complete the file action');
  }
});

async function bootstrap() {
  if (authToken) {
    if (syncMeta.dirty) {
      // Local edits that never reached the backend must not be overwritten by
      // an older remote copy when the page reloads.
      const ok = await pushRemoteState();
      if (!ok && authToken) setSyncStatus('⚠ Unsynced changes saved locally', 'error');
    } else {
      const remote = await pullRemoteState();
      if (!authToken) {
        setSyncStatus('⚠ Sign in again to sync', 'error');
      } else if (remote && remote.updated_at) {
        applyRemoteWorkspace(remote);
        setSyncStatus('✓ Loaded from backend', 'ok');
      } else if (remote) {
        // First save for this account: upload the local workspace.
        await pushRemoteState();
      } else {
        setSyncStatus('⚠ Saved locally — backend unavailable', 'error');
      }
    }
  } else {
    setSyncStatus('● Local only', 'ok');
  }
  if (!storedState || storedState.events?.some?.(event => !event.date || !event.priority)) storeLocalState();
  renderAll();
  renderLibrary();
  updateConnectionState();
}

bootstrap();
