const layoutApi = '';

const layoutState = {
  selectedSessions: [],
  layoutType: 'one_inch',
  authToken: null,
};

function getLayoutAuthHeaders() {
  const token = layoutState.authToken || localStorage.getItem('idphoto_token');
  return token ? { Authorization: 'Bearer ' + token } : {};
}

async function fetchSessionsForLayout() {
  try {
    const res = await fetch(layoutApi + '/api/history?type=sessions&limit=50', {
      headers: getLayoutAuthHeaders(),
    });
    if (!res.ok) {
      const data = await res.json();
      throw new Error(data.error || '加载会话列表失败');
    }
    const data = await res.json();
    return data.sessions || [];
  } catch (err) {
    showLayoutToast(err.message, 'error');
    return [];
  }
}

function renderSessionList(sessions) {
  const container = document.getElementById('sessionList');
  if (!sessions.length) {
    container.innerHTML = '<div class="empty-tip">暂无已处理的会话，请先上传并处理照片</div>';
    return;
  }
  container.innerHTML = sessions.map(s => `
    <label class="session-item${s.layout_exported ? ' exported' : ''}" data-sid="${s.sid}">
      <input type="checkbox" class="session-checkbox" value="${s.sid}" ${s.layout_exported ? '' : ''}>
      <div class="session-info">
        <div class="session-filename">${s.filename || '未知文件'}</div>
        <div class="session-meta">
          ${s.has_face ? '✅ 人脸' : '❌ 无人脸'}
          ${s.confidence ? ' 置信度: ' + s.confidence.toFixed(2) : ''}
          ${s.layout_exported ? ' 🏷️ 已排版' : ''}
        </div>
        <div class="session-time">${s.created_at || ''}</div>
      </div>
    </label>
  `).join('');

  container.querySelectorAll('.session-checkbox').forEach(cb => {
    cb.addEventListener('change', onSessionCheckChange);
  });
}

function onSessionCheckChange() {
  const checkboxes = document.querySelectorAll('.session-checkbox:checked');
  layoutState.selectedSessions = Array.from(checkboxes).map(cb => cb.value);
  document.getElementById('selectedCount').textContent = layoutState.selectedSessions.length;
  document.getElementById('layoutSubmitBtn').disabled = layoutState.selectedSessions.length === 0;
}

function selectAllSessions() {
  document.querySelectorAll('.session-checkbox').forEach(cb => { cb.checked = true; });
  onSessionCheckChange();
}

function deselectAllSessions() {
  document.querySelectorAll('.session-checkbox').forEach(cb => { cb.checked = false; });
  onSessionCheckChange();
}

function onLayoutTypeChange(type) {
  layoutState.layoutType = type;
  document.querySelectorAll('.layout-option').forEach(opt => {
    opt.classList.toggle('active', opt.dataset.type === type);
  });
  const capacityMap = { one_inch: 8, two_inch: 4, mixed: 6 };
  document.getElementById('layoutCapacity').textContent = capacityMap[type] || 8;
}

async function submitLayout() {
  if (layoutState.selectedSessions.length === 0) {
    showLayoutToast('请至少选择一个会话', 'warning');
    return;
  }

  const btn = document.getElementById('layoutSubmitBtn');
  btn.disabled = true;
  btn.textContent = '排版中...';

  try {
    const res = await fetch(layoutApi + '/api/layout/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getLayoutAuthHeaders() },
      body: JSON.stringify({
        session_ids: layoutState.selectedSessions,
        layout_type: layoutState.layoutType,
      }),
    });
    const data = await res.json();

    if (!res.ok || data.error) {
      showLayoutToast(data.error || '排版导出失败', 'error');
      btn.disabled = false;
      btn.textContent = '生成排版';
      return;
    }

    showLayoutToast('排版导出成功！', 'success');
    document.getElementById('downloadSection').classList.remove('hidden');
    document.getElementById('downloadPdfBtn').onclick = () => downloadFile(data.pdf_download, 'A4排版.pdf');
    document.getElementById('downloadJpgBtn').onclick = () => downloadFile(data.jpg_download, 'A4排版.jpg');

    const sessions = await fetchSessionsForLayout();
    renderSessionList(sessions);
    onSessionCheckChange();
  } catch (err) {
    showLayoutToast('网络连接失败，请重试', 'error');
  }
  btn.disabled = false;
  btn.textContent = '生成排版';
}

function downloadFile(url, filename) {
  const a = document.createElement('a');
  a.href = url + '?token=' + (layoutState.authToken || localStorage.getItem('idphoto_token') || '');
  a.download = filename;
  a.click();
}

function showLayoutToast(msg, type) {
  const container = document.getElementById('layoutToastContainer');
  const toast = document.createElement('div');
  toast.className = 'layout-toast ' + type;
  toast.textContent = msg;
  container.appendChild(toast);
  requestAnimationFrame(() => toast.classList.add('show'));
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

async function initLayoutPage() {
  layoutState.authToken = localStorage.getItem('idphoto_token');
  if (!layoutState.authToken) {
    window.location.href = '/';
    return;
  }

  let preselectedSids = [];
  try {
    const stored = localStorage.getItem('idphoto_batch_sids');
    if (stored) {
      preselectedSids = JSON.parse(stored);
      localStorage.removeItem('idphoto_batch_sids');
    }
  } catch (e) {
    preselectedSids = [];
  }

  onLayoutTypeChange('one_inch');

  document.querySelectorAll('.layout-option').forEach(opt => {
    opt.addEventListener('click', () => onLayoutTypeChange(opt.dataset.type));
  });

  document.getElementById('selectAllBtn').addEventListener('click', selectAllSessions);
  document.getElementById('deselectAllBtn').addEventListener('click', deselectAllSessions);
  document.getElementById('layoutSubmitBtn').addEventListener('click', submitLayout);
  document.getElementById('backToMainBtn').addEventListener('click', () => { window.location.href = '/'; });

  const sessions = await fetchSessionsForLayout();
  renderSessionList(sessions);

  if (preselectedSids.length > 0) {
    preselectedSids.forEach(sid => {
      const cb = document.querySelector(`.session-checkbox[value="${sid}"]`);
      if (cb) cb.checked = true;
    });
    onSessionCheckChange();
  }
}

document.addEventListener('DOMContentLoaded', initLayoutPage);

export { layoutState, fetchSessionsForLayout, submitLayout };
