import json

from vcd.gui.constants import _HISTORY_FILE, _MAX_HISTORY


class JobHistoryDB:
    def __init__(self):
        self._entries: list = []
        self._load()

    def add(self, entry: dict):
        self._entries.insert(0, entry)
        self._entries = self._entries[:_MAX_HISTORY]
        self._save()

    def update_last(self, **kw):
        if self._entries:
            self._entries[0].update(kw)
            self._save()

    def remove(self, idx: int):
        if 0 <= idx < len(self._entries):
            self._entries.pop(idx)
            self._save()

    def clear(self):
        self._entries.clear()
        self._save()

    @property
    def entries(self) -> list:
        return list(self._entries)

    def _load(self):
        try:
            self._entries = json.loads(_HISTORY_FILE.read_text(encoding="utf-8"))
            if not isinstance(self._entries, list):
                self._entries = []
        except Exception:
            self._entries = []

    def _save(self):
        try:
            _HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            _HISTORY_FILE.write_text(
                json.dumps(self._entries, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass
