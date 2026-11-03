import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from riptide.core.session import HostListener, join_session, unique_final_path


def _free_port():
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_unique_final_path_rules(tmp_path):
    assert unique_final_path(tmp_path, "report.pdf") == tmp_path / "report.pdf"
    (tmp_path / "report.pdf").write_text("old")
    assert unique_final_path(tmp_path, "report.pdf") == tmp_path / "report (1).pdf"
    (tmp_path / "report (1).pdf").write_text("old1")
    assert unique_final_path(tmp_path, "report.pdf") == tmp_path / "report (2).pdf"

    assert unique_final_path(tmp_path, "notes") == tmp_path / "notes"
    (tmp_path / "notes").write_text("old")
    assert unique_final_path(tmp_path, "notes") == tmp_path / "notes (1)"

    assert unique_final_path(tmp_path, "archive.tar.gz") == tmp_path / "archive.tar.gz"
    (tmp_path / "archive.tar.gz").write_text("old")
    assert unique_final_path(tmp_path, "archive.tar.gz") == tmp_path / "archive.tar (1).gz"

    assert unique_final_path(tmp_path, ".bashrc") == tmp_path / ".bashrc"
    (tmp_path / ".bashrc").write_text("old")
    assert unique_final_path(tmp_path, ".bashrc") == tmp_path / ".bashrc (1)"

    # Incoming name that already ends in (1) is treated literally.
    (tmp_path / "report (1).pdf").unlink()
    (tmp_path / "report (1).pdf").write_text("x")
    # report.pdf is taken, report (1).pdf is taken, so next is report (2).pdf,
    # but an incoming report (1).pdf, when taken, becomes report (1) (1).pdf.
    assert unique_final_path(tmp_path, "report (1).pdf") == tmp_path / "report (1) (1).pdf"

    # A directory with the same name counts as existing.
    (tmp_path / "folder").mkdir(exist_ok=True)
    assert unique_final_path(tmp_path, "folder") == tmp_path / "folder (1)"

    # A symlink counts as existing, so it is never replaced.
    target = tmp_path / "target.txt"
    target.write_text("target")
    (tmp_path / "link.txt").symlink_to(target)
    assert unique_final_path(tmp_path, "link.txt") == tmp_path / "link (1).txt"


def test_push_never_overwrites(tmp_path):
    host_dir = tmp_path / "host"
    client_dir = tmp_path / "client"
    host_dir.mkdir()
    client_dir.mkdir()
    (host_dir / "report.pdf").write_text("original content")
    (client_dir / "report.pdf").write_text("new content")
    port = _free_port()
    received = {}
    host_session = {}

    def host_worker():
        listener = HostListener(port, host_dir, device="host", home=tmp_path / "jhome", approve=lambda d, fp, st, old: True)
        s = listener.wait_for_client()
        s.on_file_received = lambda n, ok, r: received.update({"name": n, "ok": ok, "reason": r})
        s.start()
        host_session["s"] = s

    t = threading.Thread(target=host_worker, daemon=True)
    t.start()
    time.sleep(0.5)
    client = join_session("127.0.0.1", port, client_dir, device="client", home=tmp_path / "chome", approve_fingerprint=lambda fp: True)
    client.start()
    assert client.send_file(client_dir / "report.pdf")
    time.sleep(1)
    assert received.get("ok") is True
    # Original untouched, new file saved as (1), ack/received name is (1).
    assert (host_dir / "report.pdf").read_text() == "original content"
    assert (host_dir / "report (1).pdf").read_text() == "new content"
    assert received.get("name") == "report (1).pdf"
    assert received.get("reason", "").startswith("renamed from report.pdf")

    # Second push of the same name becomes (2).
    assert client.send_file(client_dir / "report.pdf")
    time.sleep(1)
    assert (host_dir / "report (2).pdf").read_text() == "new content"
    assert received.get("name") == "report (2).pdf"
    client.close()
    host_session["s"].close()


def test_push_no_duplicate_uses_original_name(tmp_path):
    host_dir = tmp_path / "host2"
    client_dir = tmp_path / "client2"
    host_dir.mkdir()
    client_dir.mkdir()
    (client_dir / "fresh.txt").write_text("fresh")
    port = _free_port()
    received = {}
    host_session = {}

    def host_worker():
        listener = HostListener(port, host_dir, device="host", home=tmp_path / "jhome2", approve=lambda d, fp, st, old: True)
        s = listener.wait_for_client()
        s.on_file_received = lambda n, ok, r: received.update({"name": n, "ok": ok, "reason": r})
        s.start()
        host_session["s"] = s

    t = threading.Thread(target=host_worker, daemon=True)
    t.start()
    time.sleep(0.5)
    client = join_session("127.0.0.1", port, client_dir, device="client", home=tmp_path / "chome2", approve_fingerprint=lambda fp: True)
    client.start()
    assert client.send_file(client_dir / "fresh.txt")
    time.sleep(1)
    assert received.get("name") == "fresh.txt"
    assert received.get("ok") is True
    assert (host_dir / "fresh.txt").read_text() == "fresh"
    client.close()
    host_session["s"].close()
