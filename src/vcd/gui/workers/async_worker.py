import os
import re
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from vcd.core.auth import acquire_authenticated_session
from vcd.core.config import DownloadConfig, RenderConfig
from vcd.core.exceptions import VCDError
from vcd.core.media import Renderer, init_tools, render_video_from_timeline
from vcd.core.network import Downloader
from vcd.core.timeline import collect_media_intervals, write_timeline_xml


class _StreamRouter:
    _ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
    _LOG = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\]\s+([A-Z]+)\s+(.*)$")
    _PCT = re.compile(r"(\d{1,3})\s*%")
    _SPD = re.compile(r"([\d.]+)\s*([kKmMgG]?[Bb])(?:yte)?s?/s")
    _ETA = re.compile(r"<(\d{1,2}:\d{2}(?::\d{2})?)")
    _BYTES = re.compile(r"([\d.]+\s*[kKmMgG]?B)\s*/\s*([\d.]+\s*[kKmMgG]?B)")

    def __init__(self, on_log, on_progress, on_speed=None, on_eta=None, on_bytes=None):
        self.on_log = on_log
        self.on_progress = on_progress
        self.on_speed = on_speed
        self.on_eta = on_eta
        self.on_bytes = on_bytes
        self._buf = ""
        self._last = {}

    def write(self, s):
        if not s:
            return
        if not isinstance(s, str):
            try:
                s = s.decode("utf-8", "replace")
            except Exception:
                s = str(s)
        self._buf += s
        while True:
            m = re.search(r"[\r\n]", self._buf)
            if not m:
                break
            seg = self._buf[: m.start()]
            self._buf = self._buf[m.start() + 1 :]
            self._emit(seg)

    def flush(self):
        if self._buf.strip():
            self._emit(self._buf)
            self._buf = ""

    def isatty(self):
        return False

    def _emit(self, seg):
        seg = self._ANSI.sub("", seg).rstrip()
        if not seg:
            return
        lm = self._LOG.match(seg)
        if lm:
            self.on_log(lm.group(2), lm.group(3))
            return
        if "%" in seg:
            pm = self._PCT.search(seg)
            if pm:
                pct = max(0, min(100, int(pm.group(1))))
                if "Merg" in seg or "FFmpeg" in seg or "µs" in seg:
                    mode = "render"
                elif "\u2193" in seg or "B/s" in seg or "B [" in seg:
                    mode = "download"
                    if self.on_speed:
                        sm = self._SPD.search(seg)
                        if sm:
                            self.on_speed(f"{sm.group(1)} {sm.group(2).upper()}/s")
                    if self.on_eta:
                        em = self._ETA.search(seg)
                        if em:
                            self.on_eta(em.group(1))
                    if self.on_bytes:
                        bm = self._BYTES.search(seg)
                        if bm:
                            self.on_bytes(bm.group(1).strip(), bm.group(2).strip())
                else:
                    mode = "busy"
                if self._last.get(mode) != pct:
                    self._last[mode] = pct
                    self.on_progress(mode, pct)
                return
        self.on_log("LOG", seg)


class _Cancelled(Exception):
    """Internal exception to cleanly break the pipeline on user cancellation."""

    pass


class Worker(QObject):
    sig_log = Signal(str, str)
    sig_progress = Signal(str, int)
    sig_stage = Signal(str)
    sig_speed = Signal(str)
    sig_eta = Signal(str)
    sig_bytes = Signal(str, str)
    sig_done = Signal(bool, str, str)

    def __init__(self, params: dict):
        super().__init__()
        self.p = params
        self._cancel = False
        self.downloader = Downloader()
        self.renderer: Renderer | None = None

    def cancel(self):
        self._cancel = True
        self.downloader.cancel()
        if self.renderer:
            self.renderer.cancel()

    def _ck(self):
        if self._cancel:
            raise _Cancelled()

    @Slot()
    def run(self):
        p = self.p
        try:
            out_dir = Path(p["output_dir"]).expanduser()
            out_dir.mkdir(parents=True, exist_ok=True)

            self.sig_stage.emit("Checking FFmpeg...")
            tools = init_tools()
            self.renderer = Renderer(tools.ffmpeg)
            self._ck()

            rid = p["rid"]
            result_dir = out_dir / rid

            if p["reuse"] and result_dir.is_dir():
                self.sig_log.emit(
                    "INFO", f"Found existing folder '{rid}' — skipping download."
                )
            else:
                self.sig_stage.emit("Downloading class files...")
                dl_cfg = DownloadConfig(verify_ssl=p["verify_ssl"])

                session = acquire_authenticated_session(
                    p["url"], dl_cfg, p.get("cookie")
                )
                self._ck()

                self.downloader.download_and_extract(
                    url=p["url"],
                    target_dir=result_dir,
                    session=session,
                    cfg=dl_cfg,
                    progress_cb=lambda pct: self.sig_progress.emit("download", pct),
                )
            self._ck()

            rcfg = RenderConfig(
                canvas_w=p["w"],
                canvas_h=p["h"],
                fps=p["fps"],
                crf=p["crf"],
                video_preset=p["vp"],
                audio_bitrate=p["ab"],
                padding_ms=p["pad"],
                gpu=p.get("gpu", "cpu"),
            )

            self.sig_stage.emit("Building timeline...")
            sc, ac, _ = collect_media_intervals(result_dir, tools.ffprobe)

            if not sc and not ac:
                raise VCDError("No valid media files with pacingTick were found.")

            total_ms = (
                max((c["end_ms"] for c in sc + ac), default=0.0) + rcfg.padding_ms
            )
            xml_path = result_dir / "timeline.xml"

            write_timeline_xml(sc, ac, total_ms, xml_path)
            self._ck()

            out_path = xml_path.resolve()

            if not p["xml_only"]:
                self.sig_stage.emit("Rendering video...")
                output_video = out_dir / p["output_name"]

                render_video_from_timeline(
                    renderer=self.renderer,
                    media_folder=result_dir,
                    timeline_path=xml_path,
                    output_video=output_video,
                    cfg=rcfg,
                    progress_cb=lambda pct: self.sig_progress.emit("render", pct),
                )
                out_path = output_video
            self._ck()

            self.sig_done.emit(True, "Done! 🎓", str(out_path))

        except _Cancelled:
            self.sig_done.emit(False, "Stopped.", "")

        except Exception as exc:
            if self._cancel:
                self.sig_done.emit(False, "Stopped.", "")
            else:
                self.sig_done.emit(False, str(exc), "")
