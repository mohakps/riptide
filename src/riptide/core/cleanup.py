"""riptide --cleanup: remove the firewall rule, delete the identity and saved peers.

This is a cleanup and reset command, not a full uninstall. It removes
the firewall rule, deletes the local identity and saved peers, then
exits without launching the Textual UI. It does not uninstall the
program itself, and it does not remove the router port forward,
because Riptide cannot log into the router.

Order and safety, as in the security plan: the firewall rule is
removed first, with elevation (UAC on Windows, pkexec on Linux).
Only if that succeeds, or if the rule is already not found, are
the identity and peers deleted. If the user cancels elevation,
or the firewall removal fails, the command aborts and deletes
nothing, and reports that nothing was deleted. A second run
reports "not found" instead of erroring.

Exit codes: 0 means the cleanup completed, including a second run
where nothing was left to delete. 1 means nothing was deleted:
the user declined confirmation, cancelled the elevation prompt,
or the firewall removal failed. The full removal order is:
run riptide --cleanup first, then pip uninstall riptide-transfer,
then delete the router forward manually.
"""
from __future__ import annotations

from pathlib import Path

from .config import config_dir, load_config
from .firewall import remove_firewall_port


def run_cleanup(yes: bool = False, home: Path | None = None) -> int:
    """Run the cleanup and return the process exit code."""
    directory = config_dir(home)
    config = load_config(home=home)
    port = config.session_port
    identity_key = directory / "identity.key"
    identity_cert = directory / "identity.crt"
    config_file = directory / "config.toml"

    print("riptide --cleanup will delete:")
    print(f"  - Firewall rule: name Riptide, TCP, inbound, port {port} (Private, Public on Windows)")
    print(f"  - Identity: {identity_key} and {identity_cert}")
    print(f"  - Saved peers and settings: {config_file} (the whole {directory} folder)")
    if port != 50000:
        print(f"  - A custom session port {port} resets to the default 50000")
    print("It will not delete received files, .part files in the launch folder,")
    print("the program itself, or the router port forward.")
    print()

    if not yes:
        try:
            answer = input("Type YES to continue: ")
        except (EOFError, KeyboardInterrupt):
            print("Cleanup cancelled, nothing was deleted.")
            return 1
        if answer.strip() != "YES":
            print("Cleanup cancelled, nothing was deleted.")
            return 1

    result = remove_firewall_port(port)
    if result in ("cancelled", "failed"):
        print("Cleanup aborted: nothing was deleted, the firewall rule remains.")
        return 1

    identity_found = identity_key.exists() or identity_cert.exists()
    peers_found = config_file.exists()
    if directory.exists():
        import shutil

        try:
            shutil.rmtree(directory)
        except Exception as exc:
            print(f"Could not delete {directory}: {exc}")
            print("The firewall rule was already removed. Delete the folder manually.")
            return 1

    print(f"Firewall rule: {'removed' if result == 'removed' else 'not found, nothing to remove'}.")
    print(f"Identity: {'deleted' if identity_found else 'not found'}.")
    print(f"Saved peers: {'deleted' if peers_found else 'not found'}.")
    print(f"Delete the port {port} forward in your router settings manually; Riptide cannot log into your router.")
    print("To remove the program itself, run: pip uninstall riptide-transfer")
    return 0
