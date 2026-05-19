/**
 * UI 组件模块
 * Toast 轻量通知 + Modal 自定义弹窗
 */

const iconMap = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };

let modalResolve = null;

/**
 * 显示 Toast 轻量通知
 * @param {string} msg - 消息内容
 * @param {Object} options - 配置选项
 * @param {string} [options.type='info'] - 类型：success/error/warning/info
 * @param {string} [options.title] - 标题
 * @param {number} [options.duration=3500] - 显示时长（毫秒）
 */
export function showToast(msg, { type = 'info', title, duration = 3500 } = {}) {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = 'toast ' + type;
    const icon = iconMap[type] || iconMap.info;
    const titleText = title || { success: '成功', error: '错误', warning: '提示', info: '提示' }[type] || '提示';
    toast.innerHTML = `
        <span class="toast-icon">${icon}</span>
        <div class="toast-body">
            <div class="toast-title">${titleText}</div>
            <div class="toast-msg">${msg}</div>
        </div>
        <button class="toast-close" aria-label="关闭">&times;</button>
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

/**
 * 显示自定义弹窗
 * @param {string} msg - 消息内容
 * @param {Object} options - 配置选项
 * @param {string} [options.type='info'] - 类型：success/error/warning/info
 * @param {string} [options.title] - 标题
 * @param {boolean} [options.confirm=false] - 是否为确认框
 * @returns {Promise<boolean>} 用户选择结果
 */
export function showModal(msg, { type = 'info', title, confirm = false } = {}) {
    return new Promise(resolve => {
        modalResolve = resolve;
        document.getElementById('modalIcon').textContent = iconMap[type] || iconMap.info;
        document.getElementById('modalIcon').className = 'modal-icon ' + type;
        document.getElementById('modalTitle').textContent = title || { success: '成功', error: '错误', warning: '提示', info: '提示' }[type] || '提示';
        document.getElementById('modalMsg').textContent = msg;

        const btnsEl = document.getElementById('modalBtns');
        if (confirm) {
            btnsEl.innerHTML = '<button class="btn btn-secondary" data-modal-cancel>取消</button><button class="btn btn-primary" data-modal-confirm>确定</button>';
        } else {
            btnsEl.innerHTML = '<button class="btn btn-primary" data-modal-confirm>确定</button>';
        }

        const mask = document.getElementById('modalMask');
        mask.classList.remove('hidden');
        requestAnimationFrame(() => mask.classList.add('show'));
    });
}

/**
 * 关闭弹窗
 * @param {boolean} [result=true] - 返回结果
 */
export function closeModal(result = true) {
    const mask = document.getElementById('modalMask');
    mask.classList.remove('show');
    setTimeout(() => mask.classList.add('hidden'), 200);
    if (modalResolve) {
        modalResolve(result);
        modalResolve = null;
    }
}

/**
 * 初始化弹窗事件监听
 */
export function initModalEventListeners() {
    const mask = document.getElementById('modalMask');
    mask.addEventListener('click', e => {
        if (e.target === mask) {
            closeModal(false);
        }
    });

    mask.addEventListener('click', e => {
        if (e.target.hasAttribute('data-modal-confirm')) {
            closeModal(true);
        } else if (e.target.hasAttribute('data-modal-cancel')) {
            closeModal(false);
        }
    });
}

/**
 * 设置状态栏文字
 * @param {string} msg - 状态消息
 */
export function setStatus(msg) {
    document.getElementById('statusBar').textContent = msg;
}

/**
 * 更新日志内容
 * @param {string} text - 日志文本
 */
export function updateLog(text) {
    const el = document.getElementById('logBox');
    el.textContent = text;
    el.scrollTop = el.scrollHeight;
}

/**
 * 显示/隐藏加载遮罩
 * @param {boolean} show - 是否显示
 */
export function showLoading(show) {
    document.getElementById('loadingOverlay').classList.toggle('hidden', !show);
}

/**
 * 显示 base64 图片
 * @param {string} id - 图片元素 ID
 * @param {string} base64Data - base64 图片数据
 */
export function showImage(id, base64Data) {
    document.getElementById(id).src = 'data:image/jpeg;base64,' + base64Data;
}
