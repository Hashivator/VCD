import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from typing import Optional, Callable

from tqdm import tqdm

from vcd.core.config import RenderConfig
from vcd.core.exceptions import MediaProcessingError, ToolNotFoundError
from vcd.core.timeline import (
    _read_timeline_xml,
    collect_media_intervals,
    write_timeline_xml,
)
from vcd.logger import log


# holds the currently-running ffmpeg subprocess so GUI can kill it on stop
_current_proc: "Optional[subprocess.Popen]" = None

IS_WINDOWS = platform.system() == "Windows"


class Renderer:
    def __init__(self, ffmpeg_path: str):
        self.ffmpeg_path = ffmpeg_path
        self._process: Optional[subprocess.Popen] = None

    def cancel(self):
        """Immediately terminate the FFmpeg process if running."""
        if self._process and self._process.poll() is None:
            self._process.terminate()

    def execute(
        self,
        cmd_parts: list[str],
        description: str = "FFmpeg",
        duration_sec: Optional[float] = None,
        progress_cb: Optional[Callable[[int], None]] = None,
    ) -> None:
        """Executes FFmpeg, captures its progress natively, and fires callbacks."""
        log(f"Launching: {description}")

        # Ensure the command requests machine-readable progress output
        full_cmd = (
            [self.ffmpeg_path]
            + ["-progress", "pipe:1", "-nostats", "-loglevel", "quiet"]
            + (cmd_parts[1:] if cmd_parts[0] == self.ffmpeg_path else cmd_parts)
        )

        self._process = subprocess.Popen(
            full_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )

        try:
            for line in self._process.stdout:
                # Natively parse FFmpeg's machine-readable time output
                if "out_time_ms=" in line:
                    try:
                        current_us = int(line.strip().split("=")[1])
                        if progress_cb and duration_sec and duration_sec > 0:
                            # Calculate percentage and emit to GUI
                            pct = int((current_us / (duration_sec * 1_000_000)) * 100)
                            progress_cb(max(0, min(100, pct)))
                    except (ValueError, IndexError):
                        continue
                elif "progress=end" in line:
                    break

            self._process.wait()

        finally:
            # Capture return code before nulling the process pointer
            ret_code = self._process.returncode if self._process else -1
            self._process = None

        # Check for errors, ignoring SIGTERM (-15 on Unix, 1 on Windows)
        # which happens naturally when we call self.cancel()
        if ret_code not in (0, -15, 1, 255):
            raise MediaProcessingError(f"FFmpeg failed and exited with code {ret_code}")

        log(f"{description} finished successfully.")


class ToolManager:
    """Holds validated paths to ffmpeg and ffprobe."""

    def __init__(self, ffmpeg_path: str, ffprobe_path: str):
        self.ffmpeg = ffmpeg_path
        self.ffprobe = ffprobe_path


def find_tool(base_name: str) -> Optional[str]:
    """Search for a binary; first in the bundled dir, then PATH."""
    candidates = [base_name]
    if IS_WINDOWS and not base_name.endswith(".exe"):
        candidates.append(base_name + ".exe")

    try:
        bundle_dir = sys._MEIPASS  # type: ignore[attr-defined]
    except AttributeError:
        bundle_dir = os.path.abspath(".")

    for name in candidates:
        p = os.path.join(bundle_dir, name)
        if os.path.isfile(p):
            return p

    for name in candidates:
        found = shutil.which(name)
        if found:
            return found

    return None


def init_tools() -> ToolManager:
    """Locate ffmpeg and ffprobe, exit if not found."""
    ffmpeg = find_tool("ffmpeg")
    ffprobe = find_tool("ffprobe")
    missing = []
    if not ffmpeg:
        missing.append("ffmpeg")
    if not ffprobe:
        missing.append("ffprobe")
    if missing:
        raise ToolNotFoundError(
            f"{', '.join(missing)} not found. Install FFmpeg and add it to PATH."
        )
    log(f"ffmpeg  → {ffmpeg}")
    log(f"ffprobe → {ffprobe}")
    return ToolManager(ffmpeg, ffprobe)


# FFprobe helpers
def _run_ffprobe(
    ffprobe_path: str, extra_args: list[str], file_path: Path
) -> Optional[dict]:
    cmd = [
        ffprobe_path,
        "-v",
        "quiet",
        "-print_format",
        "json",
        *extra_args,
        str(file_path),
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            return None
        return json.loads(res.stdout)
    except (json.JSONDecodeError, OSError) as exc:
        log(f"ffprobe failed for {file_path.name}: {exc}", "WARN")
        return None


def contains_stream(ffprobe_path: str, file_path: Path, stream_kind: str) -> bool:
    info = _run_ffprobe(ffprobe_path, ["-show_streams"], file_path)
    if not info:
        return False
    return any(s.get("codec_type") == stream_kind for s in info.get("streams", []))


def probe_duration(ffprobe_path: str, file_path: Path) -> float:
    """Return duration in seconds; 0.0 on any error."""
    info = _run_ffprobe(ffprobe_path, ["-show_format"], file_path)
    if not info:
        return 0.0
    try:
        return float(info["format"]["duration"])
    except (KeyError, ValueError, TypeError):
        return 0.0


# FFmpeg runner
def execute_ffmpeg(
    ffmpeg_path: str,
    cmd_parts: list[str],
    description: str = "FFmpeg",
    duration_sec: Optional[float] = None,
) -> None:
    log(f"Launching: {description}")
    full_cmd = (
        [ffmpeg_path]
        + ["-progress", "pipe:1", "-nostats", "-loglevel", "quiet"]
        + cmd_parts[1:]
        if cmd_parts[0] == ffmpeg_path
        else cmd_parts
    )
    global _current_proc
    proc = subprocess.Popen(
        full_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    _current_proc = proc

    pbar = None
    if duration_sec and duration_sec > 0:
        pbar = tqdm(
            total=int(duration_sec * 1_000_000),
            unit="µs",
            desc=description,
            colour="cyan",
            smoothing=0.02,
        )

    last_us = 0
    try:
        for line in proc.stdout:
            if "out_time_ms=" in line:
                try:
                    cur = int(line.strip().split("=")[1])
                    if pbar:
                        pbar.update(max(0, cur - last_us))
                        last_us = cur
                except (ValueError, IndexError):
                    pass
            elif "progress=end" in line:
                break
        proc.wait()

    finally:
        _current_proc = None

    if pbar:
        pbar.close()

    if proc.returncode != 0:
        raise MediaProcessingError(f"ffmpeg exited with code {proc.returncode}")
    log("FFmpeg finished successfully.", "SUCCESS")


# FilterGraphBuilder – helper for ffmpeg filter chains
class FilterGraphBuilder:
    def __init__(self):
        self._p: list[str] = []

    def add(self, s: str) -> "FilterGraphBuilder":
        self._p.append(s.rstrip(";"))
        return self

    def build(self) -> str:
        return ";".join(self._p)


# Timeline reader & renderer
def _video_encoder_args(cfg: "RenderConfig") -> list:
    """Return the FFmpeg video encoder CLI args based on cfg.gpu.

    CPU uses libx264 + CRF (same as before).
    GPU encoders use hardware-specific quality params roughly equivalent to CRF.
    """
    _nvenc_preset = {
        "ultrafast": "p1",
        "superfast": "p2",
        "veryfast": "p3",
        "faster": "p3",
        "fast": "p4",
        "medium": "p4",
        "slow": "p5",
        "slower": "p6",
    }
    if cfg.gpu == "nvidia":
        return [
            "-c:v",
            "h264_nvenc",
            "-preset",
            _nvenc_preset.get(cfg.video_preset, "p4"),
            "-rc",
            "vbr",
            "-cq",
            str(cfg.crf),
            "-b:v",
            "0",
        ]
    if cfg.gpu == "amd":
        return [
            "-c:v",
            "h264_amf",
            "-quality",
            "balanced",
            "-rc",
            "cqp",
            "-qp_i",
            str(cfg.crf),
            "-qp_p",
            str(cfg.crf),
            "-qp_b",
            str(cfg.crf),
        ]
    if cfg.gpu == "intel":
        return [
            "-c:v",
            "h264_qsv",
            "-preset",
            cfg.video_preset,
            "-global_quality",
            str(cfg.crf),
        ]
    # default: CPU libx264
    return [
        "-c:v",
        "libx264",
        "-preset",
        cfg.video_preset,
        "-crf",
        str(cfg.crf),
    ]


def render_video_from_timeline(
    tools: ToolManager,
    media_folder: Path,
    timeline_path: Path,
    output_video: Path,
    cfg: RenderConfig = RenderConfig(),
) -> None:
    video_plan, audio_meta, total_ms = _read_timeline_xml(timeline_path)
    total_sec = total_ms / 1000.0

    done: set[str] = set()
    video_srcs: list[dict] = []
    for seg in video_plan:
        fn = seg["file"]
        if fn == "black" or fn in done:
            continue
        rows = [s for s in video_plan if s["file"] == fn]
        video_srcs.append(
            {
                "file": media_folder / fn,
                "start_ms": min(r["start_ms"] for r in rows),
                "end_ms": max(r["end_ms"] for r in rows),
            }
        )
        done.add(fn)

    audio_srcs = [
        {
            "file": media_folder / fn,
            "start_ms": i["first_start_ms"],
            "end_ms": i["latest_end_ms"],
        }
        for fn, i in audio_meta.items()
    ]

    video_srcs.sort(key=lambda x: x["start_ms"])
    audio_srcs.sort(key=lambda x: x["start_ms"])
    nv, na = len(video_srcs), len(audio_srcs)

    cmd = [tools.ffmpeg, "-y"]
    cmd += [
        "-f",
        "lavfi",
        "-i",
        f"color=c=black:s={cfg.canvas_w}x{cfg.canvas_h}:r={cfg.fps}:d={total_sec},format=yuv420p",
    ]
    for vs in video_srcs:
        cmd += ["-i", str(vs["file"])]
    for as_ in audio_srcs:
        cmd += ["-i", str(as_["file"])]
    silence_idx = 1 + nv + na
    cmd += [
        "-f",
        "lavfi",
        "-i",
        f"anullsrc=channel_layout=stereo:sample_rate=44100:duration={total_sec}",
    ]

    fb = FilterGraphBuilder()

    if nv > 0:
        for idx, vs in enumerate(video_srcs):
            fb.add(
                f"[{1 + idx}:v]"
                f"scale={cfg.canvas_w}:{cfg.canvas_h}:force_original_aspect_ratio=decrease,"
                f"pad={cfg.canvas_w}:{cfg.canvas_h}:(ow-iw)/2:(oh-ih)/2,"
                f"setsar=1,format=rgba,"
                f"setpts=PTS-STARTPTS+{vs['start_ms'] / 1000}/TB[v{idx}]"
            )
        prev = "[0:v]"
        for idx in range(nv):
            lbl = f"vo{idx}" if idx < nv - 1 else "vout"
            fb.add(f"{prev}[v{idx}]overlay=0:0[{lbl}]")
            prev = f"[{lbl}]"
    else:
        fb.add("[0:v]null[vout]")

    alabs: list[str] = []
    for idx, as_ in enumerate(audio_srcs):
        lbl = f"a{idx}"
        fb.add(
            f"[{1 + nv + idx}:a]"
            f"asetpts=PTS-STARTPTS,"
            f"aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo,"
            f"adelay={int(as_['start_ms'])}|{int(as_['start_ms'])}:all=1[{lbl}]"
        )
        alabs.append(f"[{lbl}]")

    fb.add(
        f"[{silence_idx}:a]"
        f"aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[silence]"
    )
    alabs.append("[silence]")
    fb.add(
        f"{''.join(alabs)}amix=inputs={len(alabs)}:duration=longest:dropout_transition=0[outa]"
    )

    cmd += [
        "-filter_complex",
        fb.build(),
        "-map",
        "[vout]",
        "-map",
        "[outa]",
        # "-c:v", "libx264", "-preset", cfg.video_preset, "-crf", str(cfg.crf),
        *_video_encoder_args(cfg),
        "-c:a",
        "aac",
        "-b:a",
        cfg.audio_bitrate,
        "-movflags",
        "+faststart",
        "-avoid_negative_ts",
        "make_zero",
        str(output_video),
    ]

    execute_ffmpeg(tools.ffmpeg, cmd, "Merging final video", duration_sec=total_sec)
    log(f"🎉 Final video: {output_video}", "SUCCESS")


# Main processing pipeline
def process_recording(
    tools: ToolManager,
    folder_path: str,
    output_video: str = "synced_class.mp4",
    xml_only: bool = False,
    cfg: RenderConfig = RenderConfig(),
) -> None:
    folder = Path(folder_path)
    if not folder.is_dir():
        raise FileNotFoundError(f"Folder not found: {folder_path}")

    sc, ac, _ = collect_media_intervals(folder, tools.ffprobe)
    if not sc and not ac:
        raise MediaProcessingError("No media files with a valid pacingTick were found.")

    total_ms = max((c["end_ms"] for c in sc + ac), default=0.0) + cfg.padding_ms
    xml_path = folder / "timeline.xml"

    log("Generating timeline.xml …", "STEP")
    write_timeline_xml(sc, ac, total_ms, xml_path)
    if xml_only:
        return

    log("Assembling video …", "STEP")
    render_video_from_timeline(tools, folder, xml_path, Path(output_video), cfg)
