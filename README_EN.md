# [VibeMeet2Notes](https://github.com/taoxee/VibeMeet2Notes)

**Media Transcription & Meeting Minutes Tool**

[![中文](https://img.shields.io/badge/中文-red?style=for-the-badge)](README_CN.md) [![English](https://img.shields.io/badge/English-blue?style=for-the-badge)](README_EN.md)

---

Upload audio/video → ASR transcription (speaker diarization) → LLM-generated meeting minutes

---

## ✨ Features

- 🎙️ **Speaker Diarization** — Auto-identify multiple speakers, labeled as Speaker 1/2/3...
- 📝 **Structured Meeting Minutes** — LLM outputs professional Markdown meeting notes (topics, decisions, action items)
- 🔌 **Multi-Vendor Support** — 14 ASR/LLM vendors, mix and match freely
- 💾 **Local Credential Storage** — API keys stored only in browser localStorage, never sent to server
- ⚡ **Cache Detection** — Auto-reuse historical results for same file + same vendor
- 🌐 **Auto Proxy Detection** — Detects macOS system proxy (ShadowsocksX-NG / ClashX etc.)
- 📊 **SSE Real-time Progress** — Streaming progress bar, transcript shows when ASR completes, minutes show when LLM completes
- 📋 **Multi-task Parallel** — Upload multiple files, up to 3 tasks processed in parallel with queue management
- 🔢 **Token Usage Tracking** — Records token consumption for each LLM call (input/output/total)
- 🔔 **Task Completion Notification** — Pop-up notification in top-right corner, click to jump to result

---

## 🎙️ Speaker Diarization Support

| Vendor | Diarization | Notes |
|--------|-------------|-------|
| Deepgram | ✅ Native | Nova-2 model |
| ElevenLabs | ✅ Native | Scribe v1 with speaker labels |
| Soniox | ✅ Native | Async diarization with speaker tracking |
| 腾讯云 | ✅ Native | SpeakerDiarization via CreateRecTask |
| 阿里云 | ✅ Native | DashScope Paraformer-v2 |
| 微软-Global | ✅ Native | Fast Transcription API |
| 微软-世纪互联 | ✅ Native | China endpoint |
| OpenAI / Groq | ⚠️ Timestamps only | Single speaker |
| 火山云 | ⚠️ Timestamps only | Single speaker |
| 讯飞 | ✅ Native | raasr v2 API |

---

## 📋 Supported Vendors

| Vendor | ASR | LLM | TTS | Other |
|--------|-----|-----|-----|-------|
| 腾讯云 | ✅ | ✅ | ✅ | Voice Clone |
| 火山云 | ✅ | | ✅ | Voice Clone |
| 微软-世纪互联 | ✅ | | ✅ | Translation |
| Minimax-CN | | ✅ | ✅ | |
| 阿里云 | ✅ | ✅ | ✅ | Voice Clone |
| Minimax-Global | | ✅ | ✅ | Voice Clone |
| ElevenLabs | ✅ | | ✅ | Voice Clone |
| Soniox | ✅ | | | Translation |
| 微软-Global | ✅ | | ✅ | Voice Clone/Translation |
| Groq | | ✅ | | |
| Deepgram | ✅ | | | |
| 智谱 | | ✅ | | |
| 讯飞 | ✅ | | | |
| OpenAI | | ✅ | | |

---

## 🚀 Quick Start

```bash
pip install -r requirements.txt
python run.py
```

Open browser at: **http://127.0.0.1:8080**

If using SOCKS proxy (e.g. ShadowsocksX-NG):

```bash
pip install 'requests[socks]'
```

---

## 📖 Usage

1. Fill in API keys under "Vendor Credentials" (auto-saved to browser)
2. Upload audio/video file (mp3 / mp4 / wav / m4a / webm / ogg / flac)
3. Select ASR & LLM vendors (only configured ones shown)
4. Click "Start" — transcript and meeting minutes stream in real-time

---

## 📁 Project Structure

```
├── app/                # Core application
│   ├── __init__.py     # App factory
│   ├── config.py       # Config (proxy, vendors, prompts)
│   ├── routes.py       # Routes and API endpoints
│   ├── services.py     # ASR/LLM business logic
│   └── utils.py        # Utility functions
├── static/             # Frontend static files
│   └── index.html
├── data/               # Data files
│   ├── ASR_prompt.txt
│   ├── LLM_prompt.txt
│   ├── conversationHist.md
│   └── vendor_keys.csv
├── import_keys.py      # Credential auto-detection script
├── run.py              # Project entry point
├── requirements.txt
└── README.md
```

## 📁 Output Structure

Each task saves to `output/<timestamp_id>/`:

```
output/20260228_143052_a1b2c3/
├── meta.json          # Task metadata
├── source_xxx.mp3     # Source file copy
├── transcript.txt     # Diarized transcript
├── summary.txt        # Meeting minutes
├── asr_log.json       # ASR raw log
└── llm_log.json       # LLM raw log
```

---

## ⭐ Star History

[![Star History Chart](https://api.star-history.com/svg?repos=taoxee/ASRtoLLM&type=Date)](https://star-history.com/#taoxee/ASRtoLLM&Date)

---

## License

MIT
