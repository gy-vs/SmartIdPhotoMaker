/**
 * 应用全局状态管理
 * 所有模块共享的运行时状态集中在此，避免全局变量污染
 */

const state = {
    apiBase: '',
    sessionId: null,
    authToken: localStorage.getItem('idphotoToken') || null,
    currentUser: localStorage.getItem('idphotoUser') || null,
    isLoginMode: true,
    printMode: false,
    printSelected: new Set(),
    modalResolve: null,
};

export function getApiBase() {
    return state.apiBase;
}

export function setSessionId(sid) {
    state.sessionId = sid;
}

export function getSessionId() {
    return state.sessionId;
}

export function setAuthToken(token) {
    state.authToken = token;
    if (token) localStorage.setItem('idphotoToken', token);
    else localStorage.removeItem('idphotoToken');
}

export function getAuthToken() {
    return state.authToken;
}

export function setCurrentUser(user) {
    state.currentUser = user;
    if (user) localStorage.setItem('idphotoUser', user);
    else localStorage.removeItem('idphotoUser');
}

export function getCurrentUser() {
    return state.currentUser;
}

export function setIsLoginMode(mode) {
    state.isLoginMode = mode;
}

export function getIsLoginMode() {
    return state.isLoginMode;
}

export function setPrintMode(mode) {
    state.printMode = mode;
    if (!mode) state.printSelected.clear();
}

export function getPrintMode() {
    return state.printMode;
}

export function addPrintSelected(sid) {
    state.printSelected.add(sid);
}

export function removePrintSelected(sid) {
    state.printSelected.delete(sid);
}

export function clearPrintSelected() {
    state.printSelected.clear();
}

export function getPrintSelected() {
    return state.printSelected;
}

export function hasPrintSelected(sid) {
    return state.printSelected.has(sid);
}

export function setModalResolve(resolve) {
    state.modalResolve = resolve;
}

export function getModalResolve() {
    return state.modalResolve;
}

export function clearSession() {
    state.sessionId = null;
    setAuthToken(null);
    setCurrentUser(null);
}
