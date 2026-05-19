/**
 * 历史记录模块
 * 加载操作历史 / 会话列表 / 统计信息
 */

import { apiHistory, handleAuthError } from './api.js';
import { showToast } from './ui.js';

const actionLabels = {
    upload: '📂 上传照片', replace_background: '🎨 替换背景',
    remove_glasses: '👓 消除眼镜', enhance: '✨ 画质增强',
    crop: '✂️ 裁剪证件照', auto: '🚀 一键处理',
    reset: '🔄 重置', detect: '👤 人脸检测', export: '💾 导出',
    print: '📄 批量排版',
};

export function showHistoryPanel() {
    document.getElementById('historyOverlay').classList.remove('hidden');
    setTimeout(() => document.getElementById('historyOverlay').classList.add('show'), 10);
    document.getElementById('historyPanel').classList.add('open');
    switchHistoryTab('all');
}

export function closeHistoryPanel() {
    document.getElementById('historyPanel').classList.remove('open');
    document.getElementById('historyOverlay').classList.remove('show');
    setTimeout(() => document.getElementById('historyOverlay').classList.add('hidden'), 300);
}

export function switchHistoryTab(tab) {
    document.querySelectorAll('.history-tabs .tab').forEach(t => t.classList.remove('active'));
    document.getElementById('tabAll').classList.toggle('active', tab === 'all');
    document.getElementById('tabSessions').classList.toggle('active', tab === 'sessions');
    document.getElementById('tabStats').classList.toggle('active', tab === 'stats');
    document.getElementById('historyStats').classList.toggle('hidden', tab !== 'stats');

    if (tab === 'all') loadHistory('all');
    else if (tab === 'sessions') loadHistory('sessions');
    else if (tab === 'stats') loadStats();
}

async function loadHistory(type) {
    const listEl = document.getElementById('historyList');
    listEl.innerHTML = '<div style="text-align:center;color:#9aa0a6;padding:40px">加载中...</div>';

    try {
        const { res, data } = await apiHistory(type, 50);
        if (handleAuthError(res)) return;

        if (type === 'sessions') {
            renderSessions(listEl, data.sessions || []);
        } else {
            renderHistory(listEl, data.history || []);
        }
    } catch (err) {
        listEl.innerHTML = '<div style="text-align:center;color:#d93025;padding:40px">加载失败，请重试</div>';
    }
}

function renderSessions(listEl, sessions) {
    if (sessions.length === 0) {
        listEl.innerHTML = '<div style="text-align:center;color:#9aa0a6;padding:40px">暂无会话记录</div>';
        return;
    }
    const printMode = !!window.__printMode;
    const selected = window.__printSelected || new Set();
    listEl.innerHTML = sessions.map(s => {
        const checkbox = printMode
            ? `<input type="checkbox" class="print-checkbox" data-sid="${s.sid}" ${selected.has(s.sid) ? 'checked' : ''} style="margin-right:6px">`
            : '';
        const printBadge = s.used_for_printing ? '<span class="print-badge">已排版</span>' : '';
        return `
            <div class="history-item" data-sid="${s.sid}">
                <div class="action-file">${s.filename || '未知文件'}</div>
                <div class="action-params">
                    ${checkbox}
                    ${s.has_face ? '✅ 检测到人脸' : '❌ 未检测到人脸'}
                    ${s.confidence ? ' (置信度: ' + s.confidence.toFixed(2) + ')' : ''}
                    ${s.has_glasses ? ' 👓 佩戴眼镜' : ''}
                    ${printBadge}
                </div>
                <div class="action-time">${s.created_at}</div>
            </div>
        `;
    }).join('');

    if (printMode) {
        listEl.querySelectorAll('.history-item').forEach(el => {
            el.addEventListener('click', () => {
                const sid = el.dataset.sid;
                import('./printing.js').then(m => m.togglePrintSelectFromRender(sid, el));
            });
        });
    }
}

function renderHistory(listEl, history) {
    if (history.length === 0) {
        listEl.innerHTML = '<div style="text-align:center;color:#9aa0a6;padding:40px">暂无操作记录</div>';
        return;
    }
    listEl.innerHTML = history.map(h => `
        <div class="history-item">
            <div>
                <span class="action-name">${actionLabels[h.action] || h.action}</span>
                <span class="status-badge ${h.status}">${h.status === 'success' ? '成功' : '失败'}</span>
            </div>
            ${h.params ? '<div class="action-params">' + h.params + '</div>' : ''}
            ${h.filename ? '<div class="action-file">' + h.filename + '</div>' : ''}
            <div class="action-time">${h.created_at}</div>
        </div>
    `).join('');
}

async function loadStats() {
    try {
        const { res, data } = await apiHistory('stats');
        if (handleAuthError(res)) return;
        const stats = data.stats || {};
        document.getElementById('statSessions').textContent = stats.session_count || 0;
        document.getElementById('statOps').textContent = stats.history_count || 0;
        document.getElementById('statExports').textContent = stats.export_count || 0;
        document.getElementById('historyList').innerHTML = '<div style="text-align:center;color:#9aa0a6;padding:40px">统计信息已显示在上方</div>';
    } catch (err) {
        document.getElementById('historyList').innerHTML = '<div style="text-align:center;color:#d93025;padding:40px">加载失败，请重试</div>';
    }
}
