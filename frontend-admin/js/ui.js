/**
 * UI 组件模块
 * 提供 Toast 通知、Modal 弹窗、Loading 遮罩等通用 UI 能力
 */

import { getModalResolve, setModalResolve } from './app-state.js';

const iconMap = {
    success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️',
};

const titleMap = {
    success: '成功', error: '错误', warning: '提示', info: '提示',
};

function ensureContainer() {
    let container = document.getElementById('toastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainer';
        document.body.appendChild(container);
    }
    return container;
}

export function showToast(msg, { type = 'info', title, duration = 3500 } = {}) {
    const container = ensureContainer();
    const toast = document.createElement('div');
    toast.className = 'toast ' + type;
    const icon = iconMap[type] || iconMap.info;
    const titleText = title || titleMap[type] || '提示';
    toast.innerHTML = `
        <span class="toast-icon">${icon}</span>
        <div class="toast-body">
            <div class="toast-title">${titleText}</div>
            <div class="toast-msg">${msg}</div>
        </div>
        <button class="toast-close" onclick="this.parentElement.remove()">&times;</button>
        <div class="toast-progress" style="width:100%;transition:width ${duration}ms linear"></div>
    `;
    container.appendChild(toast);
    requestAnimationFrame(() => {
        toast.classList.add('show');
        toast.querySelector('.toast-progress').style.width = '0%';
    });
    const timer = setTimeout(() => {
        toast.classList.remove('show');
        toast.classList.add('hide');
        setTimeout(() => toast.remove(), 400);
    }, duration);
    toast.querySelector('.toast-close').addEventListener('click', () => {
        clearTimeout(timer);
        toast.classList.remove('show');
        toast.classList.add('hide');
        setTimeout(() => toast.remove(), 400);
    });
}

export function showModal(msg, { type = 'info', title, confirm = false } = {}) {
    return new Promise(resolve => {
        setModalResolve(resolve);
        document.getElementById('modalIcon').textContent = iconMap[type] || iconMap.info;
        document.getElementById('modalIcon').className = 'modal-icon ' + type;
        document.getElementById('modalTitle').textContent = title || titleMap[type] || '提示';
        document.getElementById('modalMsg').textContent = msg;

        const btnsEl = document.getElementById('modalBtns');
        if (confirm) {
            btnsEl.innerHTML = '<button class="btn btn-secondary" data-close="false">取消</button><button class="btn btn-primary" data-close="true">确定</button>';
        } else {
            btnsEl.innerHTML = '<button class="btn btn-primary" data-close="true">确定</button>';
        }
        btnsEl.querySelectorAll('[data-close]').forEach(btn => {
            btn.addEventListener('click', () => {
                closeModal(btn.dataset.close === 'true');
            });
        });

        const mask = document.getElementById('modalMask');
        mask.classList.remove('hidden');
        requestAnimationFrame(() => mask.classList.add('show'));
    });
}

export function closeModal(result = true) {
    const mask = document.getElementById('modalMask');
    mask.classList.remove('show');
    setTimeout(() => mask.classList.add('hidden'), 200);
    const resolve = getModalResolve();
    if (resolve) {
        resolve(result);
        setModalResolve(null);
    }
}

export function modalOutsideClick(e) {
    if (e.target === e.currentTarget) closeModal(false);
}

export function showLoading(show) {
    const el = document.getElementById('loadingOverlay');
    if (el) el.classList.toggle('hidden', !show);
}

export function setStatus(msg) {
    const el = document.getElementById('statusBar');
    if (el) el.textContent = msg;
}

export function updateLog(text) {
    const el = document.getElementById('logBox');
    if (el) {
        el.textContent = text;
        el.scrollTop = el.scrollHeight;
    }
}

export function showImage(id, base64Data) {
    const el = document.getElementById(id);
    if (el) el.src = 'data:image/jpeg;base64,' + base64Data;
}
