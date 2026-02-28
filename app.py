import os
import json
import tempfile
import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

app = Flask(__name__, static_folder="static")
CORS(app)

UPLOAD_FOLDER = tempfile.mkdtemp()
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {"mp3", "mp4", "wav", "m4a", "webm", "ogg", "flac", "mpeg", "mpga"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ── Vendor definitions with per-vendor credential fields ─────────────
VENDORS = {
    "腾讯云": {
        "types": ["ASR", "TTS", "声音复刻", "LLM"],
        "fields": [
            {"key": "appid",      "label": "appid",     "placeholder": "1400xxxxxx"},
            {"key": "secret_id",  "label": "SecretId",  "placeholder": "AKIDxxxxxxxx"},
            {"key": "secret_key", "label": "SecretKey", "placeholder": "xxxxxxxx"},
        ],
    },
    "火山云": {
        "types": ["ASR", "TTS", "声音复刻"],
        "fields": [
            {"key": "app_id",       "label": "APP ID",       "placeholder": "xxxxxxxx"},
            {"key": "access_token", "label": "Access Token",  "placeholder": "xxxxxxxx"},
            {"key": "secret_key",   "label": "Secret Key",    "placeholder": "xxxxxxxx"},
        ],
    },
    "微软-世纪互联": {
        "types": ["ASR", "TTS", "翻译"],
        "fields": [
            {"key": "key1",     "label": "密钥1",     "placeholder": "xxxxxxxx"},
            {"key": "key2",     "label": "密钥2",     "placeholder": "xxxxxxxx", "optional": True},
            {"key": "region",   "label": "位置/区域",  "placeholder": "chinaeast2", "secret": False},
            {"key": "endpoint", "label": "终结点",     "placeholder": "https://chinaeast2.api.cognitive.azure.cn/sts/v1.0/issuetoken", "secret": False},
        ],
    },
    "Minimax-CN": {
        "types": ["LLM", "TTS"],
        "fields": [
            {"key": "api_key",  "label": "接口密钥",  "placeholder": "xxxxxxxx"},
            {"key": "group_id", "label": "Group ID", "placeholder": "xxxxxxxx"},
        ],
    },
    "阿里云": {
        "types": ["ASR", "TTS", "LLM", "声音复刻"],
        "fields": [
            {"key": "api_key", "label": "api_key", "placeholder": "sk-xxxxxxxx"},
            {"key": "url",     "label": "url",     "placeholder": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions", "optional": True, "secret": False},
        ],
    },
    "Minimax-Global": {
        "types": ["TTS", "声音复刻", "LLM"],
        "fields": [
            {"key": "group_id", "label": "Group ID", "placeholder": "xxxxxxxx"},
            {"key": "api_key",  "label": "Key",      "placeholder": "xxxxxxxx"},
        ],
    },
    "ElevenLabs": {
        "types": ["ASR", "TTS", "声音复刻"],
        "fields": [
            {"key": "api_key", "label": "Key", "placeholder": "xi-xxxxxxxx"},
        ],
    },
    "Soniox": {
        "types": ["ASR", "翻译"],
        "fields": [
            {"key": "api_key", "label": "Key", "placeholder": "xxxxxxxx"},
        ],
    },
    "微软-Global": {
        "types": ["ASR", "TTS", "声音复刻", "翻译"],
        "fields": [
            {"key": "key1",     "label": "密钥1",     "placeholder": "xxxxxxxx"},
            {"key": "key2",     "label": "密钥2",     "placeholder": "xxxxxxxx", "optional": True},
            {"key": "region",   "label": "位置/区域",  "placeholder": "eastus", "secret": False},
            {"key": "endpoint", "label": "终结点",     "placeholder": "https://eastus.api.cognitive.microsoft.com", "secret": False},
        ],
    },
    "Groq": {
        "types": ["LLM"],
        "fields": [
            {"key": "api_key", "label": "API Key", "placeholder": "gsk_xxxxxxxx"},
        ],
    },
    "Deepgram": {
        "types": ["ASR"],
        "fields": [
            {"key": "api_key", "label": "API Key", "placeholder": "xxxxxxxx"},
        ],
    },
    "智谱": {
        "types": ["LLM"],
        "fields": [
            {"key": "api_key", "label": "API Key", "placeholder": "xxxxxxxx.xxxxxxxx"},
        ],
    },
    "讯飞": {
        "types": ["ASR"],
        "fields": [
            {"key": "appid",         "label": "APPID",        "placeholder": "xxxxxxxx"},
            {"key": "access_key",    "label": "accessKey",    "placeholder": "xxxxxxxx"},
            {"key": "access_secret", "label": "accessSecret", "placeholder": "xxxxxxxx"},
        ],
        "note": "方言自由说ASR，语言参数：autodialect（自动识别中英及中文方言）",
    },
    "OpenAI": {
        "types": ["LLM"],
        "fields": [
            {"key": "api_key", "label": "API Key", "placeholder": "sk-xxxxxxxx"},
        ],
    },
}


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/vendors")
def get_vendors():
    return jsonify(VENDORS)


# ── ASR: transcribe audio/video via selected vendor ─────────────────
def transcribe_openai_compatible(creds, filepath, base_url="https://api.openai.com/v1"):
    """Works for OpenAI, Groq, and other OpenAI-compatible APIs."""
    api_key = creds.get("api_key", "")
    headers = {"Authorization": f"Bearer {api_key}"}
    with open(filepath, "rb") as f:
        resp = requests.post(
            f"{base_url}/audio/transcriptions",
            headers=headers,
            files={"file": (os.path.basename(filepath), f)},
            data={"model": "whisper-large-v3" if "groq" in base_url else "whisper-1"},
            timeout=300,
        )
    resp.raise_for_status()
    return resp.json().get("text", "")


def transcribe_deepgram(creds, filepath):
    api_key = creds.get("api_key", "")
    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "audio/mpeg",
    }
    with open(filepath, "rb") as f:
        resp = requests.post(
            "https://api.deepgram.com/v1/listen?model=nova-2&language=zh",
            headers=headers,
            data=f,
            timeout=300,
        )
    resp.raise_for_status()
    data = resp.json()
    return data["results"]["channels"][0]["alternatives"][0]["transcript"]


def transcribe_elevenlabs(creds, filepath):
    api_key = creds.get("api_key", "")
    headers = {"xi-api-key": api_key}
    with open(filepath, "rb") as f:
        resp = requests.post(
            "https://api.elevenlabs.io/v1/speech-to-text",
            headers=headers,
            files={"file": (os.path.basename(filepath), f)},
            data={"model_id": "scribe_v1"},
            timeout=300,
        )
    resp.raise_for_status()
    return resp.json().get("text", "")


ASR_HANDLERS = {
    "OpenAI":     lambda c, fp: transcribe_openai_compatible(c, fp, "https://api.openai.com/v1"),
    "Groq":       lambda c, fp: transcribe_openai_compatible(c, fp, "https://api.groq.com/openai/v1"),
    "Deepgram":   transcribe_deepgram,
    "ElevenLabs": transcribe_elevenlabs,
}


# ── LLM: summarize text via selected vendor ─────────────────────────
def summarize_openai_compatible(creds, text, base_url, model):
    api_key = creds.get("api_key", "")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一个专业的文本摘要助手。请对以下内容进行详细的总结和摘要，保留关键信息，使用中文回复。"},
            {"role": "user", "content": f"请对以下转录文本进行总结：\n\n{text}"},
        ],
        "temperature": 0.3,
        "max_tokens": 4096,
    }
    resp = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def summarize_minimax(creds, text, base_url, model):
    api_key = creds.get("api_key", "")
    group_id = creds.get("group_id", "")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一个专业的文本摘要助手。请对以下内容进行详细的总结和摘要，保留关键信息，使用中文回复。"},
            {"role": "user", "content": f"请对以下转录文本进行总结：\n\n{text}"},
        ],
        "temperature": 0.3,
        "max_tokens": 4096,
    }
    url = f"{base_url}/chat/completions"
    if group_id:
        url += f"?GroupId={group_id}"
    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def summarize_tencent(creds, text):
    """腾讯云 uses SecretId/SecretKey — route through their OpenAI-compatible endpoint."""
    api_key = creds.get("secret_key", "")
    return summarize_openai_compatible(
        {"api_key": api_key}, text,
        "https://api.lkeap.cloud.tencent.com/v1", "deepseek-v3"
    )


def summarize_aliyun(creds, text):
    """阿里云 supports custom URL override."""
    custom_url = creds.get("url", "").strip().rstrip("/")
    base_url = custom_url if custom_url else "https://dashscope.aliyuncs.com/compatible-mode/v1"
    # Strip /chat/completions if user pasted the full endpoint
    if base_url.endswith("/chat/completions"):
        base_url = base_url.rsplit("/chat/completions", 1)[0]
    return summarize_openai_compatible(creds, text, base_url, "qwen-plus")


LLM_HANDLERS = {
    "OpenAI":         lambda c, text: summarize_openai_compatible(c, text, "https://api.openai.com/v1", "gpt-4o"),
    "Groq":           lambda c, text: summarize_openai_compatible(c, text, "https://api.groq.com/openai/v1", "llama-3.3-70b-versatile"),
    "智谱":           lambda c, text: summarize_openai_compatible(c, text, "https://open.bigmodel.cn/api/paas/v4", "glm-4-flash"),
    "Minimax-CN":     lambda c, text: summarize_minimax(c, text, "https://api.minimax.chat/v1", "MiniMax-Text-01"),
    "Minimax-Global": lambda c, text: summarize_minimax(c, text, "https://api.minimaxi.chat/v1", "MiniMax-Text-01"),
    "腾讯云":         summarize_tencent,
    "阿里云":         summarize_aliyun,
}


@app.route("/api/process", methods=["POST"])
def process_file():
    """Upload media → ASR transcription → LLM summary."""
    file = request.files.get("file")
    if not file or not allowed_file(file.filename):
        return jsonify({"error": "请上传有效的音视频文件 (mp3/mp4/wav/m4a/webm/ogg/flac)"}), 400

    asr_vendor = request.form.get("asr_vendor", "")
    llm_vendor = request.form.get("llm_vendor", "")

    try:
        asr_creds = json.loads(request.form.get("asr_creds", "{}"))
        llm_creds = json.loads(request.form.get("llm_creds", "{}"))
    except json.JSONDecodeError:
        return jsonify({"error": "凭证格式错误"}), 400

    if not asr_vendor or not asr_creds:
        return jsonify({"error": "请选择 ASR 供应商并填写凭证"}), 400
    if not llm_vendor or not llm_creds:
        return jsonify({"error": "请选择 LLM 供应商并填写凭证"}), 400

    # Save uploaded file
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    try:
        # Step 1: ASR
        asr_handler = ASR_HANDLERS.get(asr_vendor)
        if not asr_handler:
            return jsonify({"error": f"ASR 供应商 '{asr_vendor}' 暂未实现接口对接"}), 400
        transcript = asr_handler(asr_creds, filepath)

        if not transcript.strip():
            return jsonify({"error": "转录结果为空，请检查音频文件是否包含语音内容"}), 400

        # Step 2: LLM summary
        llm_handler = LLM_HANDLERS.get(llm_vendor)
        if not llm_handler:
            return jsonify({"error": f"LLM 供应商 '{llm_vendor}' 暂未实现接口对接"}), 400
        summary = llm_handler(llm_creds, transcript)

        return jsonify({"transcript": transcript, "summary": summary})

    except requests.exceptions.HTTPError as e:
        detail = ""
        try:
            detail = e.response.json()
        except Exception:
            detail = e.response.text[:500] if e.response else str(e)
        return jsonify({"error": f"API 调用失败: {detail}"}), 502
    except Exception as e:
        return jsonify({"error": f"处理失败: {str(e)}"}), 500
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8080)
