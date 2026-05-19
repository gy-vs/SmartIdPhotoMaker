/**
 * 批量排版模块
 * 管理多选状态、版式选择、PDF/JPG 导出下载
 */

import {
    getPrintMode, setPrintMode,
    getPrintSelected, addPrintSelected, removePrintSelected, clearPrintSelected, hasPrintSelected,
} from './app-state.js';
import { apiPrintingExport, apiPrintingDownload, handleAuthError } from './api.js';
import { showToast, showModal, setStatus } from './ui.js';
import { switchHistoryTab } from './history.js';

export function togglePrintMode() {
    const mode = !getPrintMode();
    setPrintMode(mode);
    window.__printMode = mode;
    if (mode) {
        clearPrintSelected();
        switchHistoryTab('sessions');
        document.getElementById('printToolbar').classList.add('show');
        showToast('已进入批量排版模式，请勾选照片后点击生成', { type: 'info', title: '批量排版' });
    } else {
        clearPrintSelected();
        document.getElementById('printToolbar').classList.remove('show');
        switchHistoryTab('sessions');
    }
}

export function togglePrintSelectFromRender(sid, rowEl) {
    if (!getPrintMode()) return;
    const selected = getPrintSelected();
    const checkbox = rowEl.querySelector('.print-checkbox');
    if (hasPrintSelected(sid)) {
        selected.delete(sid);
        removePrintSelected(sid);
        if (checkbox) checkbox.checked = false;
        rowEl.classList.remove('print-selected');
    } else {
        selected.add(sid);
        addPrintSelected(sid);
        if (checkbox) checkbox.checked = true;
        rowEl.classList.add('print-selected');
    }
    document.getElementById('printInfo').textContent = '已选中 ' + selected.size + ' 张照片';
}

export function clearPrintSelection() {
    clearPrintSelected();
    document.getElementById('printInfo').textContent = '已选中 0 张照片';
    switchHistoryTab('sessions');
}

async function _doPrinting(targetFormat) {
    const selected = getPrintSelected();
    if (selected.size === 0) {
        showModal('请先勾选至少一张照片再进行排版', { type: 'warning', title: '温馨提示' });
        return;
    }
    const layoutKey = document.getElementById('printLayoutSelect').value;
    setStatus('正在生成排版，请稍候...');
    try {
        const { res, data } = await apiPrintingExport(Array.from(selected), layoutKey);
        if (handleAuthError(res)) return;
        if (!res.ok) { showModal(data.error || '排版失败', { type: 'error', title: '排版失败' }); setStatus('排版失败'); return; }

        const url = targetFormat === 'pdf' ? data.pdf_url : data.jpg_url;
        const filename = targetFormat === 'pdf' ? data.pdf_name : data.jpg_name;
        const { res: dlRes, blob } = await apiPrintingDownload(url);
        if (!dlRes.ok) { showModal('下载排版文件失败', { type: 'error', title: '下载失败' }); return; }
        const dlUrl = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = dlUrl;
        a.download = 'A4排版_照片_' + selected.size + '张.' + targetFormat;
        a.click();
        URL.revokeObjectURL(dlUrl);
        setStatus('排版导出成功');
        showToast('排版导出成功，已自动下载', { type: 'success', title: '成功' });
        clearPrintSelected();
        document.getElementById('printInfo').textContent = '已选中 0 张照片';
        switchHistoryTab('sessions');
    } catch (err) {
        showModal('网络连接失败，请检查网络后重试', { type: 'error', title: '排版失败' });
        setStatus('排版失败');
    }
}

export function submitPrinting() {
    return _doPrinting('pdf');
}

export function submitPrintingJpg() {
    return _doPrinting('jpg');
}
