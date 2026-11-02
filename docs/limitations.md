# Limitations

- First setup on the Create side is manual: port forward 50000 on the router, and an inbound firewall allow on the PC, once. DDNS is needed if the public IP changes often. This is the price of directness. A cloud service hides this setup behind its own servers. Riptide has no servers to hide it behind.
- No direct connection between two CGNAT devices on IPv4, unless both have global IPv6. There is no relay fallback in the current version. Workaround: use a third reachable peer, or IPv6, if both sides have it.
- Folders cannot be sent yet. Workaround: zip a folder first and send the zip, or select its files one by one. Folder sending is the headline future feature.
- No resume for an interrupted file. Workaround: restart that file from the start. The `.part` file is kept on hash mismatch or interruption, but it is not resumed yet.
- One file at a time, in batch order. No parallel streams. This is simpler and more reliable, but it does not saturate a very fast link as well as parallel streams could.
- Both sides must be online together. No offline queue, and no send now, receive later.
- No discovery. You must exchange the host address outside Riptide, by message, call, or DDNS hostname. Riptide does not find your peer for you.
- Terminal only, Windows and Linux primarily. No graphical interface, no mobile app. macOS is not specifically tested.
- No compression, deduplication, or delta sync. A file is sent whole, every time, even if the receiver already has most of it.
- Trust is manual. Fingerprint approval is a real security decision, and a careless Allow on a first connection defeats it. See [security.md](security.md).
- An open TCP session does not survive a public IP change. If the IP changes mid-transfer, restart the session.
