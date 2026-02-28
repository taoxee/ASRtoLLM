import os
import json
import tempfile
import uuid
from datetime import datetime
import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

app = Flask(__name__, static_folder="static")
CORS(app)

# ── Load prompt templates ────────────────────────────────────────────
_PROMPT_DIR = os.path.dirname(os.path.abspath(__file__))

def _load_prompt(filename, fallback=""):
    path = os.path.join(_PROMPT_DIR, filename)
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return fallback

ASR_PROMPT = _load_prompt("ASR_prompt.txt")
LLM_PROMPT = _load_prompt("LLM_prompt.txt")

# ── Output folder for task results ──────────────────────────────────
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Proxy settings ───────────────────────────────────────────────────
# Automatically detect system proxy (macOS ShadowsocksX-NG, ClashX, etc.)
# Priority: HTTPS_PROXY env var > macOS system proxy > no proxy
def _detect_proxy():
    # 1. Check env var first
    env_proxy = os.environ.get("HTTPS_PROXY", "") or os.environ.get("https_proxy", "")
    if env_proxy.strip():
        return env_proxy.strip()
    # 2. Try reading macOS system proxy via scutil
    try:
        import subprocess
        result = subprocess.run(
            ["scutil", "--proxy"], capture_output=True, text=True, timeout=5
        )
        lines = result.stdout.strip().split("\n")
        proxy_info = {}
        for line in lines:
            if ":" in line:
                k, v = line.split(":", 1)
                proxy_info[k.strip()] = v.strip()
        # SOCKS proxy (ShadowsocksX-NG default)
        if proxy_info.get("SOCKSEnable") == "1":
            host = proxy_info.get("SOCKSProxy", "127.0.0.1")
            port = proxy_info.get("SOCKSPort", "1080")
            return f"socks5h://{host}:{port}"
        # HTTP proxy
        if proxy_info.get("HTTPSEnable") == "1":
            host = proxy_info.get("HTTPSProxy", "127.0.0.1")
            port = proxy_info.get("HTTPSPort", "1087")
            return f"http://{host}:{port}"
        if proxy_info.get("HTTPEnable") == "1":
            host = proxy_info.get("HTTPProxy", "127.0.0.1")
            port = proxy_info.get("HTTPPort", "1087")
            return f"http://{host}:{port}"
    except Exception:
        pass
    return ""

PROXY_URL = _detect_proxy()

# Shared session with proxy
http = requests.Session()
if PROXY_URL:
    http.proxies.update({"http": PROXY_URL, "https": PROXY_URL})
    print(f"[Proxy] Using: {PROXY_URL}")
else:
    print("[Proxy] No proxy detected, using direct connection")

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
            {"key": "key1",   "label": "Key",    "placeholder": "xxxxxxxx"},
            {"key": "region", "label": "Region", "placeholder": "eastus", "secret": False, "default": "eastus"},
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
            {"key": "language",      "label": "语言参数",      "placeholder": "autodialect", "secret": False, "default": "autodialect"},
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


@app.route("/api/import-keys")
def import_keys():
    """Auto-detect vendor credentials from env vars, .env, vendor_keys.csv."""
    from import_keys import detect_all
    csv_path = os.path.join(_PROMPT_DIR, "vendor_keys.csv")
    env_path = os.path.join(_PROMPT_DIR, ".env")
    creds = detect_all(
        env_file=env_path if os.path.isfile(env_path) else None,
        csv_file=csv_path,
    )
    return jsonify(creds)


# ── ASR: transcribe audio/video via selected vendor ─────────────────
def _seconds_to_hms(seconds):
    """Convert seconds (float) to HH:MM:SS string."""
    s = int(seconds)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def transcribe_openai_compatible(creds, filepath, base_url="https://api.openai.com/v1"):
    """Works for OpenAI, Groq, and other OpenAI-compatible APIs.
    Returns verbose JSON with timestamps when available."""
    api_key = creds.get("api_key", "")
    headers = {"Authorization": f"Bearer {api_key}"}
    model = "whisper-large-v3" if "groq" in base_url else "whisper-1"
    with open(filepath, "rb") as f:
        resp = http.post(
            f"{base_url}/audio/transcriptions",
            headers=headers,
            files={"file": (os.path.basename(filepath), f)},
            data={
                "model": model,
                "response_format": "verbose_json",
                "timestamp_granularities[]": "segment",
            },
            timeout=300,
        )
    resp.raise_for_status()
    data = resp.json()
    # Build timestamped segments (no speaker diarization from Whisper)
    raw_segments = data.get("segments", [])
    if raw_segments:
        segments = []
        for s in raw_segments:
            segments.append({
                "start_time": _seconds_to_hms(s.get("start", 0)),
                "end_time": _seconds_to_hms(s.get("end", 0)),
                "speaker": "Speaker 1",
                "text": s.get("text", "").strip(),
            })
        return json.dumps({
            "metadata": {"language": data.get("language", ""), "total_speakers": 1},
            "segments": segments,
        }, ensure_ascii=False, indent=2)
    return data.get("text", "")




def transcribe_deepgram(creds, filepath):
    """Deepgram Nova-2 with speaker diarization."""
    api_key = creds.get("api_key", "")
    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "audio/mpeg",
    }
    with open(filepath, "rb") as f:
        resp = http.post(
            "https://api.deepgram.com/v1/listen?model=nova-2&language=zh&diarize=true&punctuate=true&utterances=true",
            headers=headers,
            data=f,
            timeout=300,
        )
    resp.raise_for_status()
    data = resp.json()
    # Build diarized JSON output
    utterances = data.get("results", {}).get("utterances", [])
    if utterances:
        segments = []
        speaker_map = {}
        for u in utterances:
            spk_id = u.get("speaker", 0)
            if spk_id not in speaker_map:
                speaker_map[spk_id] = f"Speaker {len(speaker_map) + 1}"
            segments.append({
                "start_time": _seconds_to_hms(u.get("start", 0)),
                "end_time": _seconds_to_hms(u.get("end", 0)),
                "speaker": speaker_map[spk_id],
                "text": u.get("transcript", ""),
            })
        return json.dumps({
            "metadata": {"language": "zh", "total_speakers": len(speaker_map)},
            "segments": segments,
        }, ensure_ascii=False, indent=2)
    # Fallback: no utterances, return plain text
    return data["results"]["channels"][0]["alternatives"][0]["transcript"]




def transcribe_elevenlabs(creds, filepath):
    """ElevenLabs Scribe v1 with speaker diarization."""
    api_key = creds.get("api_key", "")
    headers = {"xi-api-key": api_key}
    with open(filepath, "rb") as f:
        resp = http.post(
            "https://api.elevenlabs.io/v1/speech-to-text",
            headers=headers,
            files={"file": (os.path.basename(filepath), f)},
            data={
                "model_id": "scribe_v1",
                "diarize": "true",
                "timestamps_granularity": "word",
            },
            timeout=300,
        )
    resp.raise_for_status()
    data = resp.json()
    # Build diarized output from words with speaker info
    words = data.get("words", [])
    if words and any(w.get("speaker_id") is not None for w in words):
        segments = []
        speaker_map = {}
        current_speaker = None
        current_text = []
        current_start = 0
        current_end = 0
        for w in words:
            spk = w.get("speaker_id", "unknown")
            if spk not in speaker_map:
                speaker_map[spk] = f"Speaker {len(speaker_map) + 1}"
            if spk != current_speaker:
                if current_text and current_speaker is not None:
                    segments.append({
                        "start_time": _seconds_to_hms(current_start),
                        "end_time": _seconds_to_hms(current_end),
                        "speaker": speaker_map[current_speaker],
                        "text": "".join(current_text).strip(),
                    })
                current_speaker = spk
                current_text = [w.get("text", "")]
                current_start = w.get("start", 0)
                current_end = w.get("end", 0)
            else:
                current_text.append(w.get("text", ""))
                current_end = w.get("end", 0)
        if current_text and current_speaker is not None:
            segments.append({
                "start_time": _seconds_to_hms(current_start),
                "end_time": _seconds_to_hms(current_end),
                "speaker": speaker_map[current_speaker],
                "text": "".join(current_text).strip(),
            })
        return json.dumps({
            "metadata": {"language": data.get("language_code", ""), "total_speakers": len(speaker_map)},
            "segments": segments,
        }, ensure_ascii=False, indent=2)
    return data.get("text", "")



def transcribe_volcengine(creds, filepath):
    """火山云 ASR via openspeech.bytedance.com submit+query API."""
    import time as _time
    app_id = creds.get("app_id", "")
    access_token = creds.get("access_token", "")

    # Step 1: Submit audio
    submit_url = "https://openspeech.bytedance.com/api/v1/vc/submit"
    params = {
        "appid": app_id,
        "language": "zh-CN",
        "use_itn": "True",
        "use_punc": "True",
        "words_per_line": 46,
    }
    headers = {
        "Content-Type": "audio/wav",
        "Authorization": f"Bearer; {access_token}",
    }
    with open(filepath, "rb") as f:
        resp = http.post(submit_url, params=params, headers=headers, data=f, timeout=300)
    resp.raise_for_status()
    submit_data = resp.json()
    if str(submit_data.get("code", "")) != "0":
        raise Exception(f"火山云提交失败: {submit_data.get('message', submit_data)}")
    task_id = submit_data["id"]

    # Step 2: Query result (blocking mode)
    query_url = "https://openspeech.bytedance.com/api/v1/vc/query"
    query_params = {"appid": app_id, "id": task_id, "blocking": 1}
    query_headers = {"Authorization": f"Bearer; {access_token}"}
    for attempt in range(60):
        resp = http.get(query_url, params=query_params, headers=query_headers, timeout=300)
        resp.raise_for_status()
        result = resp.json()
        code = result.get("code", -1)
        if code == 0:
            utterances = result.get("utterances", [])
            if utterances and any("start_time" in u for u in utterances):
                segments = []
                for u in utterances:
                    segments.append({
                        "start_time": _seconds_to_hms(u.get("start_time", 0) / 1000),
                        "end_time": _seconds_to_hms(u.get("end_time", 0) / 1000),
                        "speaker": "Speaker 1",
                        "text": u.get("text", ""),
                    })
                return json.dumps({
                    "metadata": {"language": "zh-CN", "total_speakers": 1},
                    "segments": segments,
                }, ensure_ascii=False, indent=2)
            return "".join(u.get("text", "") for u in utterances)
        elif code == 1:  # still processing
            _time.sleep(3)
            continue
        else:
            raise Exception(f"火山云查询失败: {result.get('message', result)}")
    raise Exception("火山云 ASR 超时，请稍后重试")



def transcribe_soniox(creds, filepath):
    """Soniox ASR with speaker diarization: upload → transcribe → poll → get transcript → cleanup."""
    import time as _time
    api_key = creds.get("api_key", "")
    base = "https://api.soniox.com"
    headers = {"Authorization": f"Bearer {api_key}"}

    # Step 1: Upload file
    with open(filepath, "rb") as f:
        resp = http.post(
            f"{base}/v1/files",
            headers=headers,
            files={"file": (os.path.basename(filepath), f)},
            timeout=300,
        )
    resp.raise_for_status()
    file_id = resp.json()["id"]

    try:
        # Step 2: Create transcription with diarization
        config = {
            "model": "stt-async-v4",
            "file_id": file_id,
            "language_hints": ["zh", "en"],
            "enable_language_identification": True,
            "enable_speaker_diarization": True,
            "min_num_speakers": 1,
            "max_num_speakers": 10,
        }
        resp = http.post(
            f"{base}/v1/transcriptions",
            headers={**headers, "Content-Type": "application/json"},
            json=config,
            timeout=60,
        )
        resp.raise_for_status()
        transcription_id = resp.json()["id"]

        # Step 3: Poll until completed
        for _ in range(120):
            resp = http.get(f"{base}/v1/transcriptions/{transcription_id}", headers=headers, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            if data["status"] == "completed":
                break
            elif data["status"] == "error":
                raise Exception(f"Soniox 转录失败: {data.get('error_message', 'Unknown')}")
            _time.sleep(2)
        else:
            raise Exception("Soniox ASR 超时")

        # Step 4: Get transcript with speaker info
        resp = http.get(f"{base}/v1/transcriptions/{transcription_id}/transcript", headers=headers, timeout=60)
        resp.raise_for_status()
        transcript_data = resp.json()
        tokens = transcript_data.get("tokens", [])

        # Build diarized segments from tokens with speaker info
        if tokens and any(t.get("speaker") is not None for t in tokens):
            segments = []
            speaker_map = {}
            current_speaker = None
            current_text = []
            current_start = 0
            current_end = 0
            for t in tokens:
                spk = t.get("speaker", 0)
                if spk not in speaker_map:
                    speaker_map[spk] = f"Speaker {len(speaker_map) + 1}"
                start_ms = t.get("start_ms", 0)
                end_ms = start_ms + t.get("duration_ms", 0)
                if spk != current_speaker:
                    if current_text and current_speaker is not None:
                        segments.append({
                            "start_time": _seconds_to_hms(current_start / 1000),
                            "end_time": _seconds_to_hms(current_end / 1000),
                            "speaker": speaker_map[current_speaker],
                            "text": "".join(current_text).strip(),
                        })
                    current_speaker = spk
                    current_text = [t.get("text", "")]
                    current_start = start_ms
                    current_end = end_ms
                else:
                    current_text.append(t.get("text", ""))
                    current_end = end_ms
            if current_text and current_speaker is not None:
                segments.append({
                    "start_time": _seconds_to_hms(current_start / 1000),
                    "end_time": _seconds_to_hms(current_end / 1000),
                    "speaker": speaker_map[current_speaker],
                    "text": "".join(current_text).strip(),
                })
            result = json.dumps({
                "metadata": {"language": "zh", "total_speakers": len(speaker_map)},
                "segments": segments,
            }, ensure_ascii=False, indent=2)
        else:
            result = "".join(t.get("text", "") for t in tokens)

        # Cleanup
        try:
            http.delete(f"{base}/v1/transcriptions/{transcription_id}", headers=headers, timeout=10)
        except Exception:
            pass

        return result
    finally:
        try:
            http.delete(f"{base}/v1/files/{file_id}", headers=headers, timeout=10)
        except Exception:
            pass


def transcribe_tencent(creds, filepath):
    """腾讯云 ASR: CreateRecTask → DescribeTaskStatus polling.
    Uses TC3-HMAC-SHA256 signing against asr.tencentcloudapi.com."""
    import time as _time
    import hashlib
    import hmac
    import base64

    secret_id = creds.get("secret_id", "")
    secret_key = creds.get("secret_key", "")
    appid = creds.get("appid", "")
    host = "asr.tencentcloudapi.com"
    service = "asr"
    endpoint = f"https://{host}"

    def _sign_request(action, payload_dict):
        """Build TC3-HMAC-SHA256 signed headers for Tencent Cloud API."""
        import calendar
        ts = int(_time.time())
        date = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
        payload = json.dumps(payload_dict)

        # 1. Canonical request
        http_method = "POST"
        canonical_uri = "/"
        canonical_querystring = ""
        ct = "application/json; charset=utf-8"
        canonical_headers = f"content-type:{ct}\nhost:{host}\nx-tc-action:{action.lower()}\n"
        signed_headers = "content-type;host;x-tc-action"
        hashed_payload = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        canonical_request = f"{http_method}\n{canonical_uri}\n{canonical_querystring}\n{canonical_headers}\n{signed_headers}\n{hashed_payload}"

        # 2. String to sign
        algorithm = "TC3-HMAC-SHA256"
        credential_scope = f"{date}/{service}/tc3_request"
        hashed_cr = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
        string_to_sign = f"{algorithm}\n{ts}\n{credential_scope}\n{hashed_cr}"

        # 3. Signing key
        def _hmac_sha256(key, msg):
            return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

        secret_date = _hmac_sha256(("TC3" + secret_key).encode("utf-8"), date)
        secret_service = _hmac_sha256(secret_date, service)
        secret_signing = _hmac_sha256(secret_service, "tc3_request")
        signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

        # 4. Authorization header
        authorization = (
            f"{algorithm} Credential={secret_id}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )

        return {
            "Authorization": authorization,
            "Content-Type": ct,
            "Host": host,
            "X-TC-Action": action,
            "X-TC-Version": "2019-06-14",
            "X-TC-Timestamp": str(ts),
        }

    # Read audio and base64-encode
    with open(filepath, "rb") as f:
        audio_data = base64.b64encode(f.read()).decode("utf-8")

    file_size = os.path.getsize(filepath)

    # Step 1: CreateRecTask with speaker diarization
    create_payload = {
        "EngineModelType": "16k_zh",
        "ChannelNum": 1,
        "ResTextFormat": 3,  # 3 = JSON with word-level timestamps + speaker
        "SourceType": 1,
        "Data": audio_data,
        "DataLen": file_size,
        "SpeakerDiarization": 1,  # Enable speaker diarization
        "SpeakerNumber": 0,       # 0 = auto-detect number of speakers
    }
    headers = _sign_request("CreateRecTask", create_payload)
    resp = http.post(endpoint, headers=headers, json=create_payload, timeout=300)
    resp.raise_for_status()
    result = resp.json()
    if "Response" not in result or "Data" not in result["Response"]:
        error = result.get("Response", {}).get("Error", {})
        raise Exception(f"腾讯云 CreateRecTask 失败: {error.get('Message', result)}")
    task_id = result["Response"]["Data"]["TaskId"]

    # Step 2: Poll DescribeTaskStatus
    for _ in range(120):
        _time.sleep(3)
        query_payload = {"TaskId": task_id}
        headers = _sign_request("DescribeTaskStatus", query_payload)
        resp = http.post(endpoint, headers=headers, json=query_payload, timeout=60)
        resp.raise_for_status()
        result = resp.json()
        if "Response" not in result or "Data" not in result["Response"]:
            error = result.get("Response", {}).get("Error", {})
            raise Exception(f"腾讯云查询失败: {error.get('Message', result)}")
        data = result["Response"]["Data"]
        status = data.get("StatusStr", "")
        if status == "success":
            raw_result = data.get("Result", "")
            # Try to parse and reformat into our diarized JSON format
            try:
                tencent_data = json.loads(raw_result)
                sentences = tencent_data.get("FlashResult", [{}])[0].get("sentence_list", []) if "FlashResult" in tencent_data else []
                if not sentences:
                    # Try standard result format
                    sentences = tencent_data.get("Result", {}).get("sentence_list", []) if isinstance(tencent_data.get("Result"), dict) else []
                if sentences and any(s.get("speaker_id") is not None for s in sentences):
                    speaker_map = {}
                    segments = []
                    for s in sentences:
                        spk = s.get("speaker_id", 0)
                        if spk not in speaker_map:
                            speaker_map[spk] = f"Speaker {len(speaker_map) + 1}"
                        segments.append({
                            "start_time": _seconds_to_hms(s.get("start_time", 0) / 1000),
                            "end_time": _seconds_to_hms(s.get("end_time", 0) / 1000),
                            "speaker": speaker_map[spk],
                            "text": s.get("text", ""),
                        })
                    return json.dumps({
                        "metadata": {"language": "zh", "total_speakers": len(speaker_map)},
                        "segments": segments,
                    }, ensure_ascii=False, indent=2)
            except (json.JSONDecodeError, KeyError, IndexError):
                pass
            return raw_result
        elif status == "failed":
            raise Exception(f"腾讯云 ASR 任务失败: {data.get('ErrorMsg', 'Unknown')}")
        # status == "waiting" or "doing" → keep polling

    raise Exception("腾讯云 ASR 超时，请稍后重试")


def transcribe_microsoft_global(creds, filepath):
    """Microsoft Global Speech-to-Text via Fast Transcription REST API."""
    api_key = creds.get("key1", "")
    region = creds.get("region", "eastus").strip() or "eastus"
    endpoint = f"https://{region}.api.cognitive.microsoft.com"

    definition = json.dumps({
        "locales": ["zh-CN", "en-US"],
        "profanityFilterMode": "None",
        "diarizationSettings": {
            "minSpeakers": 1,
            "maxSpeakers": 10,
        },
    })

    headers = {"Ocp-Apim-Subscription-Key": api_key}
    with open(filepath, "rb") as f:
        resp = http.post(
            f"{endpoint}/speechtotext/transcriptions:transcribe?api-version=2024-11-15",
            headers=headers,
            files={
                "audio": (os.path.basename(filepath), f),
                "definition": (None, definition, "application/json"),
            },
            timeout=300,
        )
    resp.raise_for_status()
    data = resp.json()

    # Build diarized output from phrases
    phrases = data.get("phrases", [])
    if phrases:
        speaker_map = {}
        segments = []
        for p in phrases:
            spk = p.get("speaker", 1)
            if spk not in speaker_map:
                speaker_map[spk] = f"Speaker {len(speaker_map) + 1}"
            offset_ms = p.get("offsetMilliseconds", 0)
            duration_ms = p.get("durationMilliseconds", 0)
            segments.append({
                "start_time": _seconds_to_hms(offset_ms / 1000),
                "end_time": _seconds_to_hms((offset_ms + duration_ms) / 1000),
                "speaker": speaker_map[spk],
                "text": p.get("text", ""),
            })
        return json.dumps({
            "metadata": {"language": "zh", "total_speakers": len(speaker_map)},
            "segments": segments,
        }, ensure_ascii=False, indent=2)

    # Fallback: combined text
    combined = data.get("combinedPhrases", [])
    if combined:
        return combined[0].get("text", "")
    return ""


def transcribe_xfyun(creds, filepath):
    """讯飞 ASR: 非实时转写 API (raasr.xfyun.cn) with speaker diarization.
    Flow: prepare → upload (chunked) → merge → poll progress → getResult."""
    import time as _time
    import hashlib
    import hmac
    import base64

    appid = creds.get("appid", "")
    access_key = creds.get("access_key", "")
    access_secret = creds.get("access_secret", "")
    language = creds.get("language", "autodialect")
    host = "https://raasr.xfyun.cn/v2/api"
    chunk_size = 10 * 1024 * 1024  # 10MB

    def _make_signature():
        ts = str(int(_time.time()))
        base_string = appid + ts
        md5_hash = hashlib.md5(base_string.encode("utf-8")).hexdigest()
        signa = hmac.new(
            access_key.encode("utf-8"),
            md5_hash.encode("utf-8"),
            hashlib.sha1,
        ).digest()
        return base64.b64encode(signa).decode("utf-8"), ts

    file_size = os.path.getsize(filepath)
    file_name = os.path.basename(filepath)
    slice_num = (file_size + chunk_size - 1) // chunk_size

    # Step 1: Prepare
    signa, ts = _make_signature()
    prepare_data = {
        "appId": appid,
        "signa": signa,
        "ts": ts,
        "fileSize": str(file_size),
        "fileName": file_name,
        "duration": "200",
        "language": language,
        "callbackUrl": "",
        "hasSeperateByDefault": "true",
        "roleType": "2",
        "hasParticulars": "true",
    }
    resp = http.post(f"{host}/upload", data=prepare_data, timeout=60)
    resp.raise_for_status()
    result = resp.json()
    if result.get("code") != "000000":
        raise Exception(f"讯飞 prepare 失败: {result.get('descInfo', result)}")
    task_id = result["content"]["orderId"]

    # Step 2: Upload file chunks
    with open(filepath, "rb") as f:
        slice_idx = 1
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            signa, ts = _make_signature()
            upload_data = {
                "appId": appid,
                "signa": signa,
                "ts": ts,
                "taskId": task_id,
                "sliceId": f"aaaaaaaaaa"[:10 - len(str(slice_idx))] + str(slice_idx),
            }
            resp = http.post(
                f"{host}/upload",
                data=upload_data,
                files={"file": (file_name, chunk)},
                timeout=120,
            )
            resp.raise_for_status()
            slice_idx += 1

    # Step 3: Merge
    signa, ts = _make_signature()
    merge_data = {"appId": appid, "signa": signa, "ts": ts, "taskId": task_id}
    resp = http.post(f"{host}/merge", data=merge_data, timeout=60)
    resp.raise_for_status()

    # Step 4: Poll for result
    for _ in range(180):
        _time.sleep(5)
        signa, ts = _make_signature()
        query_data = {"appId": appid, "signa": signa, "ts": ts, "taskId": task_id}
        resp = http.post(f"{host}/getResult", data=query_data, timeout=60)
        resp.raise_for_status()
        result = resp.json()
        code = result.get("code", "")
        if code == "000000":
            content = result.get("content", {})
            order_result = content.get("orderResult", "")
            if order_result:
                try:
                    parsed = json.loads(order_result)
                    lattice = parsed.get("lattice", [])
                    if lattice:
                        segments = []
                        speaker_map = {}
                        for item in lattice:
                            json_1best = json.loads(item.get("json_1best", "{}"))
                            st = json_1best.get("st", {})
                            spk = st.get("rl", "0")
                            if spk not in speaker_map:
                                speaker_map[spk] = f"Speaker {len(speaker_map) + 1}"
                            bg = int(st.get("bg", "0"))
                            ed = int(st.get("ed", "0"))
                            words = st.get("rt", [{}])[0].get("ws", [])
                            text = "".join(w.get("cw", [{}])[0].get("w", "") for w in words)
                            if text.strip():
                                segments.append({
                                    "start_time": _seconds_to_hms(bg / 1000),
                                    "end_time": _seconds_to_hms(ed / 1000),
                                    "speaker": speaker_map[spk],
                                    "text": text,
                                })
                        if segments:
                            return json.dumps({
                                "metadata": {"language": language, "total_speakers": len(speaker_map)},
                                "segments": segments,
                            }, ensure_ascii=False, indent=2)
                except (json.JSONDecodeError, KeyError):
                    pass
                return order_result
            # Still processing
            status = content.get("orderInfo", {}).get("status")
            if status == 4:  # completed
                return content.get("orderResult", "")
            elif status == -1:
                raise Exception("讯飞 ASR 任务失败")
        elif code == "26605":  # still processing
            continue
        else:
            raise Exception(f"讯飞查询失败: {result.get('descInfo', result)}")

    raise Exception("讯飞 ASR 超时，请稍后重试")


def transcribe_aliyun(creds, filepath):
    """阿里云 ASR via DashScope Paraformer HTTP API (no SDK needed).
    Uses async file transcription: submit task → poll → get result."""
    import time as _time
    import base64

    api_key = creds.get("api_key", "")
    base_url = "https://dashscope.aliyuncs.com/api/v1/services/audio/asr"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Read and base64-encode the audio file
    with open(filepath, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode("utf-8")

    ext = os.path.splitext(filepath)[1].lower().lstrip(".")
    format_map = {"mp3": "mp3", "wav": "wav", "m4a": "m4a", "mp4": "mp4",
                  "ogg": "ogg", "flac": "flac", "webm": "opus"}
    audio_format = format_map.get(ext, "mp3")

    # Step 1: Submit transcription task
    payload = {
        "model": "paraformer-v2",
        "input": {
            "file_urls": [],
            "data": audio_b64,
            "format": audio_format,
            "sample_rate": 16000,
        },
        "parameters": {
            "language_hints": ["zh", "en"],
            "diarization_enabled": True,
        },
    }
    resp = http.post(
        f"{base_url}/transcription",
        headers={**headers, "X-DashScope-Async": "enable"},
        json=payload,
        timeout=120,
    )
    resp.raise_for_status()
    result = resp.json()
    task_id = result.get("output", {}).get("task_id", "")
    if not task_id:
        raise Exception(f"阿里云 ASR 提交失败: {result}")

    # Step 2: Poll task status
    for _ in range(120):
        _time.sleep(3)
        resp = http.get(
            f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60,
        )
        resp.raise_for_status()
        result = resp.json()
        status = result.get("output", {}).get("task_status", "")
        if status == "SUCCEEDED":
            # Get transcription result URL
            results = result.get("output", {}).get("results", [])
            if results:
                trans_url = results[0].get("transcription_url", "")
                if trans_url:
                    trans_resp = http.get(trans_url, timeout=60)
                    trans_resp.raise_for_status()
                    trans_data = trans_resp.json()
                    transcripts = trans_data.get("transcripts", [])
                    if transcripts:
                        sentences = transcripts[0].get("sentences", [])
                        if sentences and any(s.get("speaker_id") is not None for s in sentences):
                            speaker_map = {}
                            segments = []
                            for s in sentences:
                                spk = s.get("speaker_id", 0)
                                if spk not in speaker_map:
                                    speaker_map[spk] = f"Speaker {len(speaker_map) + 1}"
                                segments.append({
                                    "start_time": _seconds_to_hms(s.get("begin_time", 0) / 1000),
                                    "end_time": _seconds_to_hms(s.get("end_time", 0) / 1000),
                                    "speaker": speaker_map[spk],
                                    "text": s.get("text", ""),
                                })
                            return json.dumps({
                                "metadata": {"language": "zh", "total_speakers": len(speaker_map)},
                                "segments": segments,
                            }, ensure_ascii=False, indent=2)
                        # No diarization, return plain text
                        return transcripts[0].get("text", "")
            # Fallback
            return result.get("output", {}).get("text", "")
        elif status == "FAILED":
            msg = result.get("output", {}).get("message", "Unknown")
            raise Exception(f"阿里云 ASR 失败: {msg}")
        # PENDING / RUNNING → keep polling

    raise Exception("阿里云 ASR 超时，请稍后重试")


def transcribe_microsoft_cn(creds, filepath):
    """微软-世纪互联 ASR via Azure China Speech-to-Text Fast Transcription API."""
    api_key = creds.get("key1", "")
    region = creds.get("region", "chinaeast2").strip() or "chinaeast2"
    endpoint = creds.get("endpoint", "").strip()

    # Build base URL from region if no custom endpoint
    if endpoint:
        # Strip token endpoint path if user pasted the full issuetoken URL
        base = endpoint.split("/sts/")[0] if "/sts/" in endpoint else endpoint
    else:
        base = f"https://{region}.api.cognitive.azure.cn"

    definition = json.dumps({
        "locales": ["zh-CN", "en-US"],
        "profanityFilterMode": "None",
        "diarizationSettings": {
            "minSpeakers": 1,
            "maxSpeakers": 10,
        },
    })

    headers = {"Ocp-Apim-Subscription-Key": api_key}
    with open(filepath, "rb") as f:
        resp = http.post(
            f"{base}/speechtotext/transcriptions:transcribe?api-version=2024-11-15",
            headers=headers,
            files={
                "audio": (os.path.basename(filepath), f),
                "definition": (None, definition, "application/json"),
            },
            timeout=300,
        )
    resp.raise_for_status()
    data = resp.json()

    # Build diarized output from phrases
    phrases = data.get("phrases", [])
    if phrases:
        speaker_map = {}
        segments = []
        for p in phrases:
            spk = p.get("speaker", 1)
            if spk not in speaker_map:
                speaker_map[spk] = f"Speaker {len(speaker_map) + 1}"
            offset_ms = p.get("offsetMilliseconds", 0)
            duration_ms = p.get("durationMilliseconds", 0)
            segments.append({
                "start_time": _seconds_to_hms(offset_ms / 1000),
                "end_time": _seconds_to_hms((offset_ms + duration_ms) / 1000),
                "speaker": speaker_map[spk],
                "text": p.get("text", ""),
            })
        return json.dumps({
            "metadata": {"language": "zh", "total_speakers": len(speaker_map)},
            "segments": segments,
        }, ensure_ascii=False, indent=2)

    combined = data.get("combinedPhrases", [])
    if combined:
        return combined[0].get("text", "")
    return ""


ASR_HANDLERS = {
    "OpenAI":       lambda c, fp: transcribe_openai_compatible(c, fp, "https://api.openai.com/v1"),
    "Groq":         lambda c, fp: transcribe_openai_compatible(c, fp, "https://api.groq.com/openai/v1"),
    "Deepgram":     transcribe_deepgram,
    "ElevenLabs":   transcribe_elevenlabs,
    "火山云":       transcribe_volcengine,
    "Soniox":       transcribe_soniox,
    "腾讯云":       transcribe_tencent,
    "微软-Global":  transcribe_microsoft_global,
    "微软-世纪互联": transcribe_microsoft_cn,
    "阿里云":       transcribe_aliyun,
    "讯飞":         transcribe_xfyun,
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
            {"role": "system", "content": LLM_PROMPT},
            {"role": "user", "content": text},
        ],
        "temperature": 0.3,
        "max_tokens": 4096,
    }
    resp = http.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=120)
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
            {"role": "system", "content": LLM_PROMPT},
            {"role": "user", "content": text},
        ],
        "temperature": 0.3,
        "max_tokens": 4096,
    }
    url = f"{base_url}/chat/completions"
    if group_id:
        url += f"?GroupId={group_id}"
    resp = http.post(url, headers=headers, json=payload, timeout=120)
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


def _find_cached(source_file, asr_vendor, llm_vendor):
    """Search output/ for a previous successful task with the same file + vendors.
    Returns (cached_transcript, cached_summary) — either may be None."""
    cached_transcript = None
    cached_summary = None
    if not os.path.isdir(OUTPUT_DIR):
        return None, None
    for tid in sorted(os.listdir(OUTPUT_DIR), reverse=True):
        meta_path = os.path.join(OUTPUT_DIR, tid, "meta.json")
        if not os.path.isfile(meta_path):
            continue
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                m = json.load(f)
        except Exception:
            continue
        if m.get("source_file") != source_file:
            continue
        # Check ASR cache
        if cached_transcript is None and m.get("asr_vendor") == asr_vendor and m.get("asr_status") == "success":
            tp = os.path.join(OUTPUT_DIR, tid, "transcript.txt")
            if os.path.isfile(tp):
                with open(tp, "r", encoding="utf-8") as f:
                    cached_transcript = f.read()
        # Check LLM cache (same file + same ASR vendor + same LLM vendor)
        if cached_summary is None and m.get("asr_vendor") == asr_vendor and m.get("llm_vendor") == llm_vendor and m.get("llm_status") == "success":
            sp = os.path.join(OUTPUT_DIR, tid, "summary.txt")
            if os.path.isfile(sp):
                with open(sp, "r", encoding="utf-8") as f:
                    cached_summary = f.read()
        if cached_transcript and cached_summary:
            break
    return cached_transcript, cached_summary


@app.route("/api/process", methods=["POST"])
def process_file():
    """Upload media → ASR transcription → LLM summary. Streams progress via SSE."""
    from flask import Response, stream_with_context

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

    # Generate task key
    task_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
    task_dir = os.path.join(OUTPUT_DIR, task_id)
    os.makedirs(task_dir, exist_ok=True)

    # Save uploaded file
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    meta = {
        "task_id": task_id,
        "created_at": datetime.now().isoformat(),
        "source_file": file.filename,
        "asr_vendor": asr_vendor,
        "llm_vendor": llm_vendor,
    }

    def sse_event(event, data):
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    def generate():
        transcript = ""
        summary = ""

        # Check cache for previous results with same file + vendors
        cached_transcript, cached_summary = _find_cached(file.filename, asr_vendor, llm_vendor)

        try:
            # Step 1: Upload complete
            yield sse_event("progress", {"step": "upload", "percent": 15, "message": "文件上传完成"})

            # Copy source file into task folder for archival
            import shutil
            source_copy = os.path.join(task_dir, "source_" + filename)
            if os.path.exists(filepath):
                shutil.copy2(filepath, source_copy)

            # Step 2: ASR — use cache or call API
            if cached_transcript:
                transcript = cached_transcript
                yield sse_event("progress", {"step": "asr_done", "percent": 60, "message": f"✅ 命中缓存：{asr_vendor} 转录结果（来自历史任务）"})
                yield sse_event("transcript", {"text": transcript})
                meta["asr_status"] = "cached"
                # Save cached copy to new task dir
                with open(os.path.join(task_dir, "transcript.txt"), "w", encoding="utf-8") as f:
                    f.write(transcript)
            else:
                yield sse_event("progress", {"step": "asr", "percent": 20, "message": f"正在调用 {asr_vendor} 进行语音识别..."})

                asr_handler = ASR_HANDLERS.get(asr_vendor)
                if not asr_handler:
                    yield sse_event("error", {"message": f"ASR 供应商 '{asr_vendor}' 暂未实现接口对接"})
                    return

                transcript = asr_handler(asr_creds, filepath)

                if not transcript.strip():
                    yield sse_event("error", {"message": "转录结果为空，请检查音频文件是否包含语音内容"})
                    return

                with open(os.path.join(task_dir, "transcript.txt"), "w", encoding="utf-8") as f:
                    f.write(transcript)
                # Save raw ASR request/response log
                with open(os.path.join(task_dir, "asr_log.json"), "w", encoding="utf-8") as f:
                    json.dump({
                        "vendor": asr_vendor,
                        "input": {"file": file.filename, "file_size_bytes": os.path.getsize(filepath) if os.path.exists(filepath) else 0},
                        "output": {"transcript_length": len(transcript), "transcript_preview": transcript[:500]},
                        "timestamp": datetime.now().isoformat(),
                    }, f, ensure_ascii=False, indent=2)
                meta["asr_status"] = "success"

                yield sse_event("progress", {"step": "asr_done", "percent": 60, "message": f"{asr_vendor} 语音识别完成"})
                yield sse_event("transcript", {"text": transcript})

            # Step 3: LLM — use cache or call API
            if cached_summary:
                summary = cached_summary
                yield sse_event("progress", {"step": "llm_done", "percent": 95, "message": f"✅ 命中缓存：{llm_vendor} 摘要结果（来自历史任务）"})
                yield sse_event("summary", {"text": summary})
                meta["llm_status"] = "cached"
                with open(os.path.join(task_dir, "summary.txt"), "w", encoding="utf-8") as f:
                    f.write(summary)
            else:
                yield sse_event("progress", {"step": "llm", "percent": 65, "message": f"正在调用 {llm_vendor} 生成摘要..."})

                llm_handler = LLM_HANDLERS.get(llm_vendor)
                if not llm_handler:
                    yield sse_event("error", {"message": f"LLM 供应商 '{llm_vendor}' 暂未实现接口对接"})
                    return

                summary = llm_handler(llm_creds, transcript)

                with open(os.path.join(task_dir, "summary.txt"), "w", encoding="utf-8") as f:
                    f.write(summary)
                # Save raw LLM request/response log
                with open(os.path.join(task_dir, "llm_log.json"), "w", encoding="utf-8") as f:
                    json.dump({
                        "vendor": llm_vendor,
                        "input": {"transcript_length": len(transcript), "transcript_preview": transcript[:500]},
                        "output": {"summary_length": len(summary), "summary_preview": summary[:500]},
                        "timestamp": datetime.now().isoformat(),
                    }, f, ensure_ascii=False, indent=2)
                meta["llm_status"] = "success"

                yield sse_event("progress", {"step": "llm_done", "percent": 95, "message": f"{llm_vendor} 摘要生成完成"})
                yield sse_event("summary", {"text": summary})

            # Save metadata
            with open(os.path.join(task_dir, "meta.json"), "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)

            yield sse_event("done", {"task_id": task_id, "percent": 100, "message": "全部处理完成"})

        except requests.exceptions.HTTPError as e:
            detail = ""
            try:
                detail = e.response.json()
            except Exception:
                detail = e.response.text[:500] if e.response else str(e)
            meta["error"] = f"API 调用失败: {detail}"
            with open(os.path.join(task_dir, "meta.json"), "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
            yield sse_event("error", {"message": f"API 调用失败: {detail}"})
        except Exception as e:
            meta["error"] = str(e)
            with open(os.path.join(task_dir, "meta.json"), "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
            yield sse_event("error", {"message": f"处理失败: {str(e)}"})
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


@app.route("/api/tasks")
def list_tasks():
    """List all completed tasks."""
    tasks = []
    if not os.path.isdir(OUTPUT_DIR):
        return jsonify(tasks)
    for task_id in sorted(os.listdir(OUTPUT_DIR), reverse=True):
        meta_path = os.path.join(OUTPUT_DIR, task_id, "meta.json")
        if os.path.isfile(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                tasks.append(json.load(f))
    return jsonify(tasks)


@app.route("/api/tasks/<task_id>")
def get_task(task_id):
    """Get a specific task's outputs."""
    task_dir = os.path.join(OUTPUT_DIR, secure_filename(task_id))
    if not os.path.isdir(task_dir):
        return jsonify({"error": "任务不存在"}), 404
    result = {}
    meta_path = os.path.join(task_dir, "meta.json")
    if os.path.isfile(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            result["meta"] = json.load(f)
    for fname, key in [("transcript.txt", "transcript"), ("summary.txt", "summary")]:
        fpath = os.path.join(task_dir, fname)
        if os.path.isfile(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                result[key] = f.read()
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8080)
