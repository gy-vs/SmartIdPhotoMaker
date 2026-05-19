/**
 * 认证模块
 * 处理登录、注册、token 管理
 */

export const API = '';

let authToken = localStorage.getItem('idphoto_token') || null;
let currentUser = localStorage.getItem('idphoto_user') || null;
let isLoginMode = true;

/**
 * 获取当前认证状态
 * @returns {{ token: string|null, user: string|null }}
 */
export function getAuthState() {
    return { token: authToken, user: currentUser };
}

/**
 * 获取认证请求头
 * @returns {Object}
 */
export function authHeaders() {
    return authToken ? { 'Authorization': 'Bearer ' + authToken } : {};
}

/**
 * 处理认证错误（401）
 * @param {Response} res - Fetch 响应对象
 * @returns {boolean} 是否为认证错误
 */
export function handleAuthError(res) {
    if (res.status === 401) {
        logout();
        return true;
    }
    return false;
}

/**
 * 检查认证状态，更新 UI
 */
export function checkAuth() {
    if (authToken && currentUser) {
        document.getElementById('authPage').classList.add('hidden');
        document.getElementById('userInfo').textContent = '👤 ' + currentUser;
    } else {
        document.getElementById('authPage').classList.remove('hidden');
    }
}

/**
 * 切换登录/注册模式
 */
export function toggleAuthMode() {
    isLoginMode = !isLoginMode;
    document.getElementById('authError').textContent = '';
    document.getElementById('authUsername').value = '';
    document.getElementById('authPassword').value = '';

    if (isLoginMode) {
        document.getElementById('authSubtitle').textContent = '登录后开始制作证件照';
        document.getElementById('authSubmitBtn').textContent = '登 录';
        document.getElementById('authSwitch').innerHTML = '还没有账号？<a onclick="window.handleAuthModeToggle()">立即注册</a>';
        document.getElementById('authPassword').setAttribute('autocomplete', 'current-password');
    } else {
        document.getElementById('authSubtitle').textContent = '注册新账号';
        document.getElementById('authSubmitBtn').textContent = '注 册';
        document.getElementById('authSwitch').innerHTML = '已有账号？<a onclick="window.handleAuthModeToggle()">返回登录</a>';
        document.getElementById('authPassword').setAttribute('autocomplete', 'new-password');
    }
}

/**
 * 处理登录/注册
 * @param {Function} showModal - 弹窗函数
 * @returns {Promise<void>}
 */
export async function handleAuth(showModal) {
    const username = document.getElementById('authUsername').value.trim();
    const password = document.getElementById('authPassword').value;
    const errorEl = document.getElementById('authError');
    errorEl.textContent = '';

    if (!username) {
        errorEl.textContent = '请输入用户名';
        return;
    }
    if (!password) {
        errorEl.textContent = '请输入密码';
        return;
    }

    const url = isLoginMode ? API + '/api/login' : API + '/api/register';
    const btn = document.getElementById('authSubmitBtn');
    btn.disabled = true;
    btn.textContent = isLoginMode ? '登录中...' : '注册中...';

    try {
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password }),
        });
        const data = await res.json();

        if (!res.ok || data.error) {
            errorEl.textContent = data.error || '操作失败，请重试';
            btn.disabled = false;
            btn.textContent = isLoginMode ? '登 录' : '注 册';
            return;
        }

        if (isLoginMode) {
            authToken = data.token;
            currentUser = data.username;
            localStorage.setItem('idphoto_token', authToken);
            localStorage.setItem('idphoto_user', currentUser);
            checkAuth();
        } else {
            errorEl.textContent = '';
            isLoginMode = true;
            toggleAuthMode();
            toggleAuthMode();
            document.getElementById('authError').style.color = '#0d652d';
            document.getElementById('authError').textContent = '注册成功，请登录';
            setTimeout(() => {
                document.getElementById('authError').style.color = '#d93025';
                document.getElementById('authError').textContent = '';
            }, 3000);
        }
    } catch (err) {
        errorEl.textContent = '网络连接失败，请检查网络后重试';
    }
    btn.disabled = false;
    btn.textContent = isLoginMode ? '登 录' : '注 册';
}

/**
 * 退出登录
 */
export function logout() {
    authToken = null;
    currentUser = null;
    localStorage.removeItem('idphoto_token');
    localStorage.removeItem('idphoto_user');
    checkAuth();
}

/**
 * 初始化认证事件监听
 */
export function initAuthEventListeners(handleAuthFn) {
    document.getElementById('authUsername').addEventListener('keydown', e => {
        if (e.key === 'Enter') {
            document.getElementById('authPassword').focus();
        }
    });

    document.getElementById('authPassword').addEventListener('keydown', e => {
        if (e.key === 'Enter') {
            handleAuthFn();
        }
    });
}
