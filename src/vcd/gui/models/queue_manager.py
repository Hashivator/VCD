from typing import Optional


class QueueManager:
    def __init__(self):
        self._queue: list = []

    def add(self, params: dict) -> bool:
        if params["url"] in [q["url"] for q in self._queue]:
            return False
        self._queue.append(params)
        return True

    def next(self) -> Optional[dict]:
        if not self._queue:
            return None
        self._queue[0]["_status"] = "running"
        return self._queue[0]

    def complete_current(self, ok: bool):
        if self._queue:
            self._queue[0]["_status"] = "done" if ok else "failed"
            self._queue.pop(0)

    def remove(self, row: int) -> Optional[dict]:
        if 0 <= row < len(self._queue):
            return self._queue.pop(row)
        return None

    def clear(self):
        self._queue.clear()

    @property
    def items(self) -> list:
        return list(self._queue)

    @property
    def pending_count(self) -> int:
        return len(self._queue)
