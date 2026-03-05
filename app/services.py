"""Core business logic: ASR transcription and LLM summarization handlers."""
import os
import json
import uuid
import requests
from datetime import datetime

from app.config import http, LLM_PROMPT
from app.utils import seconds_to_hms


# ═══════════════════════════════════════════════════════════════════════
#  ASR Handlers
# ═══════════════════════════════════════════════════════════════════════

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
                "start_time": seconds_to_hms(s.get("start", 0)),
                "end_time": seconds_to_hms(s.get("end", 0)),
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
                "start_time": seconds_to_hms(u.get("start", 0)),
                "end_time": seconds_to_hms(u.get("end", 0)),
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
    import time as _time
    api_key = creds.get("api_key", "")
    headers = {"xi-api-key": api_key}
    form_data = {
        "model_id": "scribe_v1",
        "diarize": "true",
        "timestamps_granularity": "word",
    }
    url = "https://api.elevenlabs.io/v1/speech-to-text"

    # Retry up to 3 times — proxy connections can drop on large uploads
    last_err = None
    for attempt in range(3):
        try:
            with open(filepath, "rb") as f:
                resp = http.post(
                    url,
                    headers=headers,
                    files={"file": (os.path.basename(filepath), f)},
                    data=form_data,
                    timeout=600,
                )
            resp.raise_for_status()
            break
        except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError) as e:
            last_err = e
            if attempt < 2:
                _time.sleep(2 * (attempt + 1))
                continue
            # Last attempt: try direct connection (no proxy)
            try:
                direct = requests.Session()
                direct.proxies = {"http": "", "https": ""}
                with open(filepath, "rb") as f:
                    resp = direct.post(
                        url,
                        headers=headers,
                        files={"file": (os.path.basename(filepath), f)},
                        data=form_data,
                        timeout=600,
                    )
                resp.raise_for_status()
                break
            except Exception:
                raise last_err

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
                        "start_time": seconds_to_hms(current_start),
                        "end_time": seconds_to_hms(current_end),
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
                "start_time": seconds_to_hms(current_start),
                "end_time": seconds_to_hms(current_end),
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
                        "start_time": seconds_to_hms(u.get("start_time", 0) / 1000),
                        "end_time": seconds_to_hms(u.get("end_time", 0) / 1000),
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
                            "start_time": seconds_to_hms(current_start / 1000),
                            "end_time": seconds_to_hms(current_end / 1000),
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
                    "start_time": seconds_to_hms(current_start / 1000),
                    "end_time": seconds_to_hms(current_end / 1000),
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
                            "start_time": seconds_to_hms(s.get("start_time", 0) / 1000),
                            "end_time": seconds_to_hms(s.get("end_time", 0) / 1000),
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
                "start_time": seconds_to_hms(offset_ms / 1000),
                "end_time": seconds_to_hms((offset_ms + duration_ms) / 1000),
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
                                    "start_time": seconds_to_hms(bg / 1000),
                                    "end_time": seconds_to_hms(ed / 1000),
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
    """阿里云 ASR via DashScope Paraformer REST API.
    DashScope only accepts file_urls (no direct upload/base64).
    Strategy: serve the file temporarily via the Flask app, then pass the URL."""
    import time as _time

    api_key = creds.get("api_key", "")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable",
    }

    # Copy file to static/tmp/ so Flask can serve it
    tmp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    tmp_name = uuid.uuid4().hex + "_" + os.path.basename(filepath)
    tmp_path = os.path.join(tmp_dir, tmp_name)
    import shutil
    shutil.copy2(filepath, tmp_path)

    # Build a publicly accessible URL — user must ensure the server is reachable
    # For local dev, this won't work with DashScope (needs public URL)
    # So we also try the oss:// upload credential approach
    try:
        # Step 1: Try to get an upload credential from DashScope
        cred_resp = http.get(
            "https://dashscope.aliyuncs.com/api/v1/uploads",
            headers={"Authorization": f"Bearer {api_key}"},
            params={"action": "getPolicy", "model": "paraformer-v2"},
            timeout=30,
        )
        cred_resp.raise_for_status()
        cred_data = cred_resp.json().get("data", {})
        oss_access_key_id = cred_data.get("oss_access_key_id", "")
        policy = cred_data.get("policy", "")
        signature = cred_data.get("signature", "")
        upload_dir = cred_data.get("upload_dir", "")
        upload_host = cred_data.get("upload_host", "")
        x_oss_object_acl = cred_data.get("x_oss_object_acl", "")
        x_oss_forbid_overwrite = cred_data.get("x_oss_forbid_overwrite", "")

        if upload_host and policy:
            # Step 2: Upload file to DashScope OSS
            oss_key = f"{upload_dir}/{tmp_name}"
            with open(filepath, "rb") as f:
                upload_resp = http.post(
                    upload_host,
                    data={
                        "OSSAccessKeyId": oss_access_key_id,
                        "policy": policy,
                        "Signature": signature,
                        "key": oss_key,
                        "x-oss-object-acl": x_oss_object_acl,
                        "x-oss-forbid-overwrite": x_oss_forbid_overwrite,
                        "success_action_status": "200",
                    },
                    files={"file": (tmp_name, f)},
                    timeout=300,
                )
            upload_resp.raise_for_status()
            file_url = f"oss://{oss_key}"
        else:
            raise Exception("无法获取上传凭证")
    except Exception:
        # Fallback: clean up and raise a helpful error
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise Exception(
            "阿里云 ASR 需要可公网访问的文件URL。请将音频文件上传至 OSS 或其他公网存储后重试。"
            "DashScope 不支持直接上传本地文件或 base64 编码。"
        )
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    # Step 3: Submit transcription task
    payload = {
        "model": "paraformer-v2",
        "input": {"file_urls": [file_url]},
        "parameters": {
            "language_hints": ["zh", "en"],
            "diarization_enabled": True,
        },
    }
    resp = http.post(
        "https://dashscope.aliyuncs.com/api/v1/services/audio/asr/transcription",
        headers=headers,
        json=payload,
        timeout=120,
    )
    resp.raise_for_status()
    result = resp.json()
    task_id = result.get("output", {}).get("task_id", "")
    if not task_id:
        raise Exception(f"阿里云 ASR 提交失败: {result}")

    # Step 4: Poll task status
    for _ in range(180):
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
            results = result.get("output", {}).get("results", [])
            if results and results[0].get("subtask_status") == "SUCCEEDED":
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
                                    "start_time": seconds_to_hms(s.get("begin_time", 0) / 1000),
                                    "end_time": seconds_to_hms(s.get("end_time", 0) / 1000),
                                    "speaker": speaker_map[spk],
                                    "text": s.get("text", ""),
                                })
                            return json.dumps({
                                "metadata": {"language": "zh", "total_speakers": len(speaker_map)},
                                "segments": segments,
                            }, ensure_ascii=False, indent=2)
                        return transcripts[0].get("text", "")
            # Check for subtask failure
            if results and results[0].get("subtask_status") == "FAILED":
                msg = results[0].get("message", "Unknown")
                raise Exception(f"阿里云 ASR 失败: {msg}")
            return ""
        elif status == "FAILED":
            msg = result.get("output", {}).get("message", "Unknown")
            raise Exception(f"阿里云 ASR 失败: {msg}")

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
                "start_time": seconds_to_hms(offset_ms / 1000),
                "end_time": seconds_to_hms((offset_ms + duration_ms) / 1000),
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
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    token_info = {
        "model": data.get("model", model),
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
    }
    return content, token_info




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
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    token_info = {
        "model": data.get("model", model),
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
    }
    return content, token_info



def summarize_tencent(creds, text, model=""):
    """腾讯云 uses SecretId/SecretKey — route through their OpenAI-compatible endpoint."""
    api_key = creds.get("secret_key", "")
    return summarize_openai_compatible(
        {"api_key": api_key}, text,
        "https://api.lkeap.cloud.tencent.com/v1", model or "deepseek-v3"
    )


def summarize_aliyun(creds, text, model=""):
    """阿里云 supports custom URL override."""
    custom_url = creds.get("url", "").strip().rstrip("/")
    base_url = custom_url if custom_url else "https://dashscope.aliyuncs.com/compatible-mode/v1"
    # Strip /chat/completions if user pasted the full endpoint
    if base_url.endswith("/chat/completions"):
        base_url = base_url.rsplit("/chat/completions", 1)[0]
    return summarize_openai_compatible(creds, text, base_url, model or "qwen-plus")


LLM_HANDLERS = {
    "OpenAI":         lambda c, text, model="": summarize_openai_compatible(c, text, "https://api.openai.com/v1", model or "gpt-4o"),
    "Groq":           lambda c, text, model="": summarize_openai_compatible(c, text, "https://api.groq.com/openai/v1", model or "llama-3.3-70b-versatile"),
    "智谱":           lambda c, text, model="": summarize_openai_compatible(c, text, "https://open.bigmodel.cn/api/paas/v4", model or "glm-4-flash"),
    "Minimax-CN":     lambda c, text, model="": summarize_minimax(c, text, "https://api.minimax.chat/v1", model or "MiniMax-Text-01"),
    "Minimax-Global": lambda c, text, model="": summarize_minimax(c, text, "https://api.minimaxi.chat/v1", model or "MiniMax-Text-01"),
    "腾讯云":         summarize_tencent,
    "阿里云":         summarize_aliyun,
}

