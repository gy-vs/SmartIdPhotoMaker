/**
 * 照片处理模块
 * 上传、处理、导出
 */

import { API, authHeaders, handleAuthError } from './auth.js';
import { showModal, setStatus, showLoading, updateLog, showImage } from './ui.js';

let sessionId = null;

/**
 * 获取当前会话 ID
 * @returns {string|null}
 */
export function getSessionId() {
    return sessionId;
}

/**
 * 触发文件选择对话框
 */
export function triggerUpload() {
    document.getElementById('fileInput').click();
}

/**
 * 处理文件选择
 * @param {Event} e - 文件选择事件
 */
export function handleFileSelect(e) {
    if (e.target.files.length > 0) {
        uploadFile(e.target.files[0]);
    }
}

/**
 * 上传照片
 * @param {File} file - 文件对象
 * @returns {Promise<void>}
 */
export async function uploadFile(file) {
    const allowedTypes = ['image/jpeg', 'image/png', 'image/bmp', 'image/webp'];
    if (!allowedTypes.includes(file.type)) {
        showModal('不支持的文件格式，请上传 JPG/PNG/BMP/WebP 格式的图片', { type: 'warning', title: '文件格式错误' });
        return;
    }

    const maxSize = 10 * 1024 * 1024;
    if (file.size > maxSize) {
        const sizeMB = (file.size / (1024 * 1024)).toFixed(1);
        showModal(`文件大小 (${sizeMB}MB) 超过限制，请上传不超过 10MB 的图片`, { type: 'warning', title: '文件过大' });
        return;
    }

    setStatus('正在上传并分析照片...');
    showLoading(true);

    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch(API + '/api/upload', {
            method: 'POST',
            body: formData,
            headers: authHeaders(),
        });

        if (handleAuthError(res)) {
            showLoading(false);
            return;
        }

        const data = await res.json();

        if (data.error) {
            showModal(data.error, { type: 'error', title: '上传失败' });
            setStatus('上传失败');
            showLoading(false);
            return;
        }

        sessionId = data.session_id;

        showImage('originalImg', data.original);
        document.getElementById('uploadZone').classList.add('hidden');
        document.getElementById('originalImg').classList.remove('hidden');

        showImage('resultImg', data.preview);
        document.getElementById('resultPlaceholder').classList.add('hidden');
        document.getElementById('resultImg').classList.remove('hidden');

        updateLog(data.log);

        let msg = data.has_face
            ? `已加载图片，检测到人脸 (置信度: ${data.confidence})${data.has_glasses ? '，检测到佩戴眼镜' : ''}`
            : '已加载图片，但未检测到人脸，请更换照片';
        setStatus(msg);

        if (!data.has_face) {
            showModal('未检测到人脸，建议上传光线充足、正面清晰的半身照', { type: 'warning', title: '温馨提示' });
        }
    } catch (err) {
        showModal('网络连接失败，请检查网络后重试', { type: 'error', title: '上传失败' });
        setStatus('上传失败');
    }

    showLoading(false);
}

/**
 * 执行处理操作
 * @param {string} action - 操作类型
 * @returns {Promise<void>}
 */
export async function doAction(action) {
    if (!sessionId) {
        showModal('请先上传一张照片，再进行处理操作', { type: 'warning', title: '温馨提示' });
        return;
    }

    const bgColor = document.querySelector('input[name="bgColor"]:checked').value;
    const size = document.querySelector('input[name="photoSize"]:checked').value;

    setStatus('正在处理中，请稍候...');
    showLoading(true);

    const url = action === 'detect' ? API + '/api/detect' : API + '/api/process';
    const body = { session_id: sessionId, action, bg_color: bgColor, size };

    try {
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...authHeaders() },
            body: JSON.stringify(body),
        });

        if (handleAuthError(res)) {
            showLoading(false);
            return;
        }

        const data = await res.json();

        if (data.error) {
            const actionTips = {
                detect: '人脸检测失败，请确认照片中包含清晰的正面人脸',
                replace_background: '背景替换失败，请尝试重新上传照片',
                remove_glasses: '眼镜消除失败，请确认照片中人脸清晰可见',
                enhance: '画质增强失败，请尝试重新上传照片',
                crop: '裁剪失败，请先确认已检测到人脸',
                auto: '一键处理失败，请尝试分步操作排查问题',
                reset: '重置失败，请刷新页面后重试',
            };
            const tip = actionTips[action] || data.error;
            showModal(tip, { type: 'error', title: '处理失败' });
            setStatus('处理失败');
            showLoading(false);
            return;
        }

        showImage('resultImg', data.preview);
        document.getElementById('resultPlaceholder').classList.add('hidden');
        document.getElementById('resultImg').classList.remove('hidden');
        updateLog(data.log);

        const actionNames = {
            detect: '人脸检测完成',
            replace_background: '背景替换完成',
            remove_glasses: '眼镜消除完成',
            enhance: '画质增强完成',
            crop: '裁剪完成',
            auto: '一键处理完成',
            reset: '已重置',
        };
        setStatus(actionNames[action] || '处理完成');
    } catch (err) {
        showModal('网络连接失败，请检查网络后重试', { type: 'error', title: '处理失败' });
        setStatus('处理出错');
    }

    showLoading(false);
}

/**
 * 重置照片
 * @returns {Promise<void>}
 */
export async function resetPhoto() {
    if (!sessionId) return;
    await doAction('reset');
}

/**
 * 导出照片
 * @returns {Promise<void>}
 */
export async function exportPhoto() {
    if (!sessionId) {
        showModal('请先上传并处理照片，再进行导出', { type: 'warning', title: '温馨提示' });
        return;
    }

    setStatus('正在导出...');

    try {
        const res = await fetch(API + '/api/export', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...authHeaders() },
            body: JSON.stringify({ session_id: sessionId, format: 'jpg' }),
        });

        if (handleAuthError(res)) return;

        if (!res.ok) {
            const d = await res.json();
            showModal(d.error || '导出失败，请稍后重试', { type: 'error', title: '导出失败' });
            return;
        }

        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = '证件照.jpg';
        a.click();
        URL.revokeObjectURL(url);
        setStatus('导出成功');
    } catch (err) {
        showModal('网络连接失败，请检查网络后重试', { type: 'error', title: '导出失败' });
    }
}

/**
 * 初始化上传事件监听
 */
export function initUploadEventListeners() {
    const uploadZone = document.getElementById('uploadZone');

    uploadZone.addEventListener('dragover', e => {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    });

    uploadZone.addEventListener('dragleave', () => {
        uploadZone.classList.remove('dragover');
    });

    uploadZone.addEventListener('drop', e => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            uploadFile(e.dataTransfer.files[0]);
        }
    });

    document.getElementById('fileInput').addEventListener('change', handleFileSelect);
}
