/**
 * 应用主入口模块
 * 整合所有功能模块，初始化事件监听
 */

import { checkAuth, toggleAuthMode, handleAuth, logout, initAuthEventListeners } from './auth.js';
import { showToast, showModal, closeModal, initModalEventListeners } from './ui.js';
import { showHistory, switchHistoryTab, loadHistory, closeHistory, initHistoryEventListeners } from './history.js';
import {
    initPrintEventListeners,
    toggleSessionSelection,
    updateSelectionUI,
    clearSelection,
    enterPrintPage,
    exitPrintPage,
    previewPrintLayout,
    generatePrint,
    getSelectedSessions,
} from './print.js';
import {
    triggerUpload,
    doAction,
    resetPhoto,
    exportPhoto,
    initUploadEventListeners,
} from './photo.js';

/**
 * 初始化应用
 */
function initApp() {
    checkAuth();

    initAuthEventListeners(() => handleAuth(showModal));
    initModalEventListeners();
    initHistoryEventListeners();
    initPrintEventListeners();
    initUploadEventListeners();

    bindGlobalFunctions();

    console.log('智能证件照系统已加载完成');
}

/**
 * 绑定全局函数供 HTML onclick 使用
 */
function bindGlobalFunctions() {
    window.toggleAuthMode = toggleAuthMode;
    window.handleAuth = () => handleAuth(showModal);
    window.logout = logout;

    window.showHistory = () => {
        showHistory();
        setTimeout(() => {
            const selected = getSelectedSessions();
            loadHistory('sessions', selected, updateSelectionUI);
        }, 100);
    };
    window.closeHistory = closeHistory;
    window.switchHistoryTab = (tab) => {
        if (tab === 'sessions') {
            const selected = getSelectedSessions();
            loadHistory(tab, selected, updateSelectionUI);
        } else {
            loadHistory(tab);
        }
        document.querySelectorAll('.history-tabs .tab').forEach(t => t.classList.remove('active'));
        document.getElementById('tabAll').classList.toggle('active', tab === 'all');
        document.getElementById('tabSessions').classList.toggle('active', tab === 'sessions');
        document.getElementById('tabStats').classList.toggle('active', tab === 'stats');
        document.getElementById('historyStats').classList.toggle('hidden', tab !== 'stats');
    };

    window.toggleSessionSelection = toggleSessionSelection;
    window.clearSelection = clearSelection;
    window.enterPrintPage = enterPrintPage;
    window.exitPrintPage = exitPrintPage;
    window.previewPrintLayout = previewPrintLayout;
    window.generatePrint = generatePrint;

    window.triggerUpload = triggerUpload;
    window.doAction = doAction;
    window.resetPhoto = resetPhoto;
    window.exportPhoto = exportPhoto;

    window.closeModal = closeModal;
    window.modalOutsideClick = (e) => {
        if (e.target === e.currentTarget) closeModal(false);
    };

    window.handleAuthModeToggle = () => toggleAuthMode();
}

document.addEventListener('DOMContentLoaded', initApp);

export {
    showToast,
    showModal,
    closeModal,
};
