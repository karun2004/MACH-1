/* ═══════════════════════════════════════════
   MACH-1 Dashboard — Client JS
   ═══════════════════════════════════════════ */

// ── Toast Notifications ─────────────────

function showToast(message, type = 'info') {
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    const icon = type === 'success' ? '✓' : type === 'error' ? '✗' : 'ℹ';
    toast.innerHTML = `<span>${icon}</span><span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        toast.style.transition = 'all 200ms ease';
        setTimeout(() => toast.remove(), 200);
    }, 3000);
}

// ── API Helper ──────────────────────────

async function apiCall(url, method = 'POST', data = null) {
    const btn = event?.target?.closest('.btn');
    const origText = btn ? btn.innerHTML : '';
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span> Working...';
    }

    try {
        const opts = { method };
        if (data) {
            opts.headers = { 'Content-Type': 'application/json' };
            opts.body = JSON.stringify(data);
        }

        const resp = await fetch(url, opts);
        const text = await resp.text();

        let result;
        try {
            result = JSON.parse(text);
        } catch (e) {
            showToast(`Server error (${resp.status})`, 'error');
            return { success: false };
        }

        if (result.success) {
            showToast(result.result || 'Done!', 'success');
        } else {
            showToast(result.error || result.result || 'Failed', 'error');
        }
        return result;
    } catch (e) {
        showToast(`Error: ${e.message}`, 'error');
        return { success: false };
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = origText;
        }
    }
}

// ── Action Buttons ──────────────────────

async function createPlan() {
    const result = await apiCall('/api/plans/create');
    if (result.success) setTimeout(() => location.reload(), 1000);
}

async function approvePlan(id) {
    await apiCall(`/api/plans/${id}/approve`);
    setTimeout(() => location.reload(), 500);
}

async function rejectPlan(id) {
    await apiCall(`/api/plans/${id}/reject`);
    setTimeout(() => location.reload(), 500);
}

async function executePlan(id) {
    showToast('Executing plan — this may take a while...', 'info');
    const result = await apiCall(`/api/plans/${id}/execute`);
    if (result.success) setTimeout(() => location.reload(), 1000);
}

async function approveContent(id) {
    await apiCall(`/api/content/${id}/approve`);
    setTimeout(() => location.reload(), 500);
}

async function rejectContent(id) {
    await apiCall(`/api/content/${id}/reject`);
    setTimeout(() => location.reload(), 500);
}

async function publishContent(id) {
    await apiCall(`/api/content/${id}/publish`);
    setTimeout(() => location.reload(), 500);
}

async function rejectTopic(id) {
    await apiCall(`/api/topics/${id}/reject`);
    setTimeout(() => location.reload(), 500);
}

async function selectTopic(id) {
    await apiCall(`/api/topics/${id}/select`);
    setTimeout(() => location.reload(), 500);
}

async function pushProject(id) {
    await apiCall(`/api/projects/${id}/push`);
    setTimeout(() => location.reload(), 1000);
}

async function approveOutreach(id) {
    await apiCall(`/api/outreach/${id}/approve`);
    setTimeout(() => location.reload(), 500);
}

async function rejectOutreach(id) {
    await apiCall(`/api/outreach/${id}/reject`);
    setTimeout(() => location.reload(), 500);
}

async function markOutreachSent(id) {
    await apiCall(`/api/outreach/${id}/sent`);
    setTimeout(() => location.reload(), 500);
}

async function runScrape() { await apiCall('/api/actions/scrape'); setTimeout(() => location.reload(), 1000); }
async function runRank() { await apiCall('/api/actions/rank'); setTimeout(() => location.reload(), 1000); }
async function runHealthCheck() { await apiCall('/api/actions/health'); setTimeout(() => location.reload(), 1000); }
async function runBackup() { await apiCall('/api/actions/backup'); }

async function runOpenClaw() {
    const contentType = document.getElementById('oc-type')?.value || 'blog';
    const count = parseInt(document.getElementById('oc-count')?.value || '5');
    showToast(`Running OpenClaw: ${count}x ${contentType}...`, 'info');
    const result = await apiCall('/api/actions/openclaw', 'POST', {
        content_type: contentType, count: count
    });
    if (result.success) setTimeout(() => location.reload(), 1000);
}

// ── Copy to Clipboard ───────────────────

function copyContent(elementId) {
    const el = document.getElementById(elementId);
    if (!el) return;

    const text = el.innerText || el.textContent;
    navigator.clipboard.writeText(text).then(() => {
        const btn = event.target.closest('.copy-btn');
        if (btn) {
            btn.classList.add('copied');
            btn.textContent = 'Copied!';
            setTimeout(() => {
                btn.classList.remove('copied');
                btn.textContent = 'Copy';
            }, 2000);
        }
        showToast('Copied to clipboard', 'success');
    }).catch(() => {
        showToast('Copy failed', 'error');
    });
}

// ── Mobile Sidebar Toggle ───────────────

function toggleSidebar() {
    document.querySelector('.sidebar')?.classList.toggle('open');
}
