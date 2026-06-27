from PySide6.QtCore import QSettings

from vcd.gui.constants import _MAX_URL_HIST


class SettingsManager:
    def __init__(self):
        self._settings = QSettings("VCD", "VCD-GUI-v04")
        self._url_history: list = []
        self._cookie_profiles: dict = {}

    def save(self, ui_state: dict):
        s = self._settings
        for key, value in ui_state.items():
            s.setValue(key, value)

    def load(self) -> dict:
        s = self._settings
        return {
            "url": s.value("url", ""),
            "dir": s.value("dir", ""),
            "preset": s.value("preset", "Balanced (720p)"),
            "res": s.value("res", "1280x720"),
            "fps": s.value("fps", 30),
            "crf": s.value("crf", 28),
            "ab": s.value("ab", "96k"),
            "vp": s.value("vp", "veryfast"),
            "gpu": s.value("gpu", "cpu"),
            "pad": s.value("pad", 2000),
            "xml": s.value("xml", False),
            "ssl": s.value("ssl", False),
            "reuse": s.value("reuse", True),
            "auto_retry": s.value("auto_retry", True),
            "adv_open": s.value("adv_open", False),
            "splitter": s.value("splitter", None),
            "url_history": s.value("url_history", []),
        }

    def load_cookie_profiles(self) -> dict:
        raw = self._settings.value("cookie_profiles", {}) or {}
        self._cookie_profiles = raw if isinstance(raw, dict) else {}
        return self._cookie_profiles

    def save_cookie_profile(self, name: str, value: str):
        self._cookie_profiles[name] = value
        self._settings.setValue("cookie_profiles", self._cookie_profiles)

    def load_url_history(self) -> list:
        hist = self._settings.value("url_history", []) or []
        self._url_history = list(hist)[:_MAX_URL_HIST]
        return self._url_history

    def push_url_history(self, url: str):
        if url in self._url_history:
            self._url_history.remove(url)
        self._url_history.insert(0, url)
        self._url_history = self._url_history[:_MAX_URL_HIST]
        self._settings.setValue("url_history", self._url_history)
