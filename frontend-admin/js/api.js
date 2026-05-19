/**
 * API 请求封装模块
 * 统一处理 Authorization Header 和错误分支
 */

import { getApiBase, getAuthToken, clearSession } from './app-state.js';

export function buildAuthHeaders(extra = {}) {
    const token = getAuthToken();
    const headers = { ...extra };
    if (token) headers['Authorization'] = 'Bearer ' + token;
    return headers;
}

export function handleAuthError(res) {
    if (res.status === 401) {
        clearSession();
        return true;
    }
    return false;
}

export async function apiLogin(username, password) {
    const res = await fetch(getApiBase() + '/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
    });
    return { res, data: await res.json() };
}

export async function apiRegister(username, password) {
    const res = await fetch(getApiBase() + '/api/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
    });
    return { res, data: await res.json() };
}

export async function apiUpload(formData) {
    const res = await fetch(getApiBase() + '/api/upload', {
        method: 'POST',
        body: formData,
        headers: buildAuthHeaders(),
    });
    return { res, data: await res.json() };
}

export async function apiProcess(sessionId, action, extra = {}) {
    const body = { session_id: sessionId, action, ...extra };
    const url = action === 'detect' ? '/api/detect' : '/api/process';
    const res = await fetch(getApiBase() + url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...buildAuthHeaders() },
        body: JSON.stringify(body),
    });
    return { res, data: await res.json() };
}

export async function apiExport(sessionId) {
    const res = await fetch(getApiBase() + '/api/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...buildAuthHeaders() },
        body: JSON.stringify({ session_id: sessionId, format: 'jpg' }),
    });
    return { res };
}

export async function apiHistory(type = 'all', limit = 50) {
    const res = await fetch(getApiBase() + '/api/history?type=' + type + '&limit=' + limit, {
        headers: buildAuthHeaders(),
    });
    return { res, data: await res.json() };
}

export async function apiPrintingLayouts() {
    const res = await fetch(getApiBase() + '/api/printing/layouts', {
        headers: buildAuthHeaders(),
    });
    return { res, data: await res.json() };
}

export async function apiPrintingExport(sessionIds, layout) {
    const res = await fetch(getApiBase() + '/api/printing/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...buildAuthHeaders() },
        body: JSON.stringify({ session_ids: sessionIds, layout }),
    });
    return { res, data: await res.json() };
}

export async function apiPrintingDownload(relativePath) {
    const res = await fetch(getApiBase() + relativePath, {
        headers: buildAuthHeaders(),
    });
    return { res, blob: res.ok ? await res.blob() : null };
}
