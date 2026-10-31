from __future__ import annotations

import threading
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, ProgressBar, Static

from ..core.config import Config
from ..core.focus import focus_first, handle_arrow_key
from ..core.file_select import total_size
from ..core.keys import ensure_keypair
from ..core.ssh_client import RiptideSSH, parse_peer
from ..core.transfer import TransferProgress, format_bytes, format_eta, remote_sha256, sha256_file, upload_files
from ..theme import HEADER_LINES


class TransferScreen(Screen):
    def __init__(self, peer_label: str, files: list[Path], config: Config) -> None:
        super().__init__()
        self.peer_label = peer_label
        self.files = files
        self.config = config
        self.progress = TransferProgress(total_size(files))
        self._ssh: RiptideSSH | None = None

    def compose(self) -> ComposeResult:
        names = ", ".join(p.name for p in self.files)
        yield Vertical(
            Static("\n".join(HEADER_LINES), classes="header"),
            Static("TRANSFER", classes="accent"),
            Static(f"To: {self.peer_label}"),
            Static(f"Files: {names}"),
            Static("Status: waiting to connect", id="status"),
            Static("Current file: -", id="current"),
            ProgressBar(total=100, id="file_bar"),
            ProgressBar(total=100, id="total_bar"),
            Static("Speed: -  |  Sent: -  |  Remaining: -  |  ETA: -", id="stats"),
            Button("Back", id="back"),
        )

    def on_mount(self) -> None:
        focus_first(self)
        threading.Thread(target=self._run_worker, daemon=True).start()

    def _update_ui(self, status: str, current: str) -> None:
        try:
            self.query_one("#status", Static).update(f"Status: {status}")
            self.query_one("#current", Static).update(f"Current file: {current}")
            total_bar = self.query_one("#total_bar", ProgressBar)
            total_bar.progress = self.progress.fraction * 100
            speed = self.progress.speed_ema
            self.query_one("#stats", Static).update(
                f"Speed: {format_bytes(speed)}/s  |  Sent: {format_bytes(self.progress.sent)}  |  "
                f"Remaining: {format_bytes(self.progress.remaining)}  |  ETA: {format_eta(self.progress.eta_seconds)}"
            )
        except Exception:
            pass

    def _on_file(self, name: str, sent_for_file: int, size: int) -> None:
        fraction = (sent_for_file / size * 100) if size else 100
        try:
            self.app.call_from_thread(self._set_file_progress, name, fraction)
        except Exception:
            pass

    def _set_file_progress(self, name: str, fraction: float) -> None:
        try:
            self.query_one("#file_bar", ProgressBar).progress = fraction
            self._update_ui("Transferring", name)
        except Exception:
            pass

    def _run_worker(self) -> None:
        try:
            user, host = parse_peer(self.peer_label)
            known = self.config.peer_for(user, host)
            private, _ = ensure_keypair()
            ssh = RiptideSSH(user, host, port=self.config.ssh_port, key_path=private,
                            known_fingerprint=known.fingerprint if known else "")
            self._ssh = ssh
            self.app.call_from_thread(self._update_ui, "Connecting", "-")
            ssh.connect(on_stage=lambda m: self.app.call_from_thread(self._update_ui, m, "-"),
                        allow_new_host=True)
            sftp = ssh.open_sftp()
            try:
                remote_dir = "."
                # Verification: size before rename is in upload_files; SHA-256
                # is checked here after upload and reported, not hidden.
                uploaded = upload_files(sftp, self.files, remote_dir, self.progress, on_file=self._on_file)
                results = []
                for local, remote in zip(self.files, uploaded):
                    remote_hash = remote_sha256(ssh, remote)
                    local_hash = sha256_file(local)
                    if remote_hash is None:
                        results.append(f"{local.name}: uploaded, remote hash unavailable")
                    elif remote_hash == local_hash:
                        results.append(f"{local.name}: verified")
                    else:
                        results.append(f"{local.name}: HASH MISMATCH, re-transfer this file")
                self.app.call_from_thread(self._update_ui, "Done: " + "; ".join(results), "-")
            finally:
                try:
                    sftp.close()
                except Exception:
                    pass
                ssh.close()
        except Exception as exc:
            self.app.call_from_thread(self._update_ui, f"Failed: {exc}", "-")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            if self._ssh is not None:
                self._ssh.close()
            self.app.pop_screen()

    async def on_key(self, event) -> None:
        if event.key == "escape":
            if self._ssh is not None:
                self._ssh.close()
            self.app.pop_screen()
            return
        if handle_arrow_key(self, event.key):
            event.stop()
