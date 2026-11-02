# Riptide

Riptide is a terminal program for direct, encrypted, PC to PC file transfer. Run `riptide` in a folder, connect two computers, and send files from one to the other over one encrypted TCP connection. Files go straight from sender to receiver. No server stores a copy in between.

The name comes from Minecraft. Riptide is the trident enchantment that launches the player forward at high speed. With an Elytra in rain, Riptide plus Elytra is the fastest travel method in Minecraft. Riptide the program aims for the same idea for files: the shortest route, from one PC to the other.

## Screenshots

Add screenshots to a `screenshots/` folder next to this README, with these filenames.

![Homepage](screenshots/homepage.png)

![Create Server page](screenshots/create-server.png)

![Join Server page](screenshots/join-server.png)

![File transfer page](screenshots/transfer.png)

## Features

- Direct session between two PCs. One side listens, the other dials in. Both sides must be online at the same time.
- Either side can send files after the session opens. File direction does not depend on connection direction.
- Multiple file selection. Select files with Space, send the batch with Enter.
- File manager with folders, live search in `Find:`, auto-highlight of the first file or folder, and `0` to deselect all.
- File requests with approval. Type a peer path, press Enter, and nothing is sent until the peer presses Allow.
- Saved connections. Peers, hostnames, and certificate fingerprints are saved in `~/.riptide/config.toml`. Saved devices appear on the Join Server page.
- Live progress with speed, transferred total, remaining size, and ETA, on sender and receiver.
- Hash verification. Each file is SHA-256 hashed before sending, written as `.part` on receipt, and renamed only if the hash matches.
- TLS encryption for headers and file bytes, with per-machine self-signed certificates.
- Fingerprint approval. First connection to a peer shows its certificate fingerprint for approval. A changed fingerprint later aborts the session.
- CGNAT check and public address display on Create Server. A red banner appears if CGNAT blocks inbound connections.
- Dark grey terminal UI with a soft red accent, for Windows and Linux.

Security, in brief: TLS protects files in transit. Fingerprints authenticate peers. Download requests need explicit approval. Private keys stay in `~/.riptide/` at 0600 and are never stored in `config.toml`. Files on disk are not encrypted. A push after session approval does not ask per file, so only approve sessions for peers you trust. Full detail is in [docs/security.md](docs/security.md).

## Installation

GitHub only. Riptide is not published to PyPI.

Requirements: Python 3.11 or newer, `pipx`, `git`, Windows or Linux.

```sh
pipx install git+https://github.com/mohakps/riptide
```

Run it from the folder you want to send from or receive into:

```sh
riptide
```

Update:

```sh
pipx upgrade riptide
```

If upgrade fails, uninstall and install again:

```sh
pipx uninstall riptide
pipx install git+https://github.com/mohakps/riptide
```

## Usage

Create Server listens. Join Server dials. Create stays on top in the menu.

1. Create side, the public side: run `riptide`, choose Create Server, and share the public address or DDNS hostname shown on that page with the other person. Keep the page open.
2. Join side, the CGNAT side or dialling side: run `riptide`, choose Join Server, enter the creator hostname or IP, or pick a saved device, and press Enter.
3. Approve the connection when asked, on either side.
4. Send: select files with Space in the file manager, press Enter. Request: type a peer path in Download From Peer, press Enter, and wait for the peer to Allow it.
5. Files arrive in the folder where the receiving side ran `riptide`.

If the red CGNAT banner appears on Create Server, swap roles. Let the other side Create, and you Join. Full usage, shortcuts, and setup steps are in [docs/usage.md](docs/usage.md). Network terms and setup are in [docs/architecture.md](docs/architecture.md).

### Shortcuts

| Key | Action |
| --- | --- |
| Up / Down | Move in a list |
| Space | Open a folder, or select a file |
| Enter | Send selected files, or Allow a pending connection |
| Backspace | Erase Find text, go up a folder when Find is empty, or Deny a pending connection |
| 0 | Deselect all files |
| Tab | Cycle between file list and download input |
| Esc | Back, or leave the session |

## Advantages

- One direct transfer, at bottleneck speed. No server in the middle to slow, throttle, or queue it.
- About half the time of a cloud transfer for large files. Cloud transfer is upload plus download. Direct transfer is one transfer.
- No account, storage quota, or file size limit from Riptide. Disk space is the limit.
- No third party holds a copy, so privacy does not depend on a provider policy.
- LAN speed when both PCs are on the same LAN, using a private LAN address.

Full detail is in [docs/advantages.md](docs/advantages.md).

## Limitations

- First setup on the Create side is manual: port forward 50000 on the router, and an inbound firewall allow on the PC, once. DDNS is needed if the public IP changes often.
- No direct connection between two CGNAT devices on IPv4, unless both have global IPv6. There is no relay fallback.
- Folders cannot be sent yet. Zip a folder first, or select its files one by one.
- No resume for an interrupted file. It restarts from the start.
- One file at a time, in batch order. No parallel streams.
- Both sides must be online together. No offline queue.
- You must exchange the creator address outside Riptide, by message or DDNS hostname.
- Terminal only, Windows and Linux primarily. macOS is not specifically tested.

Full detail, with workarounds where they exist, is in [docs/limitations.md](docs/limitations.md).

## Docs

- [Usage](docs/usage.md): detailed usage, shortcuts, setup steps, update and uninstall.
- [Architecture](docs/architecture.md): terminology, layers, protocol, flows, and NAT behaviour.
- [Security](docs/security.md): full security detail.
- [Advantages](docs/advantages.md): full advantages.
- [Limitations](docs/limitations.md): full limitations.
- [Troubleshooting](docs/troubleshooting.md): symptom, cause, and check, in table form.
- [Project structure](docs/project-structure.md): project layout, with per-file explanations.
- [Sources and references](docs/sources-references.md): references, contributions, and how to contribute.
