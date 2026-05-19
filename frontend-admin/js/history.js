/**
 * 历史记录模块
 * 历史记录展示、会话列表、统计信息
 */

import { API, authHeaders, handleAuthError } from './auth.js';
import { showModal } from './ui.js';

const actionLabels = {
    upload: '📂 上传照片',
    replace_background: '🎨 替换背景',
    remove_glasses: '👓 消除眼镜',
    enhance: '✨ 画质增强',
    crop: '✂️ 裁剪证件照',
    auto: '🚀 一键处理',
    reset: '🔄 重置',
    detect: '👤 人脸检测',
    export: '💾 导出',
    print: '🖨️ 排版导出',
};

let currentHistoryType = 'all';

/**
 * 打开历史记录面板
 */
export function showHistory() {
    document.getElementById('historyOverlay').classList.remove('hidden');
    setTimeout(() => document.getElementById('historyOverlay').classList.add('show'), 10);
    document.getElementById('historyPanel').classList.add('open');
    switchHistoryTab('all');
}

/**
 * 关闭历史记录面板
 */
export function closeHistory() {
    document.getElementById('historyPanel').classList.remove('open');
    document.getElementById('historyOverlay').classList.remove('show');
    setTimeout(() => document.getElementById('historyOverlay').classList.add('hidden'), 300);
}

/**
 * 切换历史记录标签页
 * @param {string} tab - 标签页类型：all/sessions/stats
 */
export function switchHistoryTab(tab) {
    currentHistoryType = tab;
    document.querySelectorAll('.history-tabs .tab').forEach(t => t.classList.remove('active'));
    document.getElementById('tabAll').classList.toggle('active', tab === 'all');
    document.getElementById('tabSessions').classList.toggle('active', tab === 'sessions');
    document.getElementById('tabStats').classList.toggle('active', tab === 'stats');
    document.getElementById('historyStats').classList.toggle('hidden', tab !== 'stats');

    if (tab === 'all') {
        loadHistory('all');
    } else if (tab === 'sessions') {
        loadHistory('sessions');
    } else if (tab === 'stats') {
        loadStats();
    }
}

/**
 * 加载历史记录
 * @param {string} type - 类型
 * @param {Map<string, boolean>} selectedSessions - 已选中的会话集合
 * @param {Function} updateSelectionUI - 更新选择 UI 的函数
 */
export async function loadHistory(type, selectedSessions = null, updateSelectionUI = null) {
    const listEl = document.getElementById('historyList');
    listEl.innerHTML = '<div style="text-align:center;color:#9aa0a6;padding:40px">加载中...</div>';

    try {
        const res = await fetch(API + '/api/history?type=' + type + '&limit=50', {
            headers: authHeaders(),
        });

        if (handleAuthError(res)) return;

        const data = await res.json();

        if (type === 'sessions') {
            const sessions = data.sessions || [];
            if (sessions.length === 0) {
                listEl.innerHTML = '<div style="text-align:center;color:#9aa0a6;padding:40px">暂无会话记录</div>';
                return;
            } else {
                renderSessionList(sessions, selectedSessions, updateSelectionUI);
            }
        } else if (type === 'all') {
            const history = data.history || [];
            if (history.length === 0) {
                listEl.innerHTML = '<div style="text-align:center;color:#9aa0a6;padding:40px">暂无操作记录</div>';
                return;
            } else {
                renderHistoryList(history);
            }
        }
    } catch (err) {
        listEl.innerHTML = '<div style="text-align:center;color:#d93025;padding:40px">加载失败，请重试</div>';
    }
}

/**
 * 渲染会话列表
 * @param {Array} sessions - 会话列表
 * @param {Map<string, boolean>} selectedSessions - 已选中的会话集合
 * @param {Function} updateSelectionUI - 更新选择 UI 的函数
 */
function renderSessionList(sessions, selectedSessions, updateSelectionUI) {
    const listEl = document.getElementById('historyList');
    listEl.innerHTML = sessions.map(s => `
        <div class="session-item ${selectedSessions && selectedSessions.has(s.sid) ? 'selected' : ''}" 
             data-sid="${s.sid}">
            <input type="checkbox" class="session-checkbox"
                ${selectedSessions && selectedSessions.has(s.sid) ? 'checked' : ''}>
            <div class="session-item-content">
                <div class="action-file">
                    ${s.filename || '未知文件'}
                    ${s.used_for_printing ? '<span class="print-badge">已排版</span>' : ''}
                </div>
                <div class="action-params">
                    ${s.has_face ? '✅ 检测到人脸' : '❌ 未检测到人脸'}
                    ${s.confidence ? ' (置信度: ' + s.confidence.toFixed(2) + ')' : ''}
                    ${s.has_glasses ? ' 👓 佩戴眼镜' : ''}
                </div>
                <div class="action-time">${s.created_at}</div>
            </div>
        </div>
    `).join('');

    if (selectedSessions) {
        listEl.querySelectorAll('.session-item').forEach(item => {
            const sid = item.dataset.sid;
            const checkbox = item.querySelector('.session-checkbox');
            const content = item.querySelector('.session-item-content');

            if (checkbox) {
                checkbox.addEventListener('click', (e) => {
                    e.stopPropagation();
                    if (window.toggleSessionSelection) {
                        window.toggleSessionSelection(sid, e);
                    }
                });
            }
            if (content) {
                content.addEventListener('click', (e) => {
                    e.stopPropagation();
                    if (window.toggleSessionSelection) {
                        window.toggleSessionSelection(sid, e);
                    }
                });
            }
        });
    }
}

/**
 * 渲染历史操作记录列表
 * @param {Array} history - 历史记录列表
 */
function renderHistoryList(history) {
    const listEl = document.getElementById('historyList');
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

/**
 * 加载统计信息
 */
export async function loadStats() {
    try {
        const res = await fetch(API + '/api/history?type=stats', {
            headers: authHeaders(),
        });

        if (handleAuthError(res)) return;

        const data = await res.json();
        const stats = data.stats || {};
        document.getElementById('statSessions').textContent = stats.session_count || 0;
        document.getElementById('statOps').textContent = stats.history_count || 0;
        document.getElementById('statExports').textContent = stats.export_count || 0;
        document.getElementById('statPrints').textContent = stats.print_count || 0;
        document.getElementById('historyList').innerHTML = '<div style="text-align:center;color:#9aa0a6;padding:40px">统计信息已显示在上方</div>';
    } catch (err) {
        document.getElementById('historyList').innerHTML = '<div style="text-align:center;color:#d93025;padding:40px">加载失败，请重试</div>';
    }
}

/**
 * 初始化历史记录事件监听
 * @param {Function} onShowHistory - 显示历史记录的回调
 */
export function initHistoryEventListeners(onShowHistory) {
    document.getElementById('historyOverlay').addEventListener('click', () => {
        closeHistory();
    });
}
