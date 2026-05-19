/**
 * 排版导出模块
 * A4 批量排版导出功能
 */

import { API, authHeaders, handleAuthError } from './auth.js';
import { showToast, showModal } from './ui.js';
import { closeHistory } from './history.js';

let selectedSessions = new Set();
let currentPrintLayout = 'one_inch';

const layoutLimits = { one_inch: 8, two_inch: 4, mixed: 6 };

/**
 * 获取已选中的会话
 * @returns {Set<string>}
 */
export function getSelectedSessions() {
    return selectedSessions;
}

/**
 * 获取当前版式类型
 * @returns {string}
 */
export function getCurrentPrintLayout() {
    return currentPrintLayout;
}

/**
 * 初始化版式选择事件监听
 */
export function initPrintEventListeners() {
    document.querySelectorAll('input[name="layoutType"]').forEach(radio => {
        radio.addEventListener('change', function () {
            currentPrintLayout = this.value;
            document.querySelectorAll('.layout-option').forEach(opt => {
                opt.classList.toggle('active', opt.querySelector('input').checked);
            });
            updatePrintPhotoLimit();
        });
    });
}

/**
 * 更新排版照片数量限制提示
 */
export function updatePrintPhotoLimit() {
    const max = layoutLimits[currentPrintLayout] || 8;
    document.getElementById('printPhotoLimit').textContent = `最多可放 ${max} 张`;
}

/**
 * 切换会话选择状态
 * @param {string} sid - 会话 ID
 * @param {Event} event - 点击事件
 */
export function toggleSessionSelection(sid, event) {
    if (event && event.stopPropagation) {
        event.stopPropagation();
    }

    if (selectedSessions.has(sid)) {
        selectedSessions.delete(sid);
    } else {
        const max = layoutLimits[currentPrintLayout] || 8;
        if (selectedSessions.size >= max) {
            showToast(`最多只能选择 ${max} 张照片`, { type: 'warning' });
            return;
        }
        selectedSessions.add(sid);
    }

    updateSelectionUI();
}

/**
 * 更新选择状态 UI
 */
export function updateSelectionUI() {
    document.getElementById('selectedCount').textContent = selectedSessions.size;
    document.getElementById('batchActions').classList.toggle('hidden', selectedSessions.size === 0);

    document.querySelectorAll('.session-item').forEach(item => {
        const sid = item.dataset.sid;
        item.classList.toggle('selected', selectedSessions.has(sid));
        const checkbox = item.querySelector('.session-checkbox');
        if (checkbox) {
            checkbox.checked = selectedSessions.has(sid);
        }
    });
}

/**
 * 清除所有选择
 */
export function clearSelection() {
    selectedSessions.clear();
    updateSelectionUI();
}

/**
 * 进入排版页面
 */
export function enterPrintPage() {
    if (selectedSessions.size === 0) {
        showToast('请先选择要排版的照片', { type: 'warning' });
        return;
    }

    closeHistory();
    document.getElementById('printPage').classList.remove('hidden');
    document.getElementById('printPhotoCount').textContent = selectedSessions.size;
    updatePrintPhotoLimit();
    document.getElementById('printPreview').style.display = 'none';
    document.getElementById('printPreviewPlaceholder').style.display = 'block';
}

/**
 * 退出排版页面
 */
export function exitPrintPage() {
    document.getElementById('printPage').classList.add('hidden');
}

/**
 * 预览排版效果
 * @returns {Promise<void>}
 */
export async function previewPrintLayout() {
    if (selectedSessions.size === 0) {
        showToast('请先选择照片', { type: 'warning' });
        return;
    }

    const btn = document.getElementById('previewBtn');
    btn.disabled = true;
    btn.textContent = '生成预览中...';

    try {
        const res = await fetch(API + '/api/print/preview', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...authHeaders() },
            body: JSON.stringify({
                session_ids: Array.from(selectedSessions),
                layout_type: currentPrintLayout,
            }),
        });

        if (handleAuthError(res)) return;

        const data = await res.json();

        if (data.error) {
            showModal(data.error, { type: 'error' });
            return;
        }

        const img = document.getElementById('printPreview');
        img.src = 'data:image/jpeg;base64,' + data.preview;
        img.style.display = 'block';
        document.getElementById('printPreviewPlaceholder').style.display = 'none';
        showToast('预览生成成功', { type: 'success' });
    } catch (err) {
        showModal('预览生成失败，请检查网络后重试', { type: 'error' });
    }

    btn.disabled = false;
    btn.textContent = '👁️ 预览排版';
}

/**
 * 生成排版文件
 * @param {string} format - 格式：pdf/jpg/both
 * @returns {Promise<void>}
 */
export async function generatePrint(format) {
    if (selectedSessions.size === 0) {
        showToast('请先选择照片', { type: 'warning' });
        return;
    }

    const formatLabels = { pdf: 'PDF', jpg: 'JPG', both: 'PDF + JPG' };
    const btnMap = { pdf: 'downloadPdfBtn', jpg: 'downloadJpgBtn', both: 'downloadBothBtn' };
    const btn = document.getElementById(btnMap[format]);
    btn.disabled = true;
    btn.textContent = `生成${formatLabels[format]}中...`;

    try {
        const res = await fetch(API + '/api/print/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...authHeaders() },
            body: JSON.stringify({
                session_ids: Array.from(selectedSessions),
                layout_type: currentPrintLayout,
                format: format,
            }),
        });

        if (handleAuthError(res)) return;

        const data = await res.json();

        if (data.error) {
            showModal(data.error, { type: 'error' });
            return;
        }

        if (data.pdf_url) {
            window.open(API + data.pdf_url, '_blank');
        }
        if (data.jpg_url) {
            window.open(API + data.jpg_url, '_blank');
        }

        showToast(`${formatLabels[format]} 生成成功，正在下载...`, { type: 'success' });
        clearSelection();
    } catch (err) {
        showModal('生成失败，请检查网络后重试', { type: 'error' });
    }

    btn.disabled = false;
    const originalTexts = {
        pdf: '💾 下载 PDF',
        jpg: '🖼️ 下载高清 JPG',
        both: '📦 同时下载 PDF + JPG'
    };
    btn.textContent = originalTexts[format] || btn.textContent;
}
