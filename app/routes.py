"""All Flask route definitions."""
import os
import json
import uuid
import shutil
import threading
from datetime import datetime
from collections import OrderedDict

import requests
from flask import Blueprint, request, jsonify, send_from_directory, Response, stream_with_context
from werkzeug.utils import secure_filename

from app.config import VENDORS, OUTPUT_DIR, UPLOAD_FOLDER, DATA_DIR
from app.utils import allowed_file, find_cached
from app.services import ASR_HANDLERS, LLM_HANDLERS

bp = Blueprint("main", __name__)

# ── Task queue for parallel processing ───────────────────────────────
_task_lock = threading.Lock()
_task_queue = OrderedDict()


@bp.route("/")
def index():
    from app.config import BASE_DIR
    return send_from_directory(os.path.join(BASE_DIR, "static"), "index.html")


@bp.route("/api/vendors")
def get_vendors():
    return jsonify(VENDORS)


@bp.route("/api/import-keys")
def import_keys_route():
    """Auto-detect vendor credentials from env vars, .env, vendor_keys.csv."""
    from import_keys import detect_all
    from app.config import BASE_DIR
    # Check data/ first, then project root as fallback
    csv_path = os.path.join(DATA_DIR, "vendor_keys.csv")
    if not os.path.isfile(csv_path):
        csv_path = os.path.join(BASE_DIR, "vendor_keys.csv")
    env_path = os.path.join(DATA_DIR, ".env")
    if not os.path.isfile(env_path):
        env_path = os.path.join(BASE_DIR, ".env")
    creds = detect_all(
        env_file=env_path if os.path.isfile(env_path) else None,
        csv_file=csv_path,
    )
    return jsonify(creds)


@bp.route("/api/process", methods=["POST"])
def process_file():
    """Upload media → ASR transcription → LLM summary. Streams progress via SSE."""
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

    task_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
    task_dir = os.path.join(OUTPUT_DIR, task_id)
    os.makedirs(task_dir, exist_ok=True)

    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    meta = {
        "task_id": task_id,
        "created_at": datetime.now().isoformat(),
        "source_file": file.filename,
        "asr_vendor": asr_vendor,
        "llm_vendor": llm_vendor,
    }

    with _task_lock:
        _task_queue[task_id] = {"status": "running", "source_file": file.filename,
                                "asr_vendor": asr_vendor, "llm_vendor": llm_vendor,
                                "created_at": meta["created_at"]}

    def sse_event(event, data):
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    def generate():
        transcript = ""
        summary = ""
        token_usage = {}

        cached_transcript, cached_summary = find_cached(file.filename, asr_vendor, llm_vendor)

        try:
            yield sse_event("progress", {"step": "upload", "percent": 15, "message": "文件上传完成"})

            source_copy = os.path.join(task_dir, "source_" + filename)
            if os.path.exists(filepath):
                shutil.copy2(filepath, source_copy)

            # ASR
            if cached_transcript:
                transcript = cached_transcript
                yield sse_event("progress", {"step": "asr_done", "percent": 60, "message": f"✅ 命中缓存：{asr_vendor} 转录结果（来自历史任务）"})
                yield sse_event("transcript", {"text": transcript})
                meta["asr_status"] = "cached"
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

            # LLM
            if cached_summary:
                summary = cached_summary
                yield sse_event("progress", {"step": "llm_done", "percent": 95, "message": f"✅ 命中缓存：{llm_vendor} 摘要结果（来自历史任务）"})
                yield sse_event("summary", {"text": summary})
                meta["llm_status"] = "cached"
                with open(os.path.join(task_dir, "summary.txt"), "w", encoding="utf-8") as f:
                    f.write(summary)
            else:
                yield sse_event("progress", {"step": "llm", "percent": 65, "message": f"正在调用 {llm_vendor} 生成会议纪要..."})
                llm_handler = LLM_HANDLERS.get(llm_vendor)
                if not llm_handler:
                    yield sse_event("error", {"message": f"LLM 供应商 '{llm_vendor}' 暂未实现接口对接"})
                    return

                llm_result = llm_handler(llm_creds, transcript)
                if isinstance(llm_result, tuple):
                    summary, token_usage = llm_result
                else:
                    summary = llm_result

                with open(os.path.join(task_dir, "summary.txt"), "w", encoding="utf-8") as f:
                    f.write(summary)
                llm_log = {
                    "vendor": llm_vendor,
                    "input": {"transcript_length": len(transcript), "transcript_preview": transcript[:500]},
                    "output": {"summary_length": len(summary), "summary_preview": summary[:500]},
                    "timestamp": datetime.now().isoformat(),
                }
                if token_usage:
                    llm_log["token_usage"] = token_usage
                with open(os.path.join(task_dir, "llm_log.json"), "w", encoding="utf-8") as f:
                    json.dump(llm_log, f, ensure_ascii=False, indent=2)
                meta["llm_status"] = "success"
                yield sse_event("progress", {"step": "llm_done", "percent": 95, "message": f"{llm_vendor} 会议纪要生成完成"})
                yield sse_event("summary", {"text": summary})

            if token_usage:
                meta["token_usage"] = token_usage

            with open(os.path.join(task_dir, "meta.json"), "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)

            yield sse_event("done", {"task_id": task_id, "percent": 100, "message": "全部处理完成",
                                     "token_usage": token_usage})

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
            with _task_lock:
                if task_id in _task_queue:
                    _task_queue[task_id]["status"] = "done" if not meta.get("error") else "error"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


@bp.route("/api/queue")
def get_queue():
    with _task_lock:
        return jsonify(list(_task_queue.values()))


@bp.route("/api/tasks")
def list_tasks():
    tasks = []
    if not os.path.isdir(OUTPUT_DIR):
        return jsonify(tasks)
    for tid in sorted(os.listdir(OUTPUT_DIR), reverse=True):
        meta_path = os.path.join(OUTPUT_DIR, tid, "meta.json")
        if os.path.isfile(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                tasks.append(json.load(f))
    return jsonify(tasks)


@bp.route("/api/tasks/<task_id>")
def get_task(task_id):
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
