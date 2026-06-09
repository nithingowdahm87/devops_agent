/* ── State ──────────────────────────────────────────── */
const state = {
  token: localStorage.getItem('token') || null,
  email: localStorage.getItem('email') || null,
  projects: [],
  selectedProjectId: null,
};

/* ── API helpers ────────────────────────────────────── */
function apiFetch(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...options.headers };
  if (state.token) headers['Authorization'] = `Bearer ${state.token}`;
  return fetch(path, { ...options, headers });
}

/* ── Init ───────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  if (state.token) {
    showDashboard();
  } else {
    showAuth();
  }
});

/* ── Auth ───────────────────────────────────────────── */
function showAuth() {
  document.getElementById('header').classList.add('hidden');
  document.getElementById('auth-section').classList.remove('hidden');
  document.getElementById('dashboard-section').classList.add('hidden');
  document.getElementById('login-form').classList.remove('hidden');
  document.getElementById('register-card').classList.add('hidden');
  clearErrors();
}

function showDashboard() {
  document.getElementById('header').classList.remove('hidden');
  document.getElementById('auth-section').classList.add('hidden');
  document.getElementById('dashboard-section').classList.remove('hidden');
  document.getElementById('header-email').textContent = state.email || '';
  loadProjects();
  loadRuns();
}

function clearErrors() {
  document.querySelectorAll('.error').forEach(el => { el.textContent = ''; el.classList.add('hidden'); });
}

/* ── Login ──────────────────────────────────────────── */
document.getElementById('login-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  clearErrors();

  const username = document.getElementById('login-email').value.trim();
  const password = document.getElementById('login-password').value;

  const formData = new URLSearchParams({ username, password });

  try {
    const res = await fetch('/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formData,
    });

    if (res.ok) {
      const data = await res.json();
      state.token = data.access_token;
      state.email = username;
      localStorage.setItem('token', state.token);
      localStorage.setItem('email', state.email);
      showDashboard();
    } else {
      showError('login-error', 'Invalid credentials. Please try again.');
    }
  } catch {
    showError('login-error', 'Unable to reach the server. Is it running?');
  }
});

/* ── Register ───────────────────────────────────────── */
document.getElementById('show-register-btn').addEventListener('click', () => {
  clearErrors();
  document.getElementById('login-form').classList.add('hidden');
  document.getElementById('register-card').classList.remove('hidden');
});

document.getElementById('show-login-btn').addEventListener('click', () => {
  clearErrors();
  document.getElementById('register-card').classList.add('hidden');
  document.getElementById('login-form').classList.remove('hidden');
});

document.getElementById('register-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  clearErrors();

  const email    = document.getElementById('register-email').value.trim();
  const password = document.getElementById('register-password').value;

  try {
    const res = await fetch('/api/v1/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });

    if (res.ok) {
      // Auto-login after register
      const formData = new URLSearchParams({ username: email, password });
      const loginRes = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData,
      });
      if (loginRes.ok) {
        const data = await loginRes.json();
        state.token = data.access_token;
        state.email = email;
        localStorage.setItem('token', state.token);
        localStorage.setItem('email', state.email);
        showDashboard();
      } else {
        // Switch to login form so user can sign in manually
        showError('register-error', 'Account created. Please sign in.');
        document.getElementById('register-card').classList.add('hidden');
        document.getElementById('login-form').classList.remove('hidden');
        document.getElementById('login-email').value = email;
      }
    } else {
      const err = await res.json().catch(() => ({}));
      showError('register-error', err.detail || 'Registration failed.');
    }
  } catch {
    showError('register-error', 'Unable to reach the server.');
  }
});

/* ── Logout ─────────────────────────────────────────── */
document.getElementById('logout-btn').addEventListener('click', () => {
  state.token = null;
  state.email = null;
  state.projects = [];
  localStorage.removeItem('token');
  localStorage.removeItem('email');
  showAuth();
});

/* ── Projects ───────────────────────────────────────── */
document.getElementById('show-create-project-btn').addEventListener('click', () => {
  document.getElementById('create-project-form').classList.toggle('hidden');
  document.getElementById('create-project-error').classList.add('hidden');
});

document.getElementById('cancel-create-project-btn').addEventListener('click', () => {
  document.getElementById('create-project-form').classList.add('hidden');
  document.getElementById('project-name').value = '';
  document.getElementById('project-repo').value = '';
});

document.getElementById('create-project-btn').addEventListener('click', async () => {
  const name = document.getElementById('project-name').value.trim();
  const repo = document.getElementById('project-repo').value.trim();
  if (!name) return;

  const btn = document.getElementById('create-project-btn');
  btn.disabled = true;

  try {
    const res = await apiFetch('/api/v1/projects/', {
      method: 'POST',
      body: JSON.stringify({ name, repo_url: repo }),
    });

    if (res.ok) {
      document.getElementById('project-name').value = '';
      document.getElementById('project-repo').value = '';
      document.getElementById('create-project-form').classList.add('hidden');
      loadProjects();
    } else {
      const err = await res.json().catch(() => ({}));
      showError('create-project-error', err.detail || 'Failed to create project.');
    }
  } catch {
    showError('create-project-error', 'Network error.');
  } finally {
    btn.disabled = false;
  }
});

async function loadProjects() {
  const loading = document.getElementById('projects-loading');
  const empty   = document.getElementById('projects-empty');
  const table   = document.getElementById('projects-table');
  const tbody   = document.getElementById('projects-tbody');

  loading.classList.remove('hidden');
  empty.classList.add('hidden');
  table.classList.add('hidden');

  try {
    const res = await apiFetch('/api/v1/projects/');
    if (res.ok) {
      state.projects = await res.json();
      renderProjects();
    }
  } catch {
    // silently fail on network errors
  } finally {
    loading.classList.add('hidden');
  }
}

function renderProjects() {
  const empty = document.getElementById('projects-empty');
  const table = document.getElementById('projects-table');
  const tbody = document.getElementById('projects-tbody');

  if (!state.projects.length) {
    empty.classList.remove('hidden');
    table.classList.add('hidden');
    return;
  }

  empty.classList.add('hidden');
  table.classList.remove('hidden');
  tbody.innerHTML = '';

  state.projects.forEach(p => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${escHtml(p.name)}</td>
      <td>${escHtml(p.repo_url || '—')}</td>
      <td>
        <button class="btn btn-sm" onclick="startRun(${p.id})">Start Run</button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

/* ── Runs ───────────────────────────────────────────── */
document.getElementById('refresh-runs-btn').addEventListener('click', loadRuns);

async function loadRuns() {
  const loading = document.getElementById('runs-loading');
  const empty   = document.getElementById('runs-empty');
  const table   = document.getElementById('runs-table');
  const detail  = document.getElementById('run-detail');

  loading.classList.remove('hidden');
  empty.classList.add('hidden');
  table.classList.add('hidden');
  detail.classList.add('hidden');

  try {
    const res = await apiFetch('/api/v1/runs/');
    if (res.ok) {
      const runs = await res.json();
      renderRuns(runs);
    }
  } catch {
    // silently fail
  } finally {
    loading.classList.add('hidden');
  }
}

function renderRuns(runs) {
  const empty  = document.getElementById('runs-empty');
  const table  = document.getElementById('runs-table');
  const tbody  = document.getElementById('runs-tbody');

  if (!runs.length) {
    empty.classList.remove('hidden');
    table.classList.add('hidden');
    return;
  }

  empty.classList.add('hidden');
  table.classList.remove('hidden');
  tbody.innerHTML = '';

  runs.forEach(r => {
    const statusBadge = makeStatusBadge(r.status);
    const stageText   = r.stage || '—';
    const dateText    = r.created_at ? new Date(r.created_at).toLocaleString() : '—';
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${r.id}</td>
      <td>${escHtml(String(r.project_id))}</td>
      <td>${statusBadge}</td>
      <td>${escHtml(stageText)}</td>
      <td>${escHtml(dateText)}</td>
      <td>
        <button class="btn btn-sm" onclick="viewRunDetail(${r.id})">View</button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

async function startRun(projectId) {
  try {
    const res = await apiFetch('/api/v1/runs/', {
      method: 'POST',
      body: JSON.stringify({ project_id: projectId, config: {}, no_heal: false }),
    });
    if (res.ok) {
      loadRuns();
    } else {
      const err = await res.json().catch(() => ({}));
      alert(err.detail || 'Failed to start run.');
    }
  } catch {
    alert('Network error starting run.');
  }
}

async function viewRunDetail(runId) {
  const detail = document.getElementById('run-detail');
  detail.classList.remove('hidden');
  detail.innerHTML = '<span class="loading">Loading run details…</span>';

  try {
    const res = await apiFetch(`/api/v1/runs/${runId}`);
    if (res.ok) {
      const run = await res.json();
      const statusBadge = makeStatusBadge(run.status);
      detail.innerHTML = `
        <div class="run-detail-header" style="display:flex;align-items:center;gap:.75rem;margin-bottom:.5rem;">
          <strong>Run #${run.id}</strong>
          ${statusBadge}
          <span style="color:var(--muted);font-size:.8rem;">${run.stage || ''}</span>
        </div>
        <pre>${JSON.stringify(run, null, 2)}</pre>
      `;
    } else {
      detail.innerHTML = '<span class="error">Failed to load run details.</span>';
    }
  } catch {
    detail.innerHTML = '<span class="error">Network error.</span>';
  }
}

/* ── Utilities ──────────────────────────────────────── */
function showError(id, msg) {
  const el = document.getElementById(id);
  if (el) { el.textContent = msg; el.classList.remove('hidden'); }
}

function escHtml(str) {
  const div = document.createElement('div');
  div.textContent = str == null ? '' : String(str);
  return div.innerHTML;
}

function makeStatusBadge(status) {
  const s = (status || '').toLowerCase();
  let cls = 'badge-muted', label = status || 'unknown';
  if (s === 'success' || s === 'completed') cls = 'badge-success';
  else if (s === 'failed' || s === 'error')  cls = 'badge-error';
  else if (s === 'running' || s === 'pending') cls = 'badge-info';
  else if (s === 'warning' || s === 'healing') cls = 'badge-warning';
  return `<span class="badge ${cls}">${escHtml(label)}</span>`;
}