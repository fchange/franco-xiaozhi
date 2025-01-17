# 实时语音对话服务

该项目旨在通过自动语音识别（ASR）、大语言模型（LLM）和文本转语音（TTS）技术，提供一个高效的实时语音对话服务。该服务可以应用于多种场景，如客户服务、智能助手等。

## 功能特性

- **WebSocket 支持**：通过 WebSocket 协议实现实时双向通信。
- **WebRTC 集成**：利用 WebRTC 技术实现浏览器间的直接通信。
- **SIP 协议兼容**：通过 SIP 协议支持语音通话功能。
- **音频保存**：支持将处理后的音频文件保存到指定目录。
- **多模块架构**：项目分为多个模块，便于管理和扩展。

## 目录结构

```
.
├── client
│   ├── client_ws.py
│   └── html
│       └── ws.html
├── server
│   ├── __init__.py
│   ├── server_ws.py
│   ├── modules
│   │   ├── __init__.py
│   │   ├── asr_server.py
│   │   ├── audio_saver.py
│   │   ├── base_handler.py
│   │   ├── test.wav
│   │   ├── test51.wav
│   │   ├── test112.wav
│   │   ├── test132.wav
│   │   └── vad_handler.py
│   └── server.log
├── utils
│   ├── __init__.py
│   ├── pipeline_manager.py
│   └── thread_manager.py
├── README.md
├── requirements.txt
├── t.mp3
└── vad_flow.puml
```

## 快速开始

### 启动服务器

#### 使用默认配置

```bash
python server/server_ws.py
```

#### 自定义配置

```bash
python server/server_ws.py --host 0.0.0.0 --port 8080 --audio-save-dir my_audio
```

### 运行客户端

```bash
python .\client\python\websocket\audio_client.py --audio-file 天龙八部0107.wav
```

## 项目依赖

请确保安装了所有必要的依赖项：

```bash
pip install -r requirements.txt
```

## 贡献指南

欢迎贡献代码！请遵循以下步骤：

1. 克隆项目仓库。
2. 创建一个新的分支。
3. 提交更改。
4. 发起 Pull Request。

## 联系我们

如有任何问题或建议，请联系项目维护者。

邮箱：support@example.com
GitHub：https://github.com/yourusername/realtime-voice-dialogue-service
