# riptide

Direct, encrypted PC-to-PC file transfer in the terminal. No cloud upload, no website in the data path.

```
          Ψ  R I P T I D E  Ψ
     ~~~  direct file transfer  ~~~
```

Theme: dark grey background, bright soft red accent. The UI never displays a port number.

## Install (GitHub only, no PyPI)

The name is tentative, so this is not published to PyPI.

```sh
pipx install git+https://github.com/mohakps/riptide
```

Then, from any folder you want to share from or receive into:

```sh
riptide
riptide --help
riptide --version
```

## Usage, v3: Create Server / Join Server, over SSH

Main menu: Create Server, Join Server, Exit. Arrow keys + Enter, Esc to go back. Set-up is disabled in the menu in v3; Only the public joiner needs an SSH server running (from the v1 set-up, or installed manually). The CGNAT creator only needs an SSH client, which riptide includes.

There is no pairing code in v3, and no Send / Receive menu. File direction is independent of who created or joined.

### The one networking rule

The CGNAT side must be the side that dials out. "Create" and "Join" are session roles, not network roles. Calling the CGNAT side "server" does not make it reachable.

### Create Server (CGNAT side, if one side is CGNAT)

1. Enter the joiner as `user@host`. This is the public side's username and hostname / DDNS name.
2. Step 1, TLS session + SSH key exchange: your riptide dials the joiner's TLS listener, the joiner presses Allow, both sides exchange SSH public keys over TLS and add each other's key to `authorized_keys`. No code to type, no key to paste, no password.
3. Step 2, SSH: your riptide dials the joiner's SSH server on the standard SSH port with its riptide key. SSH host fingerprint is checked, Allow on first connect, abort if it changed.
4. You are now in an SSH session. Send selected (SFTP upload) and Download remote file (SFTP download) both work from here.

### Join Server (public side, if one side is CGNAT)

1. Open Join Server and keep it open. You do not dial the creator, because the creator may be behind CGNAT and unreachable.
2. When the creator dials in over TLS, press Allow. SSH keys are exchanged automatically, and your SSH server must be running.
3. You are now in the same SSH session. Send selected on your side asks the creator to download that file from you via SFTP. Files the creator uploads arrive via your SSH server, in your home folder.

### In a session

- File data goes over SSH/SFTP, not over TLS. TLS is only control + key exchange.
- Files are written with a `.part` suffix and renamed only after a size check, then SHA-256 is verified when an SSH exec channel is available and reported. A mismatch is reported, not silently accepted.
- Progress shows per-file progress and sent size.

### One-time network steps for the public side

- SSH port forwarded to their machine once (standard SSH port, from v1).
- TLS session port forwarded to their machine once, for key exchange (internal session port 49872, never shown in the UI).
- The CGNAT side needs no port forward.
- If both sides have a unique global IPv6 address, they can connect directly over IPv6 and CGNAT on IPv4 does not matter.

Saved peers live in `~/.riptide/config.toml` (on Windows, the `.riptide` folder under your home directory). That file contains hosts and fingerprints only, never private keys. SSH keys live in `~/.ssh/id_riptide`, TLS identity keys live under `~/.riptide/` with the key file at 0600.

## Security notes, v3

- File data is SSH/SFTP, with key-only auth after the TLS key exchange.
- On first connect, TLS certificate fingerprint and SSH host fingerprint are both checked, Allow on first connect, abort if either changes.
- No pairing code, no pairing listener, no public key pasting, no password sharing.
- Partial files stay as `.part` until verified, so a failed transfer does not look like a complete file.

## Limitations in v3

- Files only, no folders.
- If both sides are CGNAT on IPv4 and neither has IPv6, this model does not work on its own: a reachable third peer or relay would be needed.
- Live two-machine CGNAT testing over SSH is still needed before calling this finished. Localhost tests pass for TLS session, SSH key exchange over TLS, both-direction TLS control, SFTP download helper, and fingerprint-change abort. A local SSH server was not available on the test VM, so live SSH/SFTP transfer itself is untested in this build.
- Set-up SSH from v1 is present in the code but disabled in the menu in v3.

## Development

```sh
python -m venv .venv
.venv/bin/pip install -e .
.venv/bin/pip install pytest
.venv/bin/python -m pytest -q
python -m compileall src/riptide
```
