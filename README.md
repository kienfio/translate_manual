# 实时翻译服务

基于 LiveKit 的实时音频翻译服务，支持多语言频道（英语、越南语、印尼语、韩语）。

## 功能特点

- 支持四种语言频道: 英语、越南语、印尼语、韩语
- 观众可自由选择语言并收听
- 翻译员可通过麦克风或音频文件推流到指定语言频道
- 现代化Web界面，支持移动设备
- 音量控制和静音功能
- 为Render平台设计的易部署架构

## 项目结构

```
├── main.py            # FastAPI项目入口
├── token_generator.py # 生成LiveKit房间访问Token
├── uploader.py        # 上传翻译员音频到房间
├── templates/         # HTML模板
│   └── index.html     # 观众语言选择页面
├── static/            # 静态资源
│   └── player.js      # LiveKit音频播放器JS
└── requirements.txt   # 依赖包清单
```

## 环境变量

在Render部署时，需要配置以下环境变量：

```
LIVEKIT_API_KEY=your_api_key_here
LIVEKIT_SECRET=your_secret_key_here
LIVEKIT_URL=wss://your-project.livekit.cloud
PORT=8000  # 可选，默认为8000
```

## 安装与运行

1. 克隆代码库
2. 安装依赖: `pip install -r requirements.txt`
3. 设置环境变量
4. 运行服务: `python main.py`

## 观众使用方法

1. 访问网站主页
2. 选择所需语言（英语、越南语、印尼语、韩语）
3. 点击"连接"按钮
4. 开始收听翻译音频

## 翻译员使用方法

使用uploader.py脚本将音频推流至指定房间：

### 使用麦克风

```bash
python uploader.py --room room-en --identity translator-en --source mic
```

### 使用音频文件

```bash
python uploader.py --room room-en --identity translator-en --source file --file path/to/audio.wav
```

## 在Render上部署

1. 在Render创建新的Web Service
2. 连接到GitHub仓库
3. 选择Python运行时
4. 启动命令: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. 添加所需环境变量
6. 部署

## 技术栈

- FastAPI: Web框架
- LiveKit: 实时音频流服务
- Jinja2: HTML模板
- JavaScript: 前端交互

## 注意事项

- 所有音频文件必须是WAV格式
- 翻译员需要稳定的网络连接以确保音频质量
- 确保LiveKit配置正确并可访问 