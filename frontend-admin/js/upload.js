/**
 * 上传 / 处理 / 导出模块
 * 处理照片上传、AI 处理步骤、单张照片导出
 */

import { getSessionId, setSessionId } from './app-state.js';
import { apiUpload, apiProcess, apiExport, handleAuthError } from './api.js';
import { showModal, setStatus, showLoading, showImage, updateLog } from './ui.js';

const allowedTypes = ['image/jpeg', 'image/png', 'image/bmp', 'image/webp'];
const maxSize = 10 * 1024 * 1024;

export function triggerUpload() {
    document.getElementById('fileInput').click();
}

export function bindUploadEvents() {
    const uploadZone = document.getElementById('uploadZone');
    uploadZone.addEventListener('dragover', e => { e.preventDefault(); uploadZone.classList.add('dragover'); });
    uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
    uploadZone.addEventListener('drop', e => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) uploadFile(e.dataTransfer.files[0]);
    });
    const fileInput = document.getElementById('fileInput');
    fileInput.addEventListener('change', e => {
        if (e.target.files.length > 0) uploadFile(e.target.files[0]);
    });
}

async function uploadFile(file) {
    if (!allowedTypes.includes(file.type)) {
        showModal('不支持的文件格式，请上传 JPG/PNG/BMP/WebP 格式的图片', { type: 'warning', title: '文件格式错误' });
        return;
    }
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
        const { res, data } = await apiUpload(formData);
        if (handleAuthError(res)) { showLoading(false); return; }
        if (!res.ok) { showModal('网络连接失败，请检查网络后重试', { type: 'error', title: '上传失败' }); setStatus('上传失败'); showLoading(false); return; }
        if (data.error) { showModal(data.error, { type: 'error', title: '上传失败' }); setStatus('上传失败'); showLoading(false); return; }

        setSessionId(data.session_id);
        showImage('originalImg', data.original);
        document.getElementById('uploadZone').classList.add('hidden');
        document.getElementById('originalImg').classList.remove('hidden');
        showImage('resultImg', data.preview);
        document.getElementById('resultPlaceholder').classList.add('hidden');
        document.getElementById('resultImg').classList.remove('hidden');
        updateLog(data.log);

        const msg = data.has_face
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

export async function doAction(action) {
    const sid = getSessionId();
    if (!sid) { showModal('请先上传一张照片，再进行处理操作', { type: 'warning', title: '温馨提示' }); return; }

    const bgColor = document.querySelector('input[name="bgColor"]:checked').value;
    const size = document.querySelector('input[name="photoSize"]:checked').value;

    setStatus('正在处理中，请稍候...');
    showLoading(true);

    const body = { session_id: sid, action };
    if (action === 'replace_background') body.bg_color = bgColor;
    if (action === 'crop') body.size = size;
    if (action === 'auto') { body.bg_color = bgColor; body.size = size; }

    try {
        const { res, data } = await apiProcess(sid, action, { ...body });
        if (handleAuthError(res)) { showLoading(false); return; }
        if (data.error) {
            const tips = {
                detect: '人脸检测失败，请确认照片中包含清晰的正面人脸',
                replace_background: '背景替换失败，请尝试重新上传照片',
                remove_glasses: '眼镜消除失败，请确认照片中人脸清晰可见',
                enhance: '画质增强失败，请尝试重新上传照片',
                crop: '裁剪失败，请先确认已检测到人脸',
                auto: '一键处理失败，请尝试分步操作排查问题',
                reset: '重置失败，请刷新页面后重试',
            };
            showModal(tips[action] || data.error, { type: 'error', title: '处理失败' });
            setStatus('处理失败');
            showLoading(false);
            return;
        }
        showImage('resultImg', data.preview);
        document.getElementById('resultPlaceholder').classList.add('hidden');
        document.getElementById('resultImg').classList.remove('hidden');
        updateLog(data.log);
        const actionNames = {
            detect: '人脸检测完成', replace_background: '背景替换完成',
            remove_glasses: '眼镜消除完成', enhance: '画质增强完成',
            crop: '裁剪完成', auto: '一键处理完成', reset: '已重置',
        };
        setStatus(actionNames[action] || '处理完成');
    } catch (err) {
        showModal('网络连接失败，请检查网络后重试', { type: 'error', title: '处理失败' });
        setStatus('处理出错');
    }
    showLoading(false);
}

export async function resetPhoto() {
    const sid = getSessionId();
    if (!sid) return;
    await doAction('reset');
}

export async function exportPhoto() {
    const sid = getSessionId();
    if (!sid) { showModal('请先上传并处理照片，再进行导出', { type: 'warning', title: '温馨提示' }); return; }
    setStatus('正在导出...');
    try {
        const { res } = await apiExport(sid);
        if (handleAuthError(res)) return;
        if (!res.ok) {
            const d = await res.json();
            showModal(d.error || '导出失败，请稍后重试', { type: 'error', title: '导出失败' });
            return;
        }
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = '证件照.jpg'; a.click();
        URL.revokeObjectURL(url);
        setStatus('导出成功');
    } catch (err) {
        showModal('网络连接失败，请检查网络后重试', { type: 'error', title: '导出失败' });
    }
}
