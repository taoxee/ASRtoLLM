# [VibeMeet2Notes · 灵感纪要](https://github.com/taoxee/VibeMeet2Notes)

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
- 🌍 **Multi-language UI** — Switch between Chinese/English, language preference auto-saved
- 🔄 **Smart Transcoding** — Auto-converts audio/video to 16kHz mono MP3, reducing file size for vendor compatibility

---

## 🎙️ Speaker Diarization Support

| Vendor | Diarization | Notes |
|--------|-------------|-------|
| Deepgram | ✅ Native | Nova-2 model |
| ElevenLabs | ✅ Native | Scribe v1 with speaker labels |
| Soniox | ✅ Native | Async diarization with speaker tracking |
| Tencent Cloud | ✅ Native | SpeakerDiarization via CreateRecTask |
| Alibaba Cloud | ✅ Native | DashScope Paraformer-v2 |
| Microsoft Global | ✅ Native | Fast Transcription API |
| Microsoft 21Vianet | ✅ Native | China endpoint |
| OpenAI / Groq | ⚠️ Timestamps only | Single speaker |
| Volcengine | ⚠️ Timestamps only | Single speaker |
| iFlytek | ✅ Native | raasr v2 API |

---

## 📋 Supported Vendors

| Vendor | ASR | LLM | TTS | Other |
|--------|-----|-----|-----|-------|
| Tencent Cloud | ✅ | ✅ | ✅ | Voice Clone |
| Volcengine | ✅ | | ✅ | Voice Clone |
| Microsoft 21Vianet | ✅ | | ✅ | Translation |
| Minimax-CN | | ✅ | ✅ | |
| Alibaba Cloud | ✅ | ✅ | ✅ | Voice Clone |
| Minimax-Global | | ✅ | ✅ | Voice Clone |
| ElevenLabs | ✅ | | ✅ | Voice Clone |
| Soniox | ✅ | | | Translation |
| Microsoft Global | ✅ | | ✅ | Voice Clone/Translation |
| Groq | | ✅ | | |
| Deepgram | ✅ | | | |
| Zhipu AI | | ✅ | | |
| iFlytek | ✅ | | | |
| OpenAI | | ✅ | | |

---

## 🚀 Quick Start

### Prerequisites

1. **Get your API Keys** — You need at least one ASR vendor and one LLM vendor API key

2. **Install ffmpeg** — Used to auto-transcode audio/video to 16kHz mono MP3, reducing file size for vendor compatibility

```bash
# Option 1: pip install (easiest, cross-platform)
pip install static-ffmpeg

# Option 2: system package manager
# macOS
brew install ffmpeg
# Ubuntu / Debian
sudo apt install ffmpeg
# Windows (Chocolatey)
choco install ffmpeg
```

Recommended combination (fast, cost-effective):

| Purpose | Recommended Vendor | Sign Up |
|---------|-------------------|---------|
| ASR (Speech-to-Text) | **Deepgram** | https://console.deepgram.com |
| LLM (Meeting Minutes) | **Alibaba Cloud** | https://bailian.console.aliyun.com |

> See the vendor table below for all supported providers. API keys are stored locally in your browser only — never sent to the server.

### Install & Run

```bash
pip install -r requirements.txt
python run.py
```

Open browser at: **http://127.0.0.1:8080**

### Optional: SOCKS Proxy Support

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

[![Star History Chart](https://api.star-history.com/svg?repos=taoxee/VibeMeet2Notes&type=Date)](https://star-history.com/#taoxee/VibeMeet2Notes&Date)

---

## License

Apache License 2.0 © [taoxee](https://github.com/taoxee)
