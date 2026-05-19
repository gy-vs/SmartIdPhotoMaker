/**
 * 认证模块
 * 处理登录 / 注册 / 登出 / 认证状态恢复
 */

import {
    setAuthToken, setCurrentUser, setIsLoginMode, setSessionId,
    getIsLoginMode, getAuthToken, getCurrentUser, clearSession,
} from './app-state.js';
import { apiLogin, apiRegister } from './api.js';
import { showModal, showToast } from './ui.js';

export function checkAuth() {
    const token = getAuthToken();
    const user = getCurrentUser();
    if (token && user) {
        document.getElementById('authPage').classList.add('hidden');
        document.getElementById('userInfo').textContent = '👤 ' + user;
    } else {
        document.getElementById('authPage').classList.remove('hidden');
    }
}

export function toggleAuthMode() {
    const mode = !getIsLoginMode();
    setIsLoginMode(mode);
    document.getElementById('authError').textContent = '';
    document.getElementById('authUsername').value = '';
    document.getElementById('authPassword').value = '';
    if (mode) {
        document.getElementById('authSubtitle').textContent = '登录后开始制作证件照';
        document.getElementById('authSubmitBtn').textContent = '登 录';
        document.getElementById('authSwitch').innerHTML = '还没有账号？<a data-action="switch">立即注册</a>';
        document.getElementById('authPassword').setAttribute('autocomplete', 'current-password');
    } else {
        document.getElementById('authSubtitle').textContent = '注册新账号';
        document.getElementById('authSubmitBtn').textContent = '注 册';
        document.getElementById('authSwitch').innerHTML = '已有账号？<a data-action="switch">返回登录</a>';
        document.getElementById('authPassword').setAttribute('autocomplete', 'new-password');
    }
}

export async function handleAuth() {
    const username = document.getElementById('authUsername').value.trim();
    const password = document.getElementById('authPassword').value;
    const errorEl = document.getElementById('authError');
    errorEl.textContent = '';

    if (!username) { errorEl.textContent = '请输入用户名'; return; }
    if (!password) { errorEl.textContent = '请输入密码'; return; }

    const mode = getIsLoginMode();
    const url = mode ? 'login' : 'register';
    const btn = document.getElementById('authSubmitBtn');
    btn.disabled = true;
    btn.textContent = mode ? '登录中...' : '注册中...';

    try {
        let result;
        if (mode) {
            result = await apiLogin(username, password);
        } else {
            result = await apiRegister(username, password);
        }
        const { res, data } = result;

        if (!res.ok || data.error) {
            errorEl.textContent = data.error || '操作失败，请重试';
            btn.disabled = false;
            btn.textContent = mode ? '登 录' : '注 册';
            return;
        }

        if (mode) {
            setAuthToken(data.token);
            setCurrentUser(data.username);
            checkAuth();
        } else {
            errorEl.style.color = '#0d652d';
            errorEl.textContent = '注册成功，请登录';
            setTimeout(() => {
                errorEl.style.color = '#d93025';
                errorEl.textContent = '';
            }, 3000);
            setIsLoginMode(true);
            toggleAuthMode();
            toggleAuthMode();
        }
    } catch (err) {
        errorEl.textContent = '网络连接失败，请检查网络后重试';
    }
    btn.disabled = false;
    btn.textContent = getIsLoginMode() ? '登 录' : '注 册';
}

export function logout() {
    clearSession();
    checkAuth();
}

export function bindAuthEvents() {
    document.getElementById('authUsername').addEventListener('keydown', e => {
        if (e.key === 'Enter') document.getElementById('authPassword').focus();
    });
    document.getElementById('authPassword').addEventListener('keydown', e => {
        if (e.key === 'Enter') handleAuth();
    });
    document.getElementById('authSwitch').addEventListener('click', e => {
        if (e.target.dataset && e.target.dataset.action === 'switch') {
            toggleAuthMode();
        }
    });
}
