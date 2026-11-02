# Sources and references

## How this was built

Riptide was built by its author, with AI assistance disclosed here:

- Meta Muse: primary assistant for design discussion, implementation, testing, and documentation, including the session and Join rework, the and this README.
- Gemini 3.8 Flash: TUI Design.

AI-generated code was tested, not trusted blindly. The test suite and headless Textual pilots are part of the workflow, and live two-machine testing is what proves a transfer.

## References

- Forouzan, Data Communications and Networking: the Computer Networks textbook behind the course syllabus this project was built for, and the source for the OSI and TCP/IP, NAT, routing, and socket treatment in [architecture.md](architecture.md).
- RFC 793, Transmission Control Protocol: TCP, the reliable byte stream Riptide builds on.
- RFC 8446, The Transport Layer Security (TLS) Protocol Version 1.3: TLS, as negotiated by Python `ssl`.
- RFC 5389, Session Traversal Utilities for NAT (STUN): how Riptide learns its public address.
- RFC 6598, IANA-Reserved IPv4 Prefix for Shared Address Space: the `100.64.0.0/10` CGNAT range.
- RFC 6888, Common Requirements for Carrier-Grade NATs (CGNs): what a CGNAT box is required to do, and why it breaks inbound connections.
- RFC 6335, Internet Assigned Numbers Authority (IANA) Procedures for the Management of the Service Name and Transport Protocol Port Number Registry: why 50000 is in the dynamic and private range and cannot be IANA-reserved.
- Python documentation for `ssl`, `socket`, and `hashlib`, and Textual documentation for the terminal UI.

## Contributing

1. Fork the repository, and clone your fork.
2. Install in a virtual environment with `pip install -e .`, and run tests with `pytest`. Async screen tests need `pytest-asyncio`.
3. Keep UI names consistent: Create means listener, Join means dialler.
4. Do not store private keys in `config.toml`.
5. Add or update tests for any behaviour change, and run a headless pilot for any screen change before pushing.
6. Open a pull request with what changed, what you tested, and what you did not live-test, so the maintainer does not have to guess.
