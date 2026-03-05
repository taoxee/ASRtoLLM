"""Utility functions: file validation, time conversion, cache lookup, audio transcoding."""
import os
import json
import shutil
import subprocess
import logging

from app.config import ALLOWED_EXTENSIONS, OUTPUT_DIR

logger = logging.getLogger(__name__)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def seconds_to_hms(seconds):
    """Convert seconds (float) to HH:MM:SS string."""
    s = int(seconds)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def find_cached(source_file, asr_vendor, llm_vendor, llm_model=""):
    """Search output/ for a previous successful task with the same file + vendors + model.
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
        if cached_transcript is None and m.get("asr_vendor") == asr_vendor and m.get("asr_status") == "success":
            tp = os.path.join(OUTPUT_DIR, tid, "transcript.txt")
            if os.path.isfile(tp):
                with open(tp, "r", encoding="utf-8") as f:
                    cached_transcript = f.read()
        if cached_summary is None and m.get("asr_vendor") == asr_vendor and m.get("llm_vendor") == llm_vendor and m.get("llm_status") == "success":
            # Also match llm_model: both empty means default, otherwise must match exactly
            cached_model = m.get("llm_model", "")
            if cached_model == llm_model:
                sp = os.path.join(OUTPUT_DIR, tid, "summary.txt")
                if os.path.isfile(sp):
                    with open(sp, "r", encoding="utf-8") as f:
                        cached_summary = f.read()
        if cached_transcript and cached_summary:
            break
    return cached_transcript, cached_summary


# ── Audio transcoding ────────────────────────────────────────────────

def _ffmpeg_available():
    """Check if ffmpeg is available — system PATH or pip-installed static-ffmpeg."""
    if shutil.which("ffmpeg"):
        return True
    # Try static-ffmpeg (pip install static-ffmpeg)
    try:
        import static_ffmpeg
        static_ffmpeg.add_paths()
        return shutil.which("ffmpeg") is not None
    except ImportError:
        return False


def get_audio_duration(filepath):
    """Get audio duration in seconds using ffprobe. Returns None if unavailable."""
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    try:
        result = subprocess.run(
            [ffprobe, "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", filepath],
            capture_output=True, text=True, timeout=30,
        )
        return float(result.stdout.strip()) if result.returncode == 0 else None
    except Exception:
        return None


def transcode_audio(filepath, target_dir=None):
    """Transcode audio/video to 16kHz mono MP3 (speech-optimized, ~28MB/hr).

    Returns (transcoded_path, info_dict) where info_dict contains:
      - original_size: bytes
      - transcoded_size: bytes
      - duration_seconds: float or None
      - skipped: bool (True if ffmpeg unavailable or file already small MP3)
      - reason: str

    If ffmpeg is not available, returns the original filepath unchanged.
    """
    original_size = os.path.getsize(filepath)
    info = {
        "original_size": original_size,
        "transcoded_size": original_size,
        "duration_seconds": None,
        "skipped": False,
        "reason": "",
    }

    if not _ffmpeg_available():
        info["skipped"] = True
        info["reason"] = "ffmpeg not installed"
        logger.error("ffmpeg not found! Please install ffmpeg: https://ffmpeg.org/download.html")
        return filepath, info

    # Skip if already a small MP3 (under 24MB — leaves headroom for 25MB vendor limits)
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".mp3" and original_size < 24 * 1024 * 1024:
        info["skipped"] = True
        info["reason"] = "already small MP3"
        return filepath, info

    # Get duration for logging
    info["duration_seconds"] = get_audio_duration(filepath)

    # Build output path
    if target_dir is None:
        target_dir = os.path.dirname(filepath)
    base = os.path.splitext(os.path.basename(filepath))[0]
    out_path = os.path.join(target_dir, base + "_transcoded.mp3")

    try:
        cmd = [
            "ffmpeg", "-y", "-i", filepath,
            "-vn",                    # strip video
            "-ac", "1",               # mono
            "-ar", "16000",           # 16kHz sample rate
            "-b:a", "64k",            # 64kbps bitrate (speech-quality)
            "-map_metadata", "-1",    # strip metadata
            out_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            logger.error(f"ffmpeg transcode failed: {result.stderr[-500:]}")
            info["skipped"] = True
            info["reason"] = f"ffmpeg error: {result.stderr[-200:]}"
            return filepath, info

        info["transcoded_size"] = os.path.getsize(out_path)
        info["reason"] = "transcoded to 16kHz mono MP3"
        logger.info(
            f"Transcoded: {original_size / 1024 / 1024:.1f}MB → "
            f"{info['transcoded_size'] / 1024 / 1024:.1f}MB "
            f"({info['transcoded_size'] / original_size * 100:.0f}%)"
        )
        return out_path, info

    except subprocess.TimeoutExpired:
        info["skipped"] = True
        info["reason"] = "ffmpeg timeout (>10min)"
        logger.error("ffmpeg transcode timed out")
        return filepath, info
    except Exception as e:
        info["skipped"] = True
        info["reason"] = f"transcode error: {str(e)}"
        logger.error(f"Transcode error: {e}")
        return filepath, info
