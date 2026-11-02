# Security

## Protected

- Confidentiality in transit. Headers and file bytes travel over one TLS-encrypted TCP connection. No third party on the path, and no cloud server, sees file contents or filenames in plaintext.
- Integrity. Every file is SHA-256 hashed by the sender before transfer, and by the receiver as it arrives. A mismatch is not renamed, and an ack reports the failure. This catches corruption and truncation, as well as tampering.
- Peer authentication, by fingerprint. A first connection requires explicit Allow of a SHA-256 certificate fingerprint, and a changed fingerprint aborts later connections. This is the same trust-on-first-use model as SSH host keys.
- Download authorisation. A peer cannot pull a file from you just because a session is open. A download request shows Allow and Deny, and Deny sends nothing.
- Private keys stay private. The TLS identity key is in `~/.riptide/identity.key` at 0600, never in `config.toml`, never sent over the network, and never logged. `config.toml` holds only hostnames, device names, and fingerprints.
- No account, password, or cloud copy. There is nothing to leak from a server breach, because there is no server holding files or credentials.

## How fingerprint trust works

1. Each machine generates one self-signed RSA-2048 key and certificate on first run, in `~/.riptide/`. The certificate is valid for 10 years.
2. On connect, each side computes the SHA-256 fingerprint of the other side certificate.
3. On a first connection, the user sees that fingerprint and presses Allow to trust it. The fingerprint is then saved with the peer.
4. On a later connection, if the fingerprint changed, the session aborts.

TLS contexts use `CERT_NONE` at the library level, because Python built-in verification would reject a self-signed certificate outright. The real verification is the fingerprint check in Riptide itself.

## Limits and risks

- Trust on first use can be tricked if you Allow blindly. If an attacker can intercept a first connection and present their own certificate, and you press Allow without checking, you will trust the attacker. For a sensitive transfer, compare the fingerprint with the other person over a separate channel, for example a call or message, before pressing Allow.
- A push is trusted after session approval. Once you Allow a session, the other side can push files to you without a per-file approval. Download requests are the ones that ask per file. Only Allow a session for a peer you intend to receive files from. Do not Allow a stranger incoming connection to see what happens.
- An exposed port is an attack surface. The Create side listens on port 50000. Anyone who learns the public IP or DDNS hostname can attempt a connection, and Riptide will show an approval prompt, but the port itself is reachable. Do not share the public address publicly, keep Riptide closed when you are not transferring, and do not forward the port on a router you do not control.
- Files at rest are not encrypted. Received files are stored as plain files in the launch folder. TLS protects them in transit, not on disk. Encrypt the disk or the file itself if that matters.
- No rate limiting, allow-list, or IP filtering in the current version. A scanner can attempt many connections and generate many approval prompts. Treat approval prompts as security decisions, not pop-ups to dismiss.
- Device names are labels, not proof of identity. A device name in a hello message is not authenticated beyond the certificate. The fingerprint is the proof.
- Path handling: the file header sent back for a download carries only the basename, so the receiver saves into its own launch folder, never into an arbitrary path supplied by the peer.
