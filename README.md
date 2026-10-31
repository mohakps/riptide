# riptide

Direct, encrypted PC-to-PC file transfer in the terminal. No cloud upload, no website in the data path.

```
          Ψ  R I P T I D E  Ψ
     ~~~  direct file transfer  ~~~
```

Theme: dark grey background, bright soft red accent. The UI never displays a port number. Peer fields are `user@host` only.

## Install (GitHub only, no PyPI)

The name is tentative, so this is not published to PyPI.

```sh
pipx install git+https://github.com/mohakps/riptide
```

Pipx creates an isolated venv and puts `riptide` on your PATH, so you do not need to set PATH up by hand (run `pipx ensurepath` once if pipx asks).

Local alternative, also without PyPI:

```sh
git clone https://github.com/mohakps/riptide
cd riptide
pipx install .
```

Then, from any folder you want to send from or receive into:

```sh
riptide
riptide --help
riptide --version
```

## Usage

Main menu: Send, Receive, Set-up SSH, Exit. Arrow keys + Enter, Esc to go back.

### Send

1. Enter a peer as `user@host` (hostname, DDNS name, IPv4, or IPv6).
2. Riptide connects in the background while you select files. Status shows Resolving, Connecting, SSH handshake, Host key check, Authenticated, or Failed with a reason. A failed connection does not block file selection.
3. Select files from the current folder: type a name, Tab to complete it, Enter to add it, Enter on a blank line to start. Or drag and drop files into the terminal: most terminals paste their paths, and riptide parses those pasted paths into the same Selected list. Both methods work at the same time.
4. Transfer shows per-file and total progress, speed, sent/total, remaining size, and ETA. Files are written with a `.part` suffix and renamed only after a size check, then SHA-256 is verified and reported. A dropped transfer can resume from the `.part` size.

Saved peers live in `~/.riptide/config.toml` (on Windows, the `.riptide` folder under your home directory). That file never contains private keys.

### Receive

Open Receive and share only the 6-digit pairing code it shows (valid 5 minutes) with the sender. The sender enters that code, not a full public key. Riptide sends the sender's public key over a pairing listener authenticated by the code, and the receiver adds it to `authorized_keys`.

Choose Allow always, Allow once, or Deny for an incoming pairing. Known peers skip the code on later transfers. If a host fingerprint ever changes, the transfer aborts with a warning instead of silently trusting the new host.

Files land in the folder where you ran `riptide`, unless you choose otherwise before accepting.

### Set-up SSH

Set-up enables the system OpenSSH server: on Windows it installs OpenSSH Server and starts the service (needs Administrator); on Linux/Arch it installs openssh and enables the service (needs sudo). It uses the standard SSH port, so it does not change your existing SSH configuration.

It tries automatic forwarding, then shows manual forwarding instructions. If forwarding fails, read the CGNAT note below.

## Reverse mode for CGNAT

If the receiver is behind CGNAT, the sender cannot dial it, and port forwarding on the receiver's router will not help. Instead, the CGNAT peer dials the public peer first. Over that connection the CGNAT peer can push a file up or pull a file down. Connection direction and file direction are independent.

The sender's side in this project is therefore the public, reachable side in the common case: a public-IP peer runs Receive/SSH, and a CGNAT peer initiates the connection to it.

## Security notes

- Transfers are key-only SSH/SFTP. No invented crypto is used.
- Private keys stay in `~/.ssh/id_riptide` (ed25519). They are never written to `~/.riptide/config.toml` or to logs.
- Turn password authentication off after pairing works. The standard SSH port is heavily scanned, so key-only auth is mandatory, not optional.
- A pairing code is single-use and expires after five minutes.
- Partial files stay as `.part` until verified, so a failed transfer does not look like a complete file.

## Simplifications in v1

- Files only, no folders. Folder transfer by zipping first is planned for v2.
- SHA-256 is checked after upload and reported; a mismatch is shown as a failure for that file and must be re-transferred, it is not automatically deleted and retried in v1.
- The pairing listener is a simple authenticated TCP exchange for the public key only. It is not a replacement for SSH authentication, which still happens for the transfer itself.
- Drag and drop depends on the terminal pasting paths. Typed names with Tab completion are the reliable fallback.
- Windows-to-Arch and Arch-to-Windows paths have been coded for, but live cross-OS testing is still needed before calling this finished.

## Development

```sh
python -m venv .venv
.venv/bin/pip install -e .
.venv/bin/pip install pytest
.venv/bin/python -m pytest -q
python -m compileall src/riptide
```
