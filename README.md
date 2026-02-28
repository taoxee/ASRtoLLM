# ASRtoLLM

**媒体文件转录与会议纪要工具 | Media Transcription & Meeting Minutes Tool**

上传音视频文件 → ASR 语音识别（说话人分离）→ LLM 自动生成会议纪要

Upload audio/video → ASR transcription (speaker diarization) → LLM-generated meeting minutes

---

## ✨ 功能特性 | Features

- 🎙️ **说话人分离** — 自动识别多位说话人，标注 Speaker 1/2/3...
- 📝 **结构化会议纪要** — LLM 输出 Markdown 格式的专业会议纪要（议题、决策、行动项）
- 🔌 **多供应商支持** — 14 家 ASR/LLM 供应商，自由组合
- 💾 **凭证本地存储** — API Key 仅保存在浏览器 localStorage，不经过服务端
- ⚡ **缓存检测** — 相同文件 + 相同供应商自动复用历史结果
- 🌐 **代理自动检测** — 自动识别 macOS 系统代理（ShadowsocksX-NG / ClashX 等）
- 📊 **SSE 实时进度** — 流式进度条，ASR 完成即显示转录，LLM 完成即显示纪要

---

## 🎙️ Speaker Diarization

- **Deepgram** — native diarization via Nova-2
- **ElevenLabs** — Scribe v1 with speaker labels
- **Soniox** — async diarization with speaker tracking
- **腾讯云** — SpeakerDiarization via CreateRecTask
- **OpenAI / Groq** — Whisper (timestamps only, single speaker)
- **火山云** — timestamps, single speaker

---

## 📋 供应商支持 | Supported Vendors

| 供应商 Vendor | ASR | LLM | TTS | 其他 Other |
|---------------|-----|-----|-----|------------|
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

## 🚀 快速开始 | Quick Start

```bash
pip install -r requirements.txt
python app.py
```

打开浏览器访问 / Open browser at: **http://127.0.0.1:8080**

如果使用 SOCKS 代理（如 ShadowsocksX-NG），需安装：
If using SOCKS proxy (e.g. ShadowsocksX-NG):

```bash
pip install 'requests[socks]'
```

---

## 📖 使用流程 | Usage

1. 在「供应商凭证管理」中填写 API Key（自动保存到浏览器）
   Fill in API keys under "Vendor Credentials" (auto-saved to browser)
2. 上传音视频文件（mp3 / mp4 / wav / m4a / webm / ogg / flac）
   Upload audio/video file
3. 选择 ASR 和 LLM 供应商（仅显示已配置的）
   Select ASR & LLM vendors (only configured ones shown)
4. 点击「开始处理」— 转录结果和会议纪要会实时显示
   Click "Start" — transcript and meeting minutes stream in real-time

---

## 📁 输出结构 | Output Structure

每次任务保存到 `output/<timestamp_id>/`：
Each task saves to `output/<timestamp_id>/`:

```
output/20260228_143052_a1b2c3/
├── meta.json          # 任务元数据 Task metadata
├── source_xxx.mp3     # 源文件副本 Source file copy
├── transcript.txt     # 转录文本（含说话人标注）Diarized transcript
├── summary.txt        # 会议纪要 Meeting minutes
├── asr_log.json       # ASR 原始日志 ASR raw log
└── llm_log.json       # LLM 原始日志 LLM raw log
```

---

## ⭐ Star History


[![Star History Chart](https://api.star-history.com/svg?repos=taoxee/ASRtoLLM&type=Date)](https://star-history.com/#taoxee/ASRtoLLM&Date)

---

## License

MIT
