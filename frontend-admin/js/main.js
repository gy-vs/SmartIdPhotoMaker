/**
 * 入口模块
 * 汇总所有子模块的公共 API 暴露到 window 上，并完成 DOM 事件绑定
 * 所有函数均使用 ES6 模块 + camelCase 命名
 */

import { checkAuth, handleAuth, logout, toggleAuthMode, bindAuthEvents } from './auth.js';
import { triggerUpload, bindUploadEvents, doAction, resetPhoto, exportPhoto } from './upload.js';
import { showHistoryPanel as showHistory, closeHistoryPanel as closeHistory, switchHistoryTab } from './history.js';
import { togglePrintMode, clearPrintSelection, submitPrinting, submitPrintingJpg } from './printing.js';
import { closeModal, modalOutsideClick } from './ui.js';

window.triggerUpload = triggerUpload;
window.resetPhoto = resetPhoto;
window.exportPhoto = exportPhoto;
window.showHistory = showHistory;
window.closeHistory = closeHistory;
window.logout = logout;
window.handleAuth = handleAuth;
window.toggleAuthMode = toggleAuthMode;
window.doAction = doAction;
window.switchHistoryTab = switchHistoryTab;
window.togglePrintMode = togglePrintMode;
window.clearPrintSelection = clearPrintSelection;
window.submitPrinting = submitPrinting;
window.submitPrintingJpg = submitPrintingJpg;
window.closeModal = closeModal;
window.modalOutsideClick = modalOutsideClick;

bindAuthEvents();
bindUploadEvents();
checkAuth();
