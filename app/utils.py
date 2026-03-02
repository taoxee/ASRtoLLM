"""Utility functions: file validation, time conversion, cache lookup."""
import os
import json

from app.config import ALLOWED_EXTENSIONS, OUTPUT_DIR


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def seconds_to_hms(seconds):
    """Convert seconds (float) to HH:MM:SS string."""
    s = int(seconds)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def find_cached(source_file, asr_vendor, llm_vendor):
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
        if cached_transcript is None and m.get("asr_vendor") == asr_vendor and m.get("asr_status") == "success":
            tp = os.path.join(OUTPUT_DIR, tid, "transcript.txt")
            if os.path.isfile(tp):
                with open(tp, "r", encoding="utf-8") as f:
                    cached_transcript = f.read()
        if cached_summary is None and m.get("asr_vendor") == asr_vendor and m.get("llm_vendor") == llm_vendor and m.get("llm_status") == "success":
            sp = os.path.join(OUTPUT_DIR, tid, "summary.txt")
            if os.path.isfile(sp):
                with open(sp, "r", encoding="utf-8") as f:
                    cached_summary = f.read()
        if cached_transcript and cached_summary:
            break
    return cached_transcript, cached_summary
