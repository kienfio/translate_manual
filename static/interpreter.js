// 翻译员音频推流控制器
class InterpreterController {
    constructor() {
        // LiveKit相关
        this.room = null;
        this.localTrack = null;
        this.isConnected = false;
        this.isPublishing = false;
        
        // 音频分析
        this.audioAnalyser = null;
        this.audioContext = null;
        this.micLevelInterval = null;
        
        // DOM元素
        this.languageSelect = document.getElementById('language-select');
        this.startButton = document.getElementById('start-button');
        this.stopButton = document.getElementById('stop-button');
        this.statusContainer = document.getElementById('status-container');
        this.statusText = document.getElementById('status-text');
        this.micLevelBar = document.getElementById('mic-level-bar');
        
        // 初始化事件监听
        this.initEventListeners();
    }
    
    // 初始化事件监听
    initEventListeners() {
        // 开始推流按钮
        this.startButton.addEventListener('click', async () => {
            this.startButton.disabled = true;
            await this.startPublishing();
        });
        
        // 停止推流按钮
        this.stopButton.addEventListener('click', async () => {
            this.stopButton.disabled = true;
            await this.stopPublishing();
        });
    }
    
    // 更新状态显示
    updateStatus(message, status = 'connecting') {
        this.statusContainer.style.display = 'flex';
        this.statusContainer.className = `status-container status-${status}`;
        this.statusText.textContent = message;
        console.log(`[状态] ${message}`);
    }
    
    // 获取当前选择的语言
    getSelectedLanguage() {
        return this.languageSelect.value;
    }
    
    // 获取房间名称
    getRoomName() {
        const language = this.getSelectedLanguage();
        return `room-${language}`;
    }
    
    // 获取翻译员身份标识
    getInterpreterIdentity() {
        const language = this.getSelectedLanguage();
        return `interpreter-${language}-${Date.now()}`;
    }
    
    // 获取访问令牌
    async getToken() {
        const roomName = this.getRoomName();
        const identity = this.getInterpreterIdentity();
        
        try {
            this.updateStatus(`正在获取访问令牌...`, 'connecting');
            
            const response = await fetch(`/token?room=${roomName}&identity=${identity}&is_publisher=true`);
            
            if (!response.ok) {
                throw new Error(`获取令牌失败: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            if (!data.token) {
                throw new Error('令牌不可用');
            }
            
            console.log('获取令牌成功');
            return {
                token: data.token,
                url: data.url,
                room: roomName,
                identity: identity
            };
        } catch (error) {
            this.updateStatus(`获取令牌失败: ${error.message}`, 'error');
            throw error;
        }
    }
    
    // 连接到LiveKit房间
    async connectToRoom() {
        try {
            const tokenData = await this.getToken();
            
            this.updateStatus(`正在连接到房间: ${tokenData.room}...`, 'connecting');
            
            try {
                // 使用新的连接方式
                this.room = await LiveKit.connect(tokenData.url, tokenData.token, {
                    autoSubscribe: true,
                    adaptiveStream: false,
                    dynacast: true,
                    videoCaptureDefaults: {
                        resolution: { width: 0, height: 0 } // 不捕获视频
                    }
                });
                
                // 设置事件监听
                this.room.on(LiveKit.RoomEvent.Disconnected, () => {
                    this.updateStatus('已断开连接', 'error');
                    this.handleDisconnect();
                });
                
                this.room.on(LiveKit.RoomEvent.ConnectionStateChanged, (state) => {
                    console.log(`连接状态变更: ${state}`);
                });
                
                this.isConnected = true;
                this.updateStatus(`已连接到房间: ${tokenData.room}`, 'connected');
                
                return true;
            } catch (error) {
                console.error("连接 LiveKit 失败:", error);
                this.updateStatus(`连接失败: ${error.message}`, 'error');
                alert("连接失败，请刷新页面重试。错误: " + error.message);
                this.handleDisconnect();
                return false;
            }
        } catch (error) {
            this.updateStatus(`连接房间失败: ${error.message}`, 'error');
            this.handleDisconnect();
            alert(`连接失败: ${error.message}`);
            return false;
        }
    }
    
    // 获取麦克风权限并创建音频轨道
    async createMicrophoneTrack() {
        try {
            this.updateStatus('正在请求麦克风权限...', 'connecting');
            
            // 请求麦克风权限并创建音频轨道
            this.localTrack = await LiveKit.createLocalAudioTrack({
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true
            });
            
            this.updateStatus('麦克风权限已获取', 'connected');
            
            // 设置音频分析器
            this.setupAudioAnalyser();
            
            return this.localTrack;
        } catch (error) {
            this.updateStatus(`获取麦克风权限失败: ${error.message}`, 'error');
            throw error;
        }
    }
    
    // 设置音频分析器以显示音量
    setupAudioAnalyser() {
        if (!this.localTrack) return;
        
        try {
            // 创建音频上下文和分析器
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const mediaStreamSource = this.audioContext.createMediaStreamSource(this.localTrack.mediaStream);
            this.audioAnalyser = this.audioContext.createAnalyser();
            this.audioAnalyser.fftSize = 256;
            mediaStreamSource.connect(this.audioAnalyser);
            
            // 开始更新音量显示
            this.startMicLevelUpdates();
        } catch (error) {
            console.error('设置音频分析器失败:', error);
        }
    }
    
    // 开始更新麦克风音量显示
    startMicLevelUpdates() {
        if (!this.audioAnalyser) return;
        
        const dataArray = new Uint8Array(this.audioAnalyser.frequencyBinCount);
        
        this.micLevelInterval = setInterval(() => {
            this.audioAnalyser.getByteFrequencyData(dataArray);
            
            // 计算平均音量
            let sum = 0;
            for (let i = 0; i < dataArray.length; i++) {
                sum += dataArray[i];
            }
            const average = sum / dataArray.length;
            
            // 更新音量显示
            const level = Math.min(100, Math.max(0, average * 1.5));
            this.micLevelBar.style.width = `${level}%`;
        }, 100);
    }
    
    // 停止更新麦克风音量显示
    stopMicLevelUpdates() {
        if (this.micLevelInterval) {
            clearInterval(this.micLevelInterval);
            this.micLevelInterval = null;
        }
        
        if (this.micLevelBar) {
            this.micLevelBar.style.width = '0%';
        }
    }
    
    // 发布音频轨道
    async publishTrack() {
        if (!this.room || !this.localTrack) {
            throw new Error('房间或音频轨道未准备好');
        }
        
        try {
            this.updateStatus('正在发布音频轨道...', 'connecting');
            
            // 发布音频轨道
            await this.room.localParticipant.publishTrack(this.localTrack);
            
            this.isPublishing = true;
            this.updateStatus('音频已开始推流', 'connected');
            
            return true;
        } catch (error) {
            this.updateStatus(`发布音频轨道失败: ${error.message}`, 'error');
            throw error;
        }
    }
    
    // 开始推流
    async startPublishing() {
        try {
            // 连接到房间
            await this.connectToRoom();
            
            // 获取麦克风权限
            await this.createMicrophoneTrack();
            
            // 发布音频轨道
            await this.publishTrack();
            
            // 更新UI
            this.startButton.disabled = true;
            this.stopButton.disabled = false;
            this.languageSelect.disabled = true;
            
            return true;
        } catch (error) {
            console.error('开始推流失败:', error);
            this.startButton.disabled = false;
            return false;
        }
    }
    
    // 停止推流
    async stopPublishing() {
        try {
            this.updateStatus('正在停止推流...', 'connecting');
            
            // 停止音量显示更新
            this.stopMicLevelUpdates();
            
            // 停止并释放音频轨道
            if (this.localTrack) {
                this.localTrack.stop();
                
                if (this.isConnected && this.room && this.room.localParticipant) {
                    await this.room.localParticipant.unpublishTrack(this.localTrack);
                }
                
                this.localTrack = null;
            }
            
            // 断开房间连接
            if (this.room) {
                await this.room.disconnect();
                this.room = null;
            }
            
            this.isConnected = false;
            this.isPublishing = false;
            
            // 更新UI
            this.updateStatus('推流已停止', 'connecting');
            this.startButton.disabled = false;
            this.stopButton.disabled = true;
            this.languageSelect.disabled = false;
            
            // 延迟后隐藏状态
            setTimeout(() => {
                this.statusContainer.style.display = 'none';
            }, 3000);
            
            return true;
        } catch (error) {
            console.error('停止推流失败:', error);
            this.updateStatus(`停止推流失败: ${error.message}`, 'error');
            this.stopButton.disabled = false;
            return false;
        }
    }
    
    // 处理断开连接
    handleDisconnect() {
        this.stopMicLevelUpdates();
        
        if (this.localTrack) {
            this.localTrack.stop();
            this.localTrack = null;
        }
        
        this.isConnected = false;
        this.isPublishing = false;
        
        this.startButton.disabled = false;
        this.stopButton.disabled = true;
        this.languageSelect.disabled = false;
    }
}

// 页面加载完成时初始化
document.addEventListener('DOMContentLoaded', () => {
    window.interpreterController = new InterpreterController();
});
