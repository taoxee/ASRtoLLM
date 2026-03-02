"""Configuration: paths, proxy, vendor definitions, prompt templates."""
import os
import tempfile

# ── Paths ────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
UPLOAD_FOLDER = tempfile.mkdtemp()

os.makedirs(OUTPUT_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {"mp3", "mp4", "wav", "m4a", "webm", "ogg", "flac", "mpeg", "mpga"}


# ── Proxy auto-detection ─────────────────────────────────────────────
def _detect_proxy():
    """Detect system proxy: env var > macOS scutil > none."""
    env_proxy = os.environ.get("HTTPS_PROXY", "") or os.environ.get("https_proxy", "")
    if env_proxy.strip():
        return env_proxy.strip()
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
        if proxy_info.get("SOCKSEnable") == "1":
            host = proxy_info.get("SOCKSProxy", "127.0.0.1")
            port = proxy_info.get("SOCKSPort", "1080")
            return f"socks5h://{host}:{port}"
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


import requests

PROXY_URL = _detect_proxy()

http = requests.Session()
if PROXY_URL:
    http.proxies.update({"http": PROXY_URL, "https": PROXY_URL})
    print(f"[Proxy] Using: {PROXY_URL}")
else:
    print("[Proxy] No proxy detected, using direct connection")


# ── Prompt templates ─────────────────────────────────────────────────
def _load_prompt(filename, fallback=""):
    # Check data/ first, then project root as fallback
    for d in [DATA_DIR, BASE_DIR]:
        path = os.path.join(d, filename)
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
    return fallback


ASR_PROMPT = _load_prompt("ASR_prompt.txt")
LLM_PROMPT = _load_prompt("LLM_prompt.txt")


# ── Vendor definitions ───────────────────────────────────────────────
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
