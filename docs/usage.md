# Usage

## Roles

| Menu item | Action | Pick it if |
| --- | --- | --- |
| Create Server, top | Listens for an incoming connection | You have a public IP, or a working port forward |
| Join Server, second | Dials out to the other side | You are behind CGNAT, or behind a strict firewall |

From v0.6.0 onward, Create means listener and Join means dialler. Older versions used the names the other way round.

## First transfer

1. Create side: run `riptide` in the folder you want to receive into. Choose Create Server. Share the public address or DDNS hostname shown on that page, only with the other person. Keep the page open.
2. Join side: run `riptide` in the folder you want to send from or receive into. Choose Join Server. Enter the creator hostname or IP in the HOSTNAME input, or pick a saved device. Press Enter.
3. Approve the connection when asked. On a first connection, check the certificate fingerprint if the transfer is sensitive. Compare it with the other person over a separate channel, for example a call or message, before pressing Allow.
4. Send: in the file manager, select files with Space, press Enter. The batch sends in order, one file at a time.
5. Request: type a peer path in Download From Peer, press Enter. The peer sees Allow and Deny. On Allow, the file arrives as a normal send. On Deny, nothing is sent.
6. Files arrive in the folder where the receiving side ran `riptide`, under their original filenames.

If you are behind CGNAT, swap roles. Let the other side Create, and you Join. See [architecture.md](architecture.md) for CGNAT, port forwarding, firewall, and DDNS.

## Launch folder

The folder where you run `riptide` is the working folder for that side. Received files go there. Sent files are browsed from there, unless you navigate elsewhere in the file manager. Launch from the right folder, or navigate to it after opening the file manager.

## File manager

- Up and Down move in the list.
- Space opens a folder, or selects and deselects a file.
- Backspace erases Find text. When Find is empty, Backspace goes up a folder.
- Typing with the file list focused searches the current folder live. The query shows in `Find:` at the right of the file box header.
- Changing directory resets Find, and auto-highlights the first real file or folder, not the `..` row.
- `0` deselects all files, when you are not typing in an input.
- Folders appear first, with a folder icon and a trailing `/`. No size or date is shown for folders.
- Selected files are listed with full paths under the file box, in accent colour. Hovered files show in white. Remaining files show in grey.

## Download requests

A download request name can be absolute on the peer, for example `/home/friend/report.pdf`, or relative to the peer launch folder, for example `report.pdf`. The peer sees the request, with Allow and Deny buttons. Multiple requests queue. The sent file header carries only the basename, so the receiver always saves into its own launch folder. This blocks path traversal from a peer-supplied path.

## Progress

Progress shows for the batch and for the current file: speed, transferred total, remaining size, and ETA, plus a progress bar. Speed is measured from spaced reports, at most every 0.1 seconds, plus the final chunk. This avoids the burst artefact where queued UI callbacks made speed read 4 to 5 times too high in versions before v0.6.0.

## Saved connections

Peers you connect to are saved in `~/.riptide/config.toml`, on Windows in the `.riptide` folder under your home directory. Each saved peer stores name, hostname, and certificate fingerprint. It never stores a private key.

On Join Server, saved devices appear as a list. Up and Down move in the list. Tab cycles between the list and the hostname input. Enter connects with the selected device, or with the hostname typed in the input. When the hostname input is focused, saved devices show unhighlighted, all grey.

## Setup, once, on the Create side

1. Router: forward TCP port 50000 to your PC current LAN address. If your PC LAN address changes later, update the rule, or set a DHCP reservation for your PC in the router.
2. PC firewall: when you click Create Server, Riptide checks TCP port 50000 in the OS firewall and adds a rule if it is closed. On Windows it uses netsh. On Linux it uses `ufw`, `firewalld`, `iptables`, or `nftables`, with passwordless sudo when needed. If Riptide cannot add the rule, because it is not run as admin, or sudo needs a password, the Create page shows the exact command to run manually. On Linux, that command is `sudo ufw allow 50000/tcp` for `ufw`, or the equivalent for your firewall tool. While Create Server waits, Riptide re-checks every 20 s, so turning the rule off after clicking still warns and tries to open it again.
3. DDNS, if your public IP changes on router restart: set up a DDNS hostname, for example through your router DDNS settings or a DDNS client, and share the hostname, not the raw IP.

The Join side normally needs no port forward and no inbound firewall rule, because it makes an outbound connection.

## Update and uninstall

Update:

```sh
pipx upgrade riptide
```

If upgrade fails:

```sh
pipx uninstall riptide
pipx install git+https://github.com/mohakps/riptide
```

Uninstall the program:

```sh
pipx uninstall riptide
```

Uninstall does not delete `~/.riptide/`. Delete that folder yourself for a clean start. That also deletes your TLS identity, so peers will see a new fingerprint next time.

## Shortcuts, full list

### Menu

| Key | Action |
| --- | --- |
| Up / Down | Move between Create Server and Join Server |
| Enter | Select |
| Esc / q | Quit |

### File transfer page

| Key | Action |
| --- | --- |
| Up / Down | Move in the file list |
| Space | Open a folder, or select / deselect a file |
| Enter | Send selected files |
| Backspace | Erase Find text, or go up a folder when Find is empty |
| 0 | Deselect all files |
| Tab | Cycle between file list and download input |
| Esc | Clear Find first, if searching, else leave the session |
| Typing, file list focused | Live search, shown in `Find:` |

### Create Server and Join Server pages

| Key | Action |
| --- | --- |
| Space | Select the focused button, or focus Allow when a connection is waiting |
| Enter | Create / Join, or Allow when a connection is waiting |
| Backspace | Deny when a connection is waiting. In the hostname input, Backspace deletes text. |
| Esc | Back |
