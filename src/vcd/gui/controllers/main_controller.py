import os
import re
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse

from PySide6.QtCore import QObject, QProcess, QThread, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QVBoxLayout,
)

from vcd.gui.constants import (
    _MAX_RETRIES,
    _THUMB_DIR,
    GPU_KEYS,
    GPU_OPTIONS,
    GREEN,
    PRESETS,
    RED,
)
from vcd.gui.managers.settings_manager import SettingsManager
from vcd.gui.models.history_db import JobHistoryDB
from vcd.gui.models.queue_manager import QueueManager
from vcd.gui.utils.formatters import _disk_free, _fmt_dur, _fmt_size, _tobool
from vcd.gui.workers.async_worker import Worker

try:
    from vcd.core import media as core
except Exception:
    core = None


class MainController(QObject):
    def __init__(
        self,
        view,
        history_db: JobHistoryDB,
        queue_manager: QueueManager,
        settings_manager: SettingsManager,
        tray_manager=None,
    ):
        super().__init__()

        self._view = view
        self._left = view.left_panel
        self._log_tab = view.log_tab
        self._hist_tab = view.history_tab
        self._files_tab = view.files_tab
        self._history = history_db
        self._queue = queue_manager
        self._settings = settings_manager
        self._tray = tray_manager

        self._running = False
        self._last_output = ""
        self._last_params = None
        self._retry_count = 0
        self._stop_requested = False
        self._elapsed = 0
        self._bar_mode = ""
        self._log_filter = "ALL"
        self._log_search = ""

        self._thread = None
        self._worker = None
        self._thumb_process = None

        self._elapsed_timer = QTimer()
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self._elapsed_tick)

        self._connect_signals()
        self._load_settings()
        self._refresh_detected()
        self._system_check()
        self._detect_gpu_encoders()
        self._append_log("INFO", "Ready — paste a URL and hit Download.")

    def _connect_signals(self):
        left = self._left
        left.sig_url_changed.connect(self._refresh_detected)
        left.sig_url_changed.connect(self._update_disk_label)
        left.sig_url_return_pressed.connect(self._start)
        left.sig_dir_changed.connect(self._update_disk_label)
        left.sig_browse_clicked.connect(self._browse_dir)
        left.sig_cookie_profile_selected.connect(self._on_cookie_profile_selected)
        left.sig_save_cookie_profile.connect(self._save_cookie_profile_dialog)
        left.sig_preset_clicked.connect(self._on_preset_click)
        left.sig_adv_toggled.connect(self._toggle_adv)
        left.sig_adv_changed.connect(self._on_adv_changed)
        left.sig_crf_changed.connect(self._on_crf)
        left.sig_go_clicked.connect(self._start)
        left.sig_stop_clicked.connect(self._stop)
        left.sig_open_output_clicked.connect(self._open_output)
        left.sig_queue_add_clicked.connect(self._queue_add_current)
        left.sig_queue_run_clicked.connect(self._queue_run)
        left.sig_queue_remove_clicked.connect(self._queue_remove_selected)
        left.sig_queue_clear_clicked.connect(self._queue_clear)

        self._log_tab.sig_clear.connect(self._clear_log)
        self._log_tab.sig_save.connect(self._save_log)
        self._log_tab.sig_filter_changed.connect(self._set_log_filter)
        self._log_tab.sig_search_changed.connect(self._on_log_search)

        self._hist_tab.sig_refresh.connect(self._refresh_history)
        self._hist_tab.sig_clear_all.connect(self._clear_history)
        self._hist_tab.sig_row_context_menu.connect(self._hist_context_menu)
        self._hist_tab.sig_row_double_clicked.connect(self._hist_open_file)

        self._files_tab.sig_refresh.connect(self._refresh_files)
        self._files_tab.sig_play_file.connect(self._play_file)
        self._files_tab.sig_open_folder.connect(self._open_in_folder)
        self._files_tab.sig_delete_file.connect(self._delete_output_file)

        self._view.right_tabs.currentChanged.connect(self._on_tab_changed)
        self._view.about_btn.clicked.connect(self._about)
        self._view.sig_close.connect(self._on_close)

    def _toggle_adv(self, on):
        self._left.toggle_adv(on)

    def _on_preset_click(self, name):
        self._left.apply_preset(name)
        self._left.select_preset(name)
        if name == "Custom":
            self._left.adv_btn.setChecked(True)
            self._left.preset_note.setText(
                "Custom — adjust the Advanced settings below."
            )

    def _on_adv_changed(self, *_):
        if self._left._loading_preset:
            return
        self._left.select_preset("Custom")
        self._left.preset_btns["Custom"].setChecked(True)
        self._left.preset_note.setText("Custom settings.")

    def _on_crf(self, v):
        self._left.crf_val.setText(str(v))
        self._on_adv_changed()

    def _refresh_detected(self):
        url = self._left.read_url()
        rid = self._rid_of(url) if url else None
        tok = self._token_of(url) if url else None
        tok_txt = (
            f"session ✓  {tok[:8]}…"
            if tok
            else "no session token — paste cookie if needed"
        )
        self._left.set_detected_text(f"ID: {rid or '—'}   ·   {tok_txt}")
        if rid and not self._left._fname_touched:
            self._left.fname_edit.blockSignals(True)
            self._left.fname_edit.setText(f"Class-{rid}.mp4")
            self._left.fname_edit.blockSignals(False)

    def _update_disk_label(self):
        out_dir = self._left.read_dir() or os.getcwd()
        ok, label = _disk_free(out_dir)
        if label:
            prefix = "💾 " if ok else "⚠ Low disk: "
            self._left.set_disk_label(ok, prefix + label)

    def _system_check(self):
        if core is None:
            for w in (self._view.sc_ff, self._view.sc_fp):
                w.setText("core missing")
                w.setStyleSheet(f"color:{RED};")
            return
        ff = core.find_tool("ffmpeg")
        fp = core.find_tool("ffprobe")
        for w, ok, name, path in (
            (self._view.sc_ff, ff, "FFmpeg", ff),
            (self._view.sc_fp, fp, "FFprobe", fp),
        ):
            w.setText(f"{name} {'✓' if ok else '✗'}")
            w.setStyleSheet(f"color:{GREEN if ok else RED}; font-weight:700;")
            if path:
                w.setToolTip(str(path))
        if not (ff and fp):
            self._append_log(
                "WARN", "FFmpeg or FFprobe not found — rendering will fail."
            )

    def _detect_gpu_encoders(self):
        if core is None:
            return
        ff = core.find_tool("ffmpeg")
        if not ff:
            return
        try:
            r = subprocess.run(
                [ff, "-encoders"], capture_output=True, text=True, timeout=6
            )
            out = r.stdout + r.stderr
            encoder_check = {
                "nvidia": "h264_nvenc",
                "amd": "h264_amf",
                "intel": "h264_qsv",
            }
            for i, key in enumerate(GPU_KEYS):
                if key == "cpu":
                    continue
                enc = encoder_check.get(key, "")
                available = enc in out
                item = self._left.gpu_cb.model().item(i)
                if item:
                    item.setEnabled(available)
                    if not available:
                        item.setText(GPU_OPTIONS[i] + "  ✗ not in your FFmpeg")
                    if available:
                        item.setText(GPU_OPTIONS[i] + "  ✓")
        except Exception:
            pass

    def _on_cookie_profile_selected(self, name):
        profiles = self._settings.load_cookie_profiles()
        val = profiles.get(name, "")
        if val:
            self._left.cookie_edit.setText(val)
            self._append_log("INFO", f"Cookie profile '{name}' loaded.")

    def _save_cookie_profile_dialog(self):
        cookie_val = self._left.read_cookie()
        if not cookie_val:
            QMessageBox.warning(self._view, "No Cookie", "Paste a cookie value first.")
            return
        dialog = QDialog(self._view)
        dialog.setWindowTitle("Save Cookie Profile")
        dialog.setMinimumWidth(310)
        dl = QVBoxLayout(dialog)
        dl.addWidget(QLabel("Profile name:"))
        name_edit = QLineEdit()
        name_edit.setPlaceholderText("e.g. IAU Main Account")
        dl.addWidget(name_edit)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        dl.addWidget(btns)
        if dialog.exec() == QDialog.Accepted:
            name = name_edit.text().strip()
            if name:
                self._settings.save_cookie_profile(name, cookie_val)
                profiles = self._settings.load_cookie_profiles()
                self._left.refresh_cookie_profiles(profiles)
                self._append_log("INFO", f"Cookie profile '{name}' saved.")

    def _build_params_from_ui(self) -> Optional[dict]:
        url = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", self._left.read_url())
        if not url.startswith(("http://", "https://")):
            return None
        rid = self._rid_of(url)
        if not rid:
            return None
        out_dir = self._left.read_dir() or os.getcwd()
        fname = self._left.read_fname() or f"Class-{rid}.mp4"
        if not self._left.read_xml_only() and not fname.lower().endswith(".mp4"):
            fname += ".mp4"

        render_params = self._left.read_render_params()
        gpu_idx = render_params.pop("gpu_index", 0)
        gpu_key = GPU_KEYS[gpu_idx] if gpu_idx < len(GPU_KEYS) else "cpu"
        # Pop keys that are passed explicitly to avoid duplicate keyword arguments
        render_params.pop("xml_only", None)
        render_params.pop("verify_ssl", None)
        render_params.pop("reuse", None)
        return dict(
            url=url,
            rid=rid,
            output_dir=out_dir,
            output_name=fname,
            cookie=self._left.read_cookie(),
            xml_only=self._left.read_xml_only(),
            verify_ssl=self._left.read_ssl(),
            reuse=self._left.read_reuse(),
            preset=self._left.current_preset_name(),
            gpu=gpu_key,
            **render_params,
        )

    def _queue_add_current(self):
        params = self._build_params_from_ui()
        if params is None:
            QMessageBox.warning(self._view, "Bad URL", "Paste a valid class URL first.")
            return
        if not self._queue.add(params):
            self._append_log("WARN", f"Already in queue: {params['rid']}")
            return
        self._refresh_queue_ui()
        self._append_log(
            "INFO",
            f"Queued: {params['rid']}  ({self._queue.pending_count} total in queue)",
        )

    def _queue_run(self):
        if self._running:
            self._append_log(
                "WARN",
                "Job running — queue will continue automatically after it finishes.",
            )
            return
        if self._queue.pending_count == 0:
            self._append_log("WARN", "Queue is empty.")
            return
        self._queue_next()

    def _queue_next(self):
        item = self._queue.next()
        if item is None:
            self._append_log("SUCCESS", "Queue finished — all jobs done.")
            if self._tray:
                self._tray.notify("VCD — Queue Done", "All queued jobs completed.")
            return
        self._refresh_queue_ui()
        self._start_job(item)

    def _queue_complete_current(self, ok: bool):
        self._queue.complete_current(ok)
        self._refresh_queue_ui()
        if self._queue.pending_count > 0:
            QTimer.singleShot(1500, self._queue_next)

    def _queue_remove_selected(self):
        row = self._left.queue_list.currentRow()
        removed = self._queue.remove(row)
        if removed:
            self._append_log("INFO", f"Removed from queue: {removed.get('rid', '?')}")
            self._refresh_queue_ui()

    def _queue_clear(self):
        self._queue.clear()
        self._refresh_queue_ui()
        self._append_log("INFO", "Queue cleared.")

    def _refresh_queue_ui(self):
        self._left.refresh_queue_ui(self._queue.items)

    def _start(self):
        if self._running:
            return
        if core is None:
            QMessageBox.critical(
                self._view, "Missing vcd_core.py", "vcd_core module not found."
            )
            return
        params = self._build_params_from_ui()
        if params is None:
            url = self._left.read_url()
            msg = (
                "URL must start with http:// or https://"
                if not url.startswith(("http://", "https://"))
                else "No recording ID found in that URL."
            )
            self._append_log("ERROR", msg)
            QMessageBox.warning(self._view, "Bad URL", msg)
            return
        ok, label = _disk_free(params["output_dir"])
        if not ok:
            r = QMessageBox.warning(
                self._view,
                "Low Disk Space",
                f"Only {label} in the output folder.\nContinue anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if r != QMessageBox.Yes:
                return
        self._save_settings()
        self._settings.push_url_history(params["url"])
        self._retry_count = 0
        self._stop_requested = False
        self._last_params = params
        self._start_job(params)

    def _start_job(self, params: dict):
        self._stop_requested = False
        self._set_running(True)
        self._elapsed = 0
        self._left.stats.reset()
        self._left.set_stats_visible(True)
        self._elapsed_timer.start()
        if self._tray:
            self._tray.set_tip(f"VCD — Downloading {params.get('rid', '')}…")
        self._append_log("STEP", f"Starting: {params['rid']}")
        self._append_log(
            "INFO",
            f"Output → {os.path.join(params['output_dir'], params['output_name'])}",
        )
        self._thread = QThread(self)
        self._worker = Worker(params)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.sig_log.connect(self._append_log)
        self._worker.sig_progress.connect(self._on_progress)
        self._worker.sig_stage.connect(self._on_stage)
        self._worker.sig_speed.connect(self._on_speed)
        self._worker.sig_eta.connect(self._on_eta)
        self._worker.sig_bytes.connect(self._on_bytes)
        self._worker.sig_done.connect(self._on_done)
        self._worker.sig_done.connect(self._thread.quit)
        #        self._worker.sig_done.connect(self._worker.deleteLater)
        #        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _stop(self):
        if not self._running:
            return
        self._stop_requested = True
        if self._worker:
            self._worker.cancel()
        self._left.stop_btn.setEnabled(False)
        self._queue.clear()
        self._refresh_queue_ui()
        self._append_log("WARN", "Stopping...")

    def _set_running(self, running: bool):
        self._running = running
        self._left.set_running(running)

    def _elapsed_tick(self):
        self._elapsed += 1
        self._left.stats.set_elapsed(self._elapsed)

    def _on_stage(self, text: str):
        self._left.set_stage_text(text)
        if self._tray:
            self._tray.set_tip(f"VCD — {text}")

    def _on_progress(self, mode: str, pct: int):
        self._left.set_progress(mode, pct)
        verb = "Downloading" if mode == "download" else "Rendering"
        self._left.set_stage_text(f"{verb}... {pct}%")
        if self._tray:
            self._tray.set_tip(f"VCD — {verb} {pct}%")

    def _on_speed(self, spd: str):
        self._left.set_speed_text(spd, True)
        self._left.stats.push_speed(spd)

    def _on_eta(self, eta: str):
        self._left.stats.set_eta(eta)

    def _on_bytes(self, dl: str, total: str):
        self._left.stats.set_bytes(dl, total)

    def _on_done(self, ok: bool, message: str, out_path: str):
        self._elapsed_timer.stop()
        self._set_running(False)
        self._left.set_stats_visible(False)
        self._left.set_retry_text("", False)
        self._left.bar.setRange(0, 100)
        self._left.bar.setValue(100 if ok else 0)

        size_str, dur_str = "", ""
        if ok and out_path and os.path.isfile(out_path):
            size_str = _fmt_size(out_path)
            dur_sec = self._probe_duration(out_path)
            dur_str = _fmt_dur(dur_sec) if dur_sec > 0 else ""

        entry = {
            "id": str(uuid.uuid4())[:8],
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "rid": self._last_params.get("rid", "?") if self._last_params else "?",
            "status": "done" if ok else "failed",
            "output_path": out_path,
            "size": size_str,
            "duration": dur_str,
            "preset": self._last_params.get("preset", "?")
            if self._last_params
            else "?",
            "elapsed_sec": self._elapsed,
        }
        self._history.add(entry)
        self._refresh_history()

        if ok:
            self._append_log("SUCCESS", message)
            detail = "  ·  ".join(p for p in [size_str, dur_str] if p)
            if detail:
                self._append_log("INFO", f"{os.path.basename(out_path)}  ({detail})")
            self._left.set_stage_text("Done ✓")
            self._last_output = out_path
            if self._tray:
                self._tray.notify(
                    "VCD — Done!",
                    f"{os.path.basename(out_path)} — {detail or 'finished'}",
                )
            QTimer.singleShot(600, lambda: self._maybe_extract_thumb(out_path))
            QTimer.singleShot(1000, lambda: self._view.right_tabs.setCurrentIndex(2))
        else:
            self._append_log("ERROR", message)
            self._left.set_stage_text("Failed — check the log")
            if self._tray:
                self._tray.notify("VCD — Failed", message, error=True)
            self._auto_retry()

        self._queue_complete_current(ok)

    def _auto_retry(self) -> bool:
        if not self._left.read_auto_retry():
            return False
        if self._retry_count >= _MAX_RETRIES:
            self._append_log(
                "WARN", f"Max retries ({_MAX_RETRIES}) reached. Giving up."
            )
            return False
        if self._last_params is None:
            return False
        self._retry_count += 1
        secs = 5 * self._retry_count
        self._append_log(
            "WARN",
            f"Auto-retrying in {secs}s…  (attempt {self._retry_count}/{_MAX_RETRIES})",
        )
        self._left.set_retry_text(
            f"⟳  Retrying in {secs}s   (attempt {self._retry_count}/{_MAX_RETRIES})",
            True,
        )
        QTimer.singleShot(
            secs * 1000,
            lambda: (
                self._left.set_retry_text("", False),
                self._start_job(self._last_params),
            ),
        )
        return True

    def _probe_duration(self, path: str) -> float:
        if core is None:
            return 0.0
        try:
            fp = core.find_tool("ffprobe")
            if fp:
                return core.probe_duration(fp, Path(path))
        except Exception:
            pass
        return 0.0

    def _maybe_extract_thumb(self, video_path: str):
        if not video_path or not os.path.isfile(video_path) or core is None:
            return
        ff = core.find_tool("ffmpeg")
        if not ff:
            return
        dur = self._probe_duration(video_path)
        t = max(2.0, dur * 0.35) if dur > 0 else 30.0
        _THUMB_DIR.mkdir(parents=True, exist_ok=True)
        out = str(_THUMB_DIR / (Path(video_path).stem + ".jpg"))

        self._thumb_process = QProcess()
        self._thumb_process.finished.connect(
            lambda exit_code, exit_status: self._on_thumb_finished(exit_code, out)
        )
        self._thumb_process.start(
            ff,
            [
                "-y",
                "-ss",
                f"{t:.1f}",
                "-i",
                video_path,
                "-frames:v",
                "1",
                "-vf",
                "scale=260:-1",
                "-q:v",
                "4",
                out,
            ],
        )

    def _on_thumb_finished(self, exit_code, out_path):
        if exit_code == 0 and Path(out_path).exists():
            self._history.update_last(thumb=out_path)
            self._refresh_files()
        self._thumb_process = None

    def _refresh_history(self):
        entries = self._history.entries
        self._hist_tab.refresh_table(entries)

    def _hist_context_menu(self, row, pos):
        entries = self._history.entries
        if row < 0 or row >= len(entries):
            return
        e = entries[row]
        path = e.get("output_path", "")
        menu = QMenu(self._view)
        if path and os.path.isfile(path):
            menu.addAction("▶  Play file", lambda: self._play_file(path))
            menu.addAction("📂  Open folder", lambda: self._open_in_folder(path))
            menu.addSeparator()
            menu.addAction("🗑  Delete file", lambda: self._delete_output_file(path))
        menu.addAction(
            "✕  Remove from history",
            lambda: (self._history.remove(row), self._refresh_history()),
        )
        menu.exec(self._hist_tab.hist_table.viewport().mapToGlobal(pos))

    def _hist_open_file(self, row):
        entries = self._history.entries
        if row < len(entries):
            path = entries[row].get("output_path", "")
            if path and os.path.isfile(path):
                self._play_file(path)

    def _clear_history(self):
        r = QMessageBox.question(
            self._view,
            "Clear History?",
            "Delete all job history records?\n(Output files are not deleted.)",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if r == QMessageBox.Yes:
            self._history.clear()
            self._refresh_history()
            self._append_log("INFO", "History cleared.")

    def _refresh_files(self):
        entries = [
            e
            for e in self._history.entries
            if e.get("output_path") and os.path.isfile(e["output_path"])
        ]
        self._files_tab.refresh_files(entries)

    def _play_file(self, path: str):
        if os.path.isfile(path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(path)))
        else:
            self._append_log("WARN", f"File not found: {path}")

    def _open_in_folder(self, path: str):
        folder = os.path.dirname(path) if os.path.isfile(path) else path
        if not os.path.isdir(folder):
            folder = os.path.dirname(folder) or "."
        QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(folder)))

    def _delete_output_file(self, path: str):
        r = QMessageBox.question(
            self._view,
            "Delete File?",
            f"Permanently delete:\n{path}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if r == QMessageBox.Yes:
            try:
                os.remove(path)
                self._append_log("INFO", f"Deleted: {os.path.basename(path)}")
                self._refresh_history()
                self._refresh_files()
            except Exception as exc:
                self._append_log("ERROR", f"Couldn't delete: {exc}")

    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(
            self._view, "Choose output folder", self._left.read_dir() or os.getcwd()
        )
        if d:
            self._left.dir_edit.setText(d)
            self._update_disk_label()

    def _open_output(self):
        self._open_in_folder(self._last_output)

    def _append_log(self, level: str, msg: str):
        self._log_tab.append_log(level, msg, self._log_filter, self._log_search)

    def _clear_log(self):
        self._log_tab.clear_log()

    def _set_log_filter(self, level: str):
        self._log_filter = level
        self._log_tab.set_filter_active(level)
        self._rebuild_log()

    def _on_log_search(self, text: str):
        self._log_search = text.strip().lower()
        self._rebuild_log()

    def _rebuild_log(self):
        self._log_tab.rebuild_log(self._log_filter, self._log_search)

    def _save_log(self):
        fn, _ = QFileDialog.getSaveFileName(
            self._view, "Save log", "vcd_log.txt", "Text (*.txt)"
        )
        if fn:
            try:
                lines = [
                    f"[{ts}] {lv}  {msg}"
                    for (lv, msg, color, icon, ts) in self._log_tab._log_all
                ]
                Path(fn).write_text("\n".join(lines), encoding="utf-8")
                self._append_log("INFO", f"Log saved → {fn}")
            except Exception as exc:
                self._append_log("ERROR", f"Couldn't save log: {exc}")

    def _on_tab_changed(self, idx: int):
        if idx == 1:
            self._refresh_history()
        elif idx == 2:
            self._refresh_files()

    def _about(self):
        self._view._about()

    def _save_settings(self):
        ui_state = {
            "url": self._left.read_url(),
            "dir": self._left.read_dir(),
            "preset": self._left.current_preset_name(),
            "res": self._left.res_cb.currentText(),
            "fps": self._left.fps_sb.value(),
            "crf": self._left.crf_sl.value(),
            "ab": self._left.ab_cb.currentText(),
            "vp": self._left.vp_cb.currentText(),
            "gpu": GPU_KEYS[self._left.get_gpu_index()],
            "pad": self._left.pad_sb.value(),
            "xml": self._left.read_xml_only(),
            "ssl": self._left.read_ssl(),
            "reuse": self._left.read_reuse(),
            "auto_retry": self._left.read_auto_retry(),
            "adv_open": self._left.adv_btn.isChecked(),
            "splitter": self._view._splitter.sizes(),
        }
        self._settings.save(ui_state)

    def _load_settings(self):
        s = self._settings.load()
        if s["url"]:
            self._left.url_edit.setText(s["url"])
        self._left.dir_edit.setText(s["dir"] or os.getcwd())
        preset = s["preset"]
        if preset not in PRESETS:
            preset = "Balanced (720p)"
        self._left.apply_preset(preset)
        self._left.select_preset(preset)
        if preset == "Custom":
            self._left._loading_preset = True
            try:
                self._left.res_cb.setCurrentText(s["res"])
                self._left.fps_sb.setValue(int(s["fps"]))
                self._left.crf_sl.setValue(int(s["crf"]))
                self._left.ab_cb.setCurrentText(s["ab"])
                self._left.vp_cb.setCurrentText(s["vp"])
                self._left.pad_sb.setValue(int(s["pad"]))
            except Exception:
                pass
            finally:
                self._left._loading_preset = False
        self._left.xml_chk.setChecked(_tobool(s["xml"]))
        self._left.ssl_chk.setChecked(_tobool(s["ssl"]))
        self._left.reuse_chk.setChecked(_tobool(s["reuse"]))
        self._left.auto_retry_chk.setChecked(_tobool(s["auto_retry"]))
        if s["gpu"] in GPU_KEYS:
            self._left.set_gpu_index(GPU_KEYS.index(s["gpu"]))
        self._left.adv_btn.setChecked(_tobool(s["adv_open"]))
        sizes = s["splitter"]
        if sizes:
            try:
                self._view._splitter.setSizes([int(x) for x in sizes])
            except Exception:
                pass
        profiles = self._settings.load_cookie_profiles()
        self._left.refresh_cookie_profiles(profiles)

    @staticmethod
    def _rid_of(url: str):
        try:
            return urlparse(url).path.rstrip("/").split("/")[-1] or None
        except Exception:
            return None

    @staticmethod
    def _token_of(url: str):
        try:
            return parse_qs(urlparse(url).query).get("session", [None])[0]
        except Exception:
            return None

    def _on_close(self, e):
        if self._running and self._thread:
            r = QMessageBox.question(
                self._view,
                "Quit?",
                "A download is still running. Quit anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if r != QMessageBox.Yes:
                e.ignore()
                return
            if self._worker:
                self._worker.cancel()
            self._thread.quit()
            self._thread.wait(1500)
        self._save_settings()
        e.accept()
