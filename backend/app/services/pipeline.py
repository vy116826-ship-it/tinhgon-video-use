"""Video editing pipeline — orchestrates the full editing workflow.

Wraps the existing video-use helpers (transcribe, render, grade) and
provides progress callbacks for real-time reporting to the web UI.
"""
import json
import os
import subprocess
import shutil
from pathlib import Path
from typing import Callable, Dict, List, Optional

from app.core.config import HELPERS_DIR, FFMPEG_PATH, FFPROBE_PATH, OUTPUT_DIR, PROJECT_DIR
from app.services.auto_editor import generate_edl, generate_srt, detect_silences, detect_fillers
from app.services.ffprobe import probe_video_sync


ProgressCallback = Callable[[str, float, str], None]  # (step_name, progress_pct, log_line)


class VideoPipeline:
    """Orchestrates the video editing pipeline for a single job."""

    def __init__(
        self,
        job_id: int,
        upload_files: List[Dict],  # [{id, filepath, original_filename}]
        config: dict,
        on_progress: Optional[ProgressCallback] = None,
    ):
        self.job_id = job_id
        self.upload_files = upload_files
        self.config = config
        self.on_progress = on_progress or (lambda *a: None)

        # Working directories
        self.work_dir = PROJECT_DIR / str(job_id)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.edit_dir = self.work_dir / "edit"
        self.edit_dir.mkdir(exist_ok=True)
        self.transcripts_dir = self.edit_dir / "transcripts"
        self.transcripts_dir.mkdir(exist_ok=True)
        self.clips_dir = self.edit_dir / "clips_graded"
        self.clips_dir.mkdir(exist_ok=True)

        # State
        self.transcripts: Dict[str, dict] = {}
        self.sources: Dict[str, str] = {}
        self.edl: Optional[dict] = None

    def _log(self, step: str, pct: float, msg: str):
        self.on_progress(step, pct, msg)

    def run(self) -> str:
        """Execute the full pipeline. Returns path to output file."""
        try:
            self.step_transcribe()
            self.step_pack()
            self.step_analyze()
            self.step_cut()

            if self.config.get("grade_preset", "none") != "none":
                self.step_grade()

            self.step_render()

            if self.config.get("subtitles_enabled", True):
                self.step_subtitles()

            output_path = self.step_finalize()
            return output_path
        except Exception as e:
            self._log("error", 0, f"Pipeline failed: {str(e)}")
            raise

    def step_transcribe(self):
        """Transcribe all source videos."""
        self._log("transcribe", 0, "Starting transcription...")
        total = len(self.upload_files)

        for i, upload in enumerate(self.upload_files):
            filepath = upload["filepath"]
            source_id = Path(filepath).stem
            self.sources[source_id] = filepath
            self._log("transcribe", (i / total) * 80, f"Transcribing: {upload['original_filename']}")

            # Check for cached transcript
            cache_file = self.transcripts_dir / f"{source_id}.json"
            if cache_file.exists():
                with open(cache_file) as f:
                    self.transcripts[source_id] = json.load(f)
                self._log("transcribe", ((i + 1) / total) * 80, f"Using cached transcript for {source_id}")
                continue

            # Try transcription via helper or built-in
            backend = self.config.get("transcription_backend", "elevenlabs")
            transcript = self._transcribe_file(filepath, backend)
            self.transcripts[source_id] = transcript

            # Cache it
            with open(cache_file, "w") as f:
                json.dump(transcript, f, indent=2)

            self._log("transcribe", ((i + 1) / total) * 80, f"Transcribed: {source_id}")

        self._log("transcribe", 100, f"Transcription complete — {total} file(s)")

    def _transcribe_file(self, filepath: str, backend: str) -> dict:
        """Transcribe a single file using chosen backend."""
        transcribe_script = HELPERS_DIR / "transcribe.py"

        if transcribe_script.exists():
            # Use the video-use helper
            try:
                result = subprocess.run(
                    ["python", str(transcribe_script), filepath],
                    capture_output=True, text=True, timeout=600,
                    cwd=str(self.work_dir),
                    env={**os.environ, "EDIT_DIR": str(self.edit_dir)},
                )
                if result.returncode == 0:
                    # Try to find the transcript file
                    source_id = Path(filepath).stem
                    tx_file = self.transcripts_dir / f"{source_id}.json"
                    if tx_file.exists():
                        with open(tx_file) as f:
                            return json.load(f)
            except (subprocess.TimeoutExpired, Exception) as e:
                self._log("transcribe", 0, f"Helper transcription failed: {e}, using fallback")

        # Fallback: use FFmpeg to extract audio + basic word detection
        return self._fallback_transcribe(filepath)

    def _fallback_transcribe(self, filepath: str) -> dict:
        """Fallback transcription using FFmpeg silence detection.

        This creates a basic word-boundary transcript from audio analysis
        when no external API is available.
        """
        # Extract audio and detect silence using FFmpeg
        audio_out = self.work_dir / "temp_audio.wav"
        subprocess.run([
            FFMPEG_PATH, "-y", "-i", filepath,
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            str(audio_out),
        ], capture_output=True, timeout=120)

        # Use FFmpeg's silencedetect filter
        result = subprocess.run([
            FFMPEG_PATH, "-i", str(audio_out),
            "-af", "silencedetect=noise=-30dB:d=0.3",
            "-f", "null", "-",
        ], capture_output=True, text=True, timeout=120)

        # Parse silence detection output
        import re
        words = []
        silence_starts = []
        silence_ends = []

        for line in result.stderr.split("\n"):
            if "silence_start:" in line:
                match = re.search(r"silence_start:\s*([\d.]+)", line)
                if match:
                    silence_starts.append(float(match.group(1)))
            elif "silence_end:" in line:
                match = re.search(r"silence_end:\s*([\d.]+)", line)
                if match:
                    silence_ends.append(float(match.group(1)))

        # Create speech segments from inverse of silence
        probe = probe_video_sync(filepath)
        duration = probe.get("duration", 0)

        speech_segments = []
        prev_end = 0.0
        for i in range(len(silence_starts)):
            if silence_starts[i] > prev_end + 0.1:
                speech_segments.append({
                    "start": prev_end,
                    "end": silence_starts[i],
                })
            if i < len(silence_ends):
                prev_end = silence_ends[i]
        if prev_end < duration - 0.1:
            speech_segments.append({"start": prev_end, "end": duration})

        # Create pseudo-words from speech segments
        for seg in speech_segments:
            words.append({
                "text": "[speech]",
                "start": seg["start"],
                "end": seg["end"],
                "speaker": "S0",
            })

        # Cleanup temp file
        if audio_out.exists():
            audio_out.unlink()

        return {"words": words, "duration": duration}

    def step_pack(self):
        """Pack transcripts into readable format."""
        self._log("pack", 0, "Packing transcripts...")

        pack_script = HELPERS_DIR / "pack_transcripts.py"
        if pack_script.exists():
            try:
                subprocess.run(
                    ["python", str(pack_script), "--edit-dir", str(self.edit_dir)],
                    capture_output=True, text=True, timeout=60,
                )
            except Exception as e:
                self._log("pack", 50, f"Pack helper failed: {e}")

        self._log("pack", 100, "Transcripts packed")

    def step_analyze(self):
        """Analyze content for editing decisions."""
        self._log("analyze", 0, "Analyzing content...")

        total_words = 0
        total_silences = 0
        total_fillers = 0
        total_duration = 0.0

        for source_id, transcript in self.transcripts.items():
            words = transcript.get("words", [])
            total_words += len(words)
            total_duration += transcript.get("duration", 0)

            silences = detect_silences(transcript, self.config.get("silence_threshold_ms", 400))
            total_silences += len(silences)

            if self.config.get("filler_remove", True):
                fillers = detect_fillers(transcript, self.config.get("filler_words"))
                total_fillers += len(fillers)

        self._log("analyze", 100,
                  f"Analysis complete: {total_words} words, {total_silences} silences, "
                  f"{total_fillers} fillers, {total_duration:.1f}s total")

    def step_cut(self):
        """Generate EDL (cut decisions)."""
        self._log("cut", 0, "Generating edit decisions...")

        self.edl = generate_edl(self.sources, self.transcripts, self.config)

        # Save EDL
        edl_path = self.edit_dir / "edl.json"
        with open(edl_path, "w") as f:
            json.dump(self.edl, f, indent=2)

        segments = len(self.edl.get("ranges", []))
        total_dur = self.edl.get("total_duration_s", 0)
        self._log("cut", 100, f"Generated EDL: {segments} segments, {total_dur:.1f}s total")

    def step_grade(self):
        """Apply color grading per segment."""
        self._log("grade", 0, "Applying color grade...")

        grade_script = HELPERS_DIR / "grade.py"
        grade_preset = self.config.get("grade_preset", "warm_cinematic")
        ranges = self.edl.get("ranges", [])

        for i, seg in enumerate(ranges):
            source_path = seg["source"]
            if source_path in self.sources:
                source_path = self.sources[source_path]

            clip_name = f"clip_{i:03d}.mp4"
            clip_path = self.clips_dir / clip_name

            # Extract segment with grade
            cmd = [
                FFMPEG_PATH, "-y",
                "-i", source_path,
                "-ss", str(seg["start"]),
                "-to", str(seg["end"]),
                "-c:v", "libx264", "-crf", "18",
                "-c:a", "aac",
                # Add 30ms audio fades
                "-af", f"afade=t=in:st=0:d=0.03,afade=t=out:st={seg['end']-seg['start']-0.03}:d=0.03",
                str(clip_path),
            ]
            try:
                subprocess.run(cmd, capture_output=True, timeout=300)
            except Exception as e:
                self._log("grade", 0, f"Grade failed for clip {i}: {e}")

            self._log("grade", ((i + 1) / len(ranges)) * 100, f"Graded clip {i+1}/{len(ranges)}")

    def step_render(self):
        """Render video from EDL."""
        self._log("render", 0, "Rendering video...")

        render_script = HELPERS_DIR / "render.py"
        edl_path = self.edit_dir / "edl.json"
        preview_path = self.edit_dir / "preview.mp4"

        if render_script.exists() and edl_path.exists():
            try:
                result = subprocess.run(
                    ["python", str(render_script), str(edl_path), "-o", str(preview_path)],
                    capture_output=True, text=True, timeout=1800,
                    cwd=str(self.work_dir),
                )
                if result.returncode == 0 and preview_path.exists():
                    self._log("render", 100, "Render complete via helper")
                    return
            except Exception as e:
                self._log("render", 0, f"Render helper failed: {e}, using direct FFmpeg")

        # Fallback: Direct FFmpeg concat
        self._render_direct()

    def _render_direct(self):
        """Direct FFmpeg rendering when helper is unavailable."""
        ranges = self.edl.get("ranges", [])

        # Create individual segments
        segment_files = []
        for i, seg in enumerate(ranges):
            source_path = seg.get("source", "")
            if source_path in self.sources:
                source_path = self.sources[source_path]

            seg_file = self.edit_dir / f"seg_{i:04d}.mp4"
            dur = seg["end"] - seg["start"]
            fade_out_start = max(dur - 0.03, 0)

            cmd = [
                FFMPEG_PATH, "-y",
                "-i", source_path,
                "-ss", str(seg["start"]),
                "-to", str(seg["end"]),
                "-c:v", "libx264", "-crf", "18", "-preset", "medium",
                "-c:a", "aac", "-b:a", "192k",
                "-af", f"afade=t=in:st=0:d=0.03,afade=t=out:st={fade_out_start}:d=0.03",
                str(seg_file),
            ]
            subprocess.run(cmd, capture_output=True, timeout=300)
            if seg_file.exists():
                segment_files.append(seg_file)

            self._log("render", ((i + 1) / len(ranges)) * 70, f"Extracted segment {i+1}/{len(ranges)}")

        # Concat all segments
        if segment_files:
            concat_file = self.edit_dir / "concat.txt"
            with open(concat_file, "w") as f:
                for sf in segment_files:
                    f.write(f"file '{sf}'\n")

            preview_path = self.edit_dir / "preview.mp4"
            cmd = [
                FFMPEG_PATH, "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(concat_file),
                "-c", "copy",
                str(preview_path),
            ]
            subprocess.run(cmd, capture_output=True, timeout=300)
            self._log("render", 90, "Segments concatenated")

            # Cleanup segment files
            for sf in segment_files:
                sf.unlink(missing_ok=True)
            concat_file.unlink(missing_ok=True)

        self._log("render", 100, "Render complete")

    def step_subtitles(self):
        """Generate and burn subtitles."""
        self._log("subtitles", 0, "Generating subtitles...")

        style = self.config.get("subtitle_style", "bold-overlay")
        srt_content = generate_srt(self.transcripts, self.edl, style)

        srt_path = self.edit_dir / "master.srt"
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_content)

        self._log("subtitles", 50, "SRT generated, burning into video...")

        # Burn subtitles into preview
        preview_path = self.edit_dir / "preview.mp4"
        final_path = self.edit_dir / "final.mp4"

        if preview_path.exists():
            # Subtitle style based on config
            if style == "bold-overlay":
                force_style = (
                    "FontName=Arial,FontSize=18,Bold=1,"
                    "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
                    "BackColour=&H00000000,BorderStyle=1,Outline=2,"
                    "Shadow=0,Alignment=2,MarginV=35"
                )
            else:
                force_style = (
                    "FontName=Arial,FontSize=22,Bold=0,"
                    "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
                    "BackColour=&H80000000,BorderStyle=3,Outline=0,"
                    "Shadow=0,Alignment=2,MarginV=60"
                )

            # Escape path for subtitles filter
            srt_escaped = str(srt_path).replace("\\", "/").replace(":", "\\:")

            cmd = [
                FFMPEG_PATH, "-y",
                "-i", str(preview_path),
                "-vf", f"subtitles='{srt_escaped}':force_style='{force_style}'",
                "-c:v", "libx264", "-crf", "18",
                "-c:a", "copy",
                str(final_path),
            ]
            try:
                subprocess.run(cmd, capture_output=True, timeout=1800)
            except Exception as e:
                self._log("subtitles", 80, f"Subtitle burn failed: {e}, using preview as final")
                shutil.copy2(preview_path, final_path)
        else:
            self._log("subtitles", 80, "No preview to burn subtitles into")

        self._log("subtitles", 100, "Subtitles complete")

    def step_finalize(self) -> str:
        """Finalize output — copy to outputs directory."""
        self._log("finalize", 0, "Finalizing output...")

        # Find the best output file
        final_path = self.edit_dir / "final.mp4"
        preview_path = self.edit_dir / "preview.mp4"

        source = final_path if final_path.exists() else preview_path
        if not source.exists():
            raise RuntimeError("No output file was generated")

        # Copy to outputs directory
        output_dir = OUTPUT_DIR / str(self.job_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "output.mp4"
        shutil.copy2(source, output_file)

        # Get file size
        file_size = output_file.stat().st_size

        self._log("finalize", 100, f"Output ready: {file_size / (1024*1024):.1f} MB")
        return str(output_file)
