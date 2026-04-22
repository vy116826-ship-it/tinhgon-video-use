"""Auto-editor engine — automated video editing decisions.

Replaces the Claude Code conversation-driven approach with rule-based
automation for silence detection, filler word removal, and EDL generation.
"""
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional


# ── Filler word patterns ────────────────────────────────────────────────

DEFAULT_FILLER_PATTERNS = [
    r"\bumm?\b", r"\buh+\b", r"\bah+\b", r"\blike\b",
    r"\byou know\b", r"\bso\b", r"\bbasically\b",
    r"\bactually\b", r"\bliterally\b", r"\bkind of\b",
    r"\bsort of\b", r"\bi mean\b",
]


def detect_silences(transcript_data: dict, threshold_ms: int = 400) -> List[Dict]:
    """Find silence gaps in a transcript that exceed the threshold.

    Returns list of {start, end, duration} for each silence gap.
    """
    silences = []
    words = transcript_data.get("words", [])

    for i in range(len(words) - 1):
        current_end = words[i].get("end", 0)
        next_start = words[i + 1].get("start", 0)
        gap = next_start - current_end

        if gap >= threshold_ms / 1000.0:
            silences.append({
                "start": current_end,
                "end": next_start,
                "duration": gap,
                "after_word": words[i].get("text", ""),
                "before_word": words[i + 1].get("text", ""),
            })

    return silences


def detect_fillers(
    transcript_data: dict,
    filler_words: Optional[List[str]] = None,
) -> List[Dict]:
    """Find filler words in the transcript.

    Returns list of {start, end, text, index} for each filler occurrence.
    """
    if filler_words is None:
        patterns = DEFAULT_FILLER_PATTERNS
    else:
        patterns = [rf"\b{re.escape(w)}\b" for w in filler_words]

    combined = re.compile("|".join(patterns), re.IGNORECASE)
    fillers = []
    words = transcript_data.get("words", [])

    for i, word in enumerate(words):
        text = word.get("text", "").strip()
        if combined.match(text):
            fillers.append({
                "start": word.get("start", 0),
                "end": word.get("end", 0),
                "text": text,
                "index": i,
            })

    return fillers


def generate_edl(
    sources: Dict[str, str],
    transcripts: Dict[str, dict],
    config: dict,
) -> dict:
    """Generate an Edit Decision List (EDL) based on automated analysis.

    Args:
        sources: {source_id: filepath}
        transcripts: {source_id: transcript_data}
        config: job configuration dict

    Returns:
        EDL dict matching the video-use format
    """
    silence_threshold = config.get("silence_threshold_ms", 400)
    remove_fillers = config.get("filler_remove", True)
    filler_words = config.get("filler_words", None)
    grade = config.get("grade_preset", "none")

    ranges = []

    for source_id, transcript in transcripts.items():
        words = transcript.get("words", [])
        if not words:
            continue

        # Find regions to remove
        remove_ranges = []

        # 1. Detect silences to cut
        if config.get("silence_remove", True):
            silences = detect_silences(transcript, silence_threshold)
            for s in silences:
                remove_ranges.append((s["start"], s["end"]))

        # 2. Detect fillers to remove
        if remove_fillers:
            fillers = detect_fillers(transcript, filler_words)
            for f in fillers:
                # Extend slightly to cover the gap around the filler
                remove_ranges.append((f["start"] - 0.03, f["end"] + 0.03))

        # 3. Merge overlapping remove ranges
        remove_ranges.sort(key=lambda x: x[0])
        merged = []
        for start, end in remove_ranges:
            if merged and start <= merged[-1][1] + 0.05:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))

        # 4. Invert to get keep ranges
        keep_ranges = []
        video_start = words[0].get("start", 0) - 0.05  # 50ms padding
        video_end = words[-1].get("end", 0) + 0.08      # 80ms padding

        prev_end = video_start
        for rm_start, rm_end in merged:
            if rm_start > prev_end:
                keep_ranges.append((max(prev_end, 0), rm_start))
            prev_end = rm_end
        if prev_end < video_end:
            keep_ranges.append((prev_end, video_end))

        # 5. Filter out very short segments (< 200ms)
        keep_ranges = [(s, e) for s, e in keep_ranges if e - s >= 0.2]

        # 6. Create EDL ranges
        for i, (start, end) in enumerate(keep_ranges):
            # Find the text in this range
            segment_words = [
                w["text"] for w in words
                if w.get("start", 0) >= start and w.get("end", 0) <= end
            ]

            ranges.append({
                "source": source_id,
                "start": round(start, 3),
                "end": round(end, 3),
                "beat": f"SEGMENT_{i+1}",
                "quote": " ".join(segment_words[:10]),
                "reason": "auto-cut",
            })

    # Calculate total duration
    total_duration = sum(r["end"] - r["start"] for r in ranges)

    edl = {
        "version": 1,
        "sources": sources,
        "ranges": ranges,
        "grade": grade,
        "overlays": [],
        "subtitles": "",
        "total_duration_s": round(total_duration, 2),
    }

    return edl


def generate_srt(
    transcripts: Dict[str, dict],
    edl: dict,
    style: str = "bold-overlay",
) -> str:
    """Generate SRT subtitles aligned to the EDL output timeline.

    Uses output-timeline offsets: output_time = word.start - segment_start + segment_offset
    """
    srt_entries = []
    output_offset = 0.0
    srt_index = 1

    for segment in edl.get("ranges", []):
        source_id = segment["source"]
        seg_start = segment["start"]
        seg_end = segment["end"]
        seg_duration = seg_end - seg_start

        transcript = transcripts.get(source_id, {})
        words = transcript.get("words", [])

        # Get words within this segment
        segment_words = [
            w for w in words
            if w.get("start", 0) >= seg_start - 0.05 and w.get("end", 0) <= seg_end + 0.05
        ]

        if style == "bold-overlay":
            # 2-word UPPERCASE chunks
            chunk_size = 2
        elif style == "natural-sentence":
            chunk_size = 5
        else:
            chunk_size = 3

        for i in range(0, len(segment_words), chunk_size):
            chunk = segment_words[i:i + chunk_size]
            if not chunk:
                continue

            # Calculate output-timeline offsets
            word_start = chunk[0].get("start", 0)
            word_end = chunk[-1].get("end", 0)
            out_start = word_start - seg_start + output_offset
            out_end = word_end - seg_start + output_offset

            text = " ".join(w.get("text", "") for w in chunk)
            if style == "bold-overlay":
                text = text.upper()

            srt_entries.append(
                f"{srt_index}\n"
                f"{_format_srt_time(out_start)} --> {_format_srt_time(out_end)}\n"
                f"{text}\n"
            )
            srt_index += 1

        output_offset += seg_duration

    return "\n".join(srt_entries)


def _format_srt_time(seconds: float) -> str:
    """Format seconds to SRT timestamp: HH:MM:SS,mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
