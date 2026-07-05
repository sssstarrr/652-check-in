from __future__ import annotations

import traceback
from typing import Any, Callable

from PyQt5.QtCore import QThread, pyqtSignal


class FunctionWorker(QThread):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)
    finished_always = pyqtSignal()

    def __init__(self, fn: Callable[..., Any], *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self) -> None:
        try:
            self.succeeded.emit(self.fn(*self.args, **self.kwargs))
        except Exception as exc:
            self.failed.emit(f"{exc}\n{traceback.format_exc(limit=3)}")
        finally:
            self.finished_always.emit()
