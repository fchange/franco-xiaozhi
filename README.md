# 实时语音对话服务

该项目主要用于基于 ASR（自动语音识别）、LLM（大语言模型）和 TTS（文本转语音）提供一个实时语音对话服务。

## 特性

- 支持 WebSocket 协议
- 支持 WebRTC
- 支持 SIP 协议

## 目录结构

## command
### 使用默认配置
python server/server_ws.py

#### 或者自定义配置
python server/server_ws.py --host 0.0.0.0 --port 8080 --audio-save-dir my_audio
