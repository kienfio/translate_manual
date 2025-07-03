// LiveKit音频播放器
class LiveKitAudioPlayer {
    constructor() {
        this.room = null;
        this.participants = new Map();
        this.isConnected = false;
        this.currentRoom = '';
        this.audioElements = new Map();
        
        // UI元素
        this.statusElement = document.getElementById('connection-status');
        this.volumeSlider = document.getElementById('volume-slider');
        
        // 初始化事件监听器
        this.initEventListeners();
    }
    
    initEventListeners() {
        // 音量控制
        if (this.volumeSlider) {
            this.volumeSlider.addEventListener('input', (e) => {
                const volume = parseFloat(e.target.value);
                this.setGlobalVolume(volume);
            });
        }
    }
    
    // 设置全局音量
    setGlobalVolume(volume) {
        this.audioElements.forEach((audio) => {
            audio.volume = volume;
        });
    }
    
    // 更新连接状态UI
    updateStatus(message, isError = false) {
        if (this.statusElement) {
            this.statusElement.textContent = message;
            this.statusElement.className = isError ? 'error' : 'connected';
        }
        console.log(message);
    }
    
    // 连接到LiveKit房间
    async connect(url, token, roomName) {
        try {
            if (this.isConnected) {
                await this.disconnect();
            }
            
            this.currentRoom = roomName;
            this.updateStatus(`正在连接到 ${roomName}...`);
            
            // 创建并连接到房间
            this.room = new LivekitClient.Room();
            
            // 设置事件监听器
            this.room.on(LivekitClient.RoomEvent.ParticipantConnected, this.handleParticipantConnected.bind(this));
            this.room.on(LivekitClient.RoomEvent.ParticipantDisconnected, this.handleParticipantDisconnected.bind(this));
            this.room.on(LivekitClient.RoomEvent.TrackSubscribed, this.handleTrackSubscribed.bind(this));
            this.room.on(LivekitClient.RoomEvent.TrackUnsubscribed, this.handleTrackUnsubscribed.bind(this));
            this.room.on(LivekitClient.RoomEvent.Disconnected, () => {
                this.updateStatus('已断开连接', true);
                this.isConnected = false;
            });
            
            // 连接到房间
            await this.room.connect(url, token);
            
            // 自动订阅轨道
            await this.room.localParticipant.setAutoSubscribe(true);
            
            this.isConnected = true;
            this.updateStatus(`已连接到 ${roomName}`);
            
            return true;
        } catch (error) {
            this.updateStatus(`连接失败: ${error.message}`, true);
            console.error('连接错误:', error);
            return false;
        }
    }
    
    // 断开连接
    async disconnect() {
        if (this.room) {
            this.updateStatus('正在断开连接...');
            
            // 移除所有音频元素
            this.audioElements.forEach((audio, trackSid) => {
                document.body.removeChild(audio);
            });
            this.audioElements.clear();
            
            // 断开房间连接
            await this.room.disconnect();
            this.room = null;
            this.isConnected = false;
            this.updateStatus('已断开连接');
        }
    }
    
    // 处理参与者连接
    handleParticipantConnected(participant) {
        console.log('参与者已连接:', participant.identity);
        this.participants.set(participant.sid, participant);
    }
    
    // 处理参与者断开
    handleParticipantDisconnected(participant) {
        console.log('参与者已断开:', participant.identity);
        this.participants.delete(participant.sid);
    }
    
    // 处理轨道订阅
    handleTrackSubscribed(track, publication, participant) {
        if (track.kind === 'audio') {
            console.log(`已订阅音频轨道: ${participant.identity}`);
            
            // 创建音频元素
            const audioElement = track.attach();
            audioElement.controls = false;
            audioElement.style.display = 'none';
            
            // 设置初始音量
            if (this.volumeSlider) {
                audioElement.volume = parseFloat(this.volumeSlider.value);
            }
            
            // 将音频元素添加到DOM
            document.body.appendChild(audioElement);
            this.audioElements.set(track.sid, audioElement);
            
            // 更新状态
            this.updateStatus(`正在播放 ${this.currentRoom} 频道`);
        }
    }
    
    // 处理轨道取消订阅
    handleTrackUnsubscribed(track) {
        if (track.kind === 'audio') {
            console.log(`已取消订阅音频轨道: ${track.sid}`);
            
            // 移除音频元素
            const audioElement = this.audioElements.get(track.sid);
            if (audioElement) {
                track.detach(audioElement);
                document.body.removeChild(audioElement);
                this.audioElements.delete(track.sid);
            }
        }
    }
    
    // 静音/取消静音
    toggleMute() {
        let isMuted = false;
        
        this.audioElements.forEach((audio) => {
            audio.muted = !audio.muted;
            isMuted = audio.muted;
        });
        
        return isMuted;
    }
}

// 连接到特定语言频道
async function connectToChannel(language) {
    // 获取UI元素
    const connectButton = document.getElementById('connect-button');
    const muteButton = document.getElementById('mute-button');
    const languageSelector = document.getElementById('language-selector');
    const playerContainer = document.getElementById('player-container');
    
    if (connectButton) {
        connectButton.disabled = true;
    }
    
    // 设置房间名称
    const roomName = `room-${language}`;
    const identity = `audience-${Date.now()}`;
    
    try {
        // 获取访问令牌
        const response = await fetch(`/token?room=${roomName}&identity=${identity}`);
        
        if (!response.ok) {
            throw new Error(`无法获取令牌: ${response.statusText}`);
        }
        
        const data = await response.json();
        const token = data.token;
        
        if (!token) {
            throw new Error('令牌不可用');
        }
        
        // 初始化播放器
        if (!window.audioPlayer) {
            window.audioPlayer = new LiveKitAudioPlayer();
        }
        
        // 连接到LiveKit房间
        const liveKitUrl = data.url || 'wss://your-project.livekit.cloud';
        const success = await window.audioPlayer.connect(liveKitUrl, token, roomName);
        
        if (success) {
            // 显示播放器UI
            if (playerContainer) {
                playerContainer.style.display = 'flex';
            }
            
            // 禁用语言选择器
            if (languageSelector) {
                const buttons = languageSelector.querySelectorAll('button');
                buttons.forEach(btn => {
                    if (btn.dataset.language === language) {
                        btn.classList.add('active');
                    } else {
                        btn.classList.remove('active');
                    }
                });
            }
            
            // 更新连接按钮
            if (connectButton) {
                connectButton.textContent = '断开连接';
                connectButton.disabled = false;
                connectButton.onclick = disconnectFromChannel;
            }
            
            // 启用静音按钮
            if (muteButton) {
                muteButton.disabled = false;
                muteButton.onclick = toggleMute;
            }
            
            // 更新URL参数，但不刷新页面
            updateUrlParam('lang', language);
        } else {
            if (connectButton) {
                connectButton.disabled = false;
            }
        }
    } catch (error) {
        console.error('连接错误:', error);
        alert(`连接错误: ${error.message}`);
        
        if (connectButton) {
            connectButton.disabled = false;
        }
    }
}

// 断开连接
async function disconnectFromChannel() {
    const connectButton = document.getElementById('connect-button');
    const muteButton = document.getElementById('mute-button');
    const playerContainer = document.getElementById('player-container');
    
    if (connectButton) {
        connectButton.disabled = true;
    }
    
    try {
        if (window.audioPlayer) {
            await window.audioPlayer.disconnect();
        }
        
        // 隐藏播放器UI
        if (playerContainer) {
            playerContainer.style.display = 'none';
        }
        
        // 更新连接按钮
        if (connectButton) {
            connectButton.textContent = '连接';
            connectButton.disabled = false;
            connectButton.onclick = () => {
                const activeButton = document.querySelector('#language-selector button.active');
                if (activeButton) {
                    connectToChannel(activeButton.dataset.language);
                } else {
                    alert('请先选择一种语言');
                }
            };
        }
        
        // 禁用静音按钮
        if (muteButton) {
            muteButton.disabled = true;
        }
        
        // 移除URL参数
        removeUrlParam('lang');
    } catch (error) {
        console.error('断开连接错误:', error);
        
        if (connectButton) {
            connectButton.disabled = false;
        }
    }
}

// 切换静音
function toggleMute() {
    const muteButton = document.getElementById('mute-button');
    
    if (window.audioPlayer) {
        const isMuted = window.audioPlayer.toggleMute();
        
        if (muteButton) {
            muteButton.textContent = isMuted ? '取消静音' : '静音';
        }
    }
}

// 选择语言
function selectLanguage(language) {
    const languageSelector = document.getElementById('language-selector');
    
    if (languageSelector) {
        const buttons = languageSelector.querySelectorAll('button');
        buttons.forEach(btn => {
            if (btn.dataset.language === language) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
    }
    
    // 如果已连接，则断开并重新连接
    if (window.audioPlayer && window.audioPlayer.isConnected) {
        disconnectFromChannel().then(() => {
            connectToChannel(language);
        });
    }
}

// 获取URL参数
function getUrlParam(param) {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get(param);
}

// 更新URL参数，不刷新页面
function updateUrlParam(key, value) {
    const url = new URL(window.location.href);
    url.searchParams.set(key, value);
    window.history.pushState({}, '', url);
}

// 移除URL参数，不刷新页面
function removeUrlParam(key) {
    const url = new URL(window.location.href);
    url.searchParams.delete(key);
    window.history.pushState({}, '', url);
}

// 生成二维码
function generateQRCodes() {
    const languages = ['en', 'vi', 'id', 'kr'];
    const baseUrl = window.location.origin + window.location.pathname;
    
    languages.forEach(lang => {
        const qrCanvas = document.getElementById(`qrcode-${lang}`);
        if (qrCanvas) {
            const qrUrl = `${baseUrl}?lang=${lang}`;
            QRCode.toCanvas(qrCanvas, qrUrl, {
                width: 128,
                margin: 1,
                color: {
                    dark: '#4a6cf7',
                    light: '#ffffff'
                }
            }, function(error) {
                if (error) console.error(`生成${lang}二维码失败:`, error);
            });
        }
    });
}

// 检查URL参数并自动连接
function checkUrlAndAutoConnect() {
    const langParam = getUrlParam('lang');
    
    if (langParam) {
        const validLanguages = ['en', 'vi', 'id', 'kr'];
        if (validLanguages.includes(langParam)) {
            // 选择对应的语言
            selectLanguage(langParam);
            
            // 自动连接
            setTimeout(() => {
                connectToChannel(langParam);
            }, 500);
        }
    }
}

// 页面加载完成时初始化
document.addEventListener('DOMContentLoaded', () => {
    const languageButtons = document.querySelectorAll('#language-selector button');
    const connectButton = document.getElementById('connect-button');
    
    // 设置语言按钮点击事件
    languageButtons.forEach(button => {
        button.addEventListener('click', () => {
            selectLanguage(button.dataset.language);
        });
    });
    
    // 设置连接按钮点击事件
    if (connectButton) {
        connectButton.addEventListener('click', () => {
            const activeButton = document.querySelector('#language-selector button.active');
            if (activeButton) {
                connectToChannel(activeButton.dataset.language);
            } else {
                alert('请先选择一种语言');
            }
        });
    }
    
    // 生成二维码
    generateQRCodes();
    
    // 检查URL参数并自动连接
    checkUrlAndAutoConnect();
}); 
