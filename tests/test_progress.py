import hashlib
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from riptide.core.transfer import TransferProgress, format_bytes, format_eta


def test_format_bytes_and_eta():
    assert format_bytes(500) == "500 B"
    assert format_bytes(2048) == "2.0 KB"
    assert format_eta(45) == "45s"
    assert format_eta(90) == "1m 30s"
    assert format_eta(None) == "--"


def test_progress_remaining_and_fraction():
    progress = TransferProgress(1000)
    progress.update(250)
    assert progress.remaining == 750
    assert progress.fraction == 0.25




class FakeSftpFile:
    def __init__(self, store, name, mode):
        self.store = store
        self.name = name
        self.mode = mode
        self.pos = 0
        if mode == "wb":
            store[name] = bytearray()

    def seek(self, offset):
        self.pos = offset

    def write(self, data):
        buf = self.store[self.name]
        if self.pos > len(buf):
            buf.extend(b"\x00" * (self.pos - len(buf)))
        end = self.pos + len(data)
        if end > len(buf):
            buf.extend(b"\x00" * (end - len(buf)))
        buf[self.pos:end] = data
        self.pos = end

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeStat:
    def __init__(self, size):
        self.st_size = size


class FakeSftp:
    def __init__(self):
        self.store = {}
        self.renamed = []

    def stat(self, path):
        if path in self.store:
            return FakeStat(len(self.store[path]))
        raise FileNotFoundError(path)

    def open(self, path, mode):
        return FakeSftpFile(self.store, path, mode)

    def rename(self, src, dst):
        self.store[dst] = self.store.pop(src)
        self.renamed.append((src, dst))

    def remove(self, path):
        self.store.pop(path, None)


