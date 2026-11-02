# Troubleshooting

| Symptom | Most likely cause | Check |
| --- | --- | --- |
| Join times out, no error from Create | Create side is behind CGNAT, or port forward or firewall is missing | Red CGNAT banner on Create? Router forward for 50000 to the right LAN address? PC firewall allow for 50000? |
| Address already in use on Create | Another Riptide is still listening, or another program uses 50000, for example DB2, Jenkins, or SAP | Close the old Riptide, or check what is listening on 50000, and stop it before retrying. |
| It worked yesterday, not today | Public IP changed, or PC got a new LAN address | Use DDNS, share the new address, update the router forward to the new LAN address. |
| Fingerprint changed, session aborts | Peer reinstalled, deleted `~/.riptide/`, or a different machine | Confirm with the peer, over another channel, that they reinstalled, then remove the old peer from config and trust the new fingerprint deliberately. |
| Transfer starts, then stops, session ends | IP changed mid-transfer, router or NAT timeout, or one side closed Riptide | Restart the session. There is no resume yet, so the file restarts from the start. |
| Speed looks too high, then drops | Old bug, fixed in v0.6.0 | Update both sides to v0.6.0 or later. Sender progress is now throttled to 0.1 s, like the receiver. |
| Download request never arrives | Peer did not Allow, or the path on the peer is wrong | Check the peer Allow and Deny prompt, and that the path is absolute on the peer or relative to the peer launch folder. |
| Files arrive with a `.part` suffix and no rename | Hash mismatch, or transfer was interrupted | Do not rename it by hand and trust it. Re-send the file and check the ack. |
| Public address shows could not be determined on Create | No internet, or STUN and HTTPS checks both failed | Check internet access, DNS, and whether UDP to a STUN server or HTTPS to an IP check service is blocked. |
| CGNAT banner does not appear, but connection still fails | UPnP is off, so the CGNAT check is inconclusive, or the router forward or firewall is wrong | Check the router WAN address directly. If it is in `100.64.0.0/10`, or private, you are behind CGNAT or double NAT, even without a banner. Check the forward and firewall as well. |
| Join side cannot type a hostname | Hostname input is not focused | Press Tab to cycle to the hostname input, or pick a saved device first, then Tab to the input. |
