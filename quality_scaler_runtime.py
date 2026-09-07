"""Small, Tk-free runtime primitives for responsive UI work."""

from collections import OrderedDict
from contextlib import contextmanager
from concurrent.futures import Future
import os
import tempfile
from queue import Empty, Queue
from threading import Thread


@contextmanager
def atomic_destination(path):
    """Publish a complete file, preserving the old destination on failure."""
    descriptor, temporary = tempfile.mkstemp(prefix=".qualityscaler-", suffix=".tmp",
                                            dir=os.path.dirname(os.path.abspath(path)))
    os.close(descriptor)
    try:
        yield temporary
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class BackgroundJobs:
    """Bounded daemon workers; results are consumed by the owning UI thread.

    A stuck third-party decoder cannot prevent application shutdown. Pending
    work is cancelled on close; running work must never access Tk objects.
    """

    def __init__(self, workers=2, capacity=8):
        self._queue = Queue(maxsize=capacity)
        self._closed = False
        for index in range(workers):
            Thread(target=self._run, name=f"media-reader-{index}", daemon=True).start()

    def submit(self, function, *args):
        if self._closed:
            raise RuntimeError("Background jobs are closed")
        future = Future()
        self._queue.put_nowait((future, function, args))
        return future

    def _run(self):
        while not self._closed:
            try:
                future, function, args = self._queue.get(timeout=0.2)
            except Empty:
                continue
            if not future.set_running_or_notify_cancel():
                continue
            try:
                future.set_result(function(*args))
            except BaseException as error:
                future.set_exception(error)

    def close(self):
        self._closed = True
        while True:
            try:
                future, _, _ = self._queue.get_nowait()
                future.cancel()
            except Empty:
                break


class FileLRU(OrderedDict):
    """One version per path, with bounded entries and O(1) invalidation."""

    def __init__(self, limit=256):
        super().__init__()
        self.limit = limit
        self._paths = {}

    def __getitem__(self, key):
        value = super().__getitem__(key)
        self.move_to_end(key)
        return value

    def __setitem__(self, key, value):
        previous = self._paths.get(key[0])
        if previous is not None and previous != key:
            self.pop(previous, None)
        super().__setitem__(key, value)
        self.move_to_end(key)
        self._paths[key[0]] = key
        while len(self) > self.limit:
            old_key, _ = self.popitem(last=False)
            if self._paths.get(old_key[0]) == old_key:
                self._paths.pop(old_key[0], None)

    def clear(self):
        super().clear()
        self._paths.clear()

    def drop_stale(self, path, key):
        previous = self._paths.get(path)
        if previous is not None and previous != key:
            self.pop(previous, None)
            self._paths.pop(path, None)
