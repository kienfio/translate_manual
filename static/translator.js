// LiveKit 客户端实例
let room;

// UI 元素
const identityBanner = document.getElementById('identityBanner');
const statusBar = document.getElementById('statusBar');
const errorMessage = document.getElementById('errorMessage');

// 获取 URL 参数
const urlParams = new URLSearchParams(window.location.search);
const roomName = urlParams.get('room');
const identity = urlParams.get('identity');

// 身份显示映射
const identityDisplayMap = {
    'zh_to_en_interpreter': '中文 → 英文',
    'en_to_zh_interpreter': '英文 → 中文'
};

// 显示错误信息
function showError(message) {
    errorMessage.textContent = message;
    errorMessage.style.display = 'block';
    statusBar.className = 'status-bar error';
    statusBar.textContent = '连接失败';
}

// 更新连接状态
function updateStatus(status, message) {
    statusBar.className = `status-bar ${status}`;
    statusBar.textContent = message;
}

// 更新身份显示
function updateIdentityBanner() {
    const displayIdentity = identityDisplayMap[identity] || '未知身份';
    identityBanner.textContent = `🎙️ 翻译员：${displayIdentity}`;
}

// 初始化 LiveKit 连接
async function initializeLiveKit() {
    try {
        // 验证必要参数
        if (!roomName || !identity) {
            throw new Error('缺少必要的房间或身份参数');
        }

        updateIdentityBanner();
        updateStatus('connecting', '正在连接...');

        // 获取 Token
        const tokenResponse = await fetch(`/token?room=${roomName}&identity=${identity}&is_publisher=true`);
        if (!tokenResponse.ok) {
            throw new Error('Token 获取失败');
        }
        const { token } = await tokenResponse.json();

        // 创建 LiveKit 房间
        room = new LiveKit.Room();

        // 连接到房间
        await room.connect(token);
        updateStatus('connected', '已连接');

        // 请求麦克风权限
        const micTrack = await LiveKit.createLocalAudioTrack();
        await room.localParticipant.publishTrack(micTrack);

        // 监听连接状态
        room.on('disconnected', () => {
            updateStatus('error', '连接已断开');
        });

        room.on('connected', () => {
            updateStatus('connected', '已连接');
        });

    } catch (error) {
        console.error('LiveKit 初始化错误:', error);
        if (error.name === 'NotAllowedError') {
            showError('请允许访问麦克风以开始翻译');
        } else {
            showError(error.message || '连接失败，请刷新页面重试');
        }
    }
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', initializeLiveKit); 