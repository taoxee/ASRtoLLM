# [VibeMeet2Notes · 灵感纪要](https://github.com/taoxee/VibeMeet2Notes)

**媒体文件转录与会议纪要工具**

[![中文](https://img.shields.io/badge/中文-red?style=for-the-badge)](README_CN.md) [![English](https://img.shields.io/badge/English-blue?style=for-the-badge)](README_EN.md)

---

上传音视频文件 → ASR 语音识别（说话人分离）→ LLM 自动生成会议纪要

---

## ✨ 功能特性

- 🎙️ **说话人分离** — 自动识别多位说话人，标注 Speaker 1/2/3...
- 📝 **结构化会议纪要** — LLM 输出 Markdown 格式的专业会议纪要（议题、决策、行动项）
- 🔌 **多供应商支持** — 14 家 ASR/LLM 供应商，自由组合
- 💾 **凭证本地存储** — API Key 仅保存在浏览器 localStorage，不经过服务端
- ⚡ **缓存检测** — 相同文件 + 相同供应商自动复用历史结果
- 🌐 **代理自动检测** — 自动识别 macOS 系统代理（ShadowsocksX-NG / ClashX 等）
- 📊 **SSE 实时进度** — 流式进度条，ASR 完成即显示转录，LLM 完成即显示纪要
- 📋 **多任务并行** — 支持多文件同时上传，最多 3 个任务并行处理，队列管理
- 🔢 **Token 用量追踪** — 记录每次 LLM 调用的 token 消耗（输入/输出/合计）
- 🔔 **任务完成通知** — 右上角弹出通知，点击跳转到对应结果
- 🌍 **多语言界面** — 支持中文/英文切换，语言偏好自动保存
- 🔄 **智能转码** — 自动将音视频转为 16kHz 单声道 MP3，减小体积，兼容所有供应商

---

## 🎙️ 说话人分离支持

| 供应商 | 分离支持 | 备注 |
|--------|----------|------|
| Deepgram | ✅ 原生支持 | Nova-2 模型 |
| ElevenLabs | ✅ 原生支持 | Scribe v1 带说话人标签 |
| Soniox | ✅ 原生支持 | 异步分离，说话人追踪 |
| 腾讯云 | ✅ 原生支持 | CreateRecTask 的 SpeakerDiarization |
| 阿里云 | ✅ 原生支持 | DashScope Paraformer-v2 |
| 微软-Global | ✅ 原生支持 | Fast Transcription API |
| 微软-世纪互联 | ✅ 原生支持 | 中国端点 |
| OpenAI / Groq | ⚠️ 仅时间戳 | 单说话人 |
| 火山云 | ⚠️ 仅时间戳 | 单说话人 |
| 讯飞 | ✅ 原生支持 | raasr v2 API |

---

## 📋 供应商支持

| 供应商 | ASR | LLM | TTS | 其他 |
|--------|-----|-----|-----|------|
| 腾讯云 | ✅ | ✅ | ✅ | 声音复刻 |
| 火山云 | ✅ | | ✅ | 声音复刻 |
| 微软-世纪互联 | ✅ | | ✅ | 翻译 |
| Minimax-CN | | ✅ | ✅ | |
| 阿里云 | ✅ | ✅ | ✅ | 声音复刻 |
| Minimax-Global | | ✅ | ✅ | 声音复刻 |
| ElevenLabs | ✅ | | ✅ | 声音复刻 |
| Soniox | ✅ | | | 翻译 |
| 微软-Global | ✅ | | ✅ | 声音复刻/翻译 |
| Groq | | ✅ | | |
| Deepgram | ✅ | | | |
| 智谱 | | ✅ | | |
| 讯飞 | ✅ | | | |
| OpenAI | | ✅ | | |

---

## 🚀 快速开始

### 前提条件

1. **准备 API Key** — 至少需要一个 ASR 供应商和一个 LLM 供应商的 API Key

2. **安装 ffmpeg** — 用于将音视频自动转码为 16kHz 单声道 MP3，减小体积，兼容所有供应商

```bash
# 方式一：pip 安装（最简单，跨平台）
pip install static-ffmpeg

# 方式二：系统包管理器
# macOS
brew install ffmpeg
# Ubuntu / Debian
sudo apt install ffmpeg
# Windows (Chocolatey)
choco install ffmpeg
```

推荐组合（速度快、性价比高）：

| 用途 | 推荐供应商 | 注册地址 |
|------|-----------|---------|
| ASR（语音转文字） | **Deepgram** | https://console.deepgram.com |
| LLM（会议纪要） | **阿里云百炼** | https://bailian.console.aliyun.com |

> 其他支持的供应商见下方「供应商支持」表。API Key 仅存储在你的浏览器本地，不会上传到服务器。

### 安装与启动

```bash
pip install -r requirements.txt
python run.py
```

打开浏览器访问：**http://127.0.0.1:8080**

### 可选：安装 SOCKS 代理支持

如果使用 SOCKS 代理（如 ShadowsocksX-NG），需安装：

```bash
pip install 'requests[socks]'
```

---

## 📖 使用流程

1. 在「供应商凭证管理」中填写 API Key（自动保存到浏览器）
2. 上传音视频文件（mp3 / mp4 / wav / m4a / webm / ogg / flac）
3. 选择 ASR 和 LLM 供应商（仅显示已配置的）
4. 点击「开始处理」— 转录结果和会议纪要会实时显示

---

## 📁 项目结构

```
├── app/                # 核心应用目录
│   ├── __init__.py     # 应用工厂
│   ├── config.py       # 配置（代理、供应商、Prompt）
│   ├── routes.py       # 路由和接口定义
│   ├── services.py     # ASR/LLM 业务逻辑
│   └── utils.py        # 工具函数
├── static/             # 前端静态文件
│   └── index.html
├── data/               # 数据文件
│   ├── ASR_prompt.txt
│   ├── LLM_prompt.txt
│   ├── conversationHist.md
│   └── vendor_keys.csv
├── import_keys.py      # 凭证自动检测脚本
├── run.py              # 项目启动入口
├── requirements.txt
└── README.md
```

## 📁 输出结构

每次任务保存到 `output/<timestamp_id>/`：

```
output/20260228_143052_a1b2c3/
├── meta.json          # 任务元数据
├── source_xxx.mp3     # 源文件副本
├── transcript.txt     # 转录文本（含说话人标注）
├── summary.txt        # 会议纪要
├── asr_log.json       # ASR 原始日志
└── llm_log.json       # LLM 原始日志
```

---

## ⭐ Star History

[![Star History Chart](https://api.star-history.com/svg?repos=taoxee/VibeMeet2Notes&type=Date)](https://star-history.com/#taoxee/VibeMeet2Notes&Date)

---

## License

Apache License 2.0 © [taoxee](https://github.com/taoxee)
