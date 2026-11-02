# Advantages

- One direct transfer, at bottleneck speed. No server in the middle to slow, throttle, or queue it.
- About half the time of a cloud transfer for large files. Cloud transfer is upload plus download, plus server processing and queueing. Direct transfer is one transfer, sender to receiver.
- Example, in round numbers: a 10 GB file on a 100 Mbps link takes about 13 to 14 minutes direct, versus about 27 to 28 minutes via cloud, upload plus download, before cloud throttling or queueing.
- No account, storage quota, or file size limit from Riptide. Disk space is the limit.
- No third party holds a copy, so privacy does not depend on a provider policy.
- LAN speed when both PCs are on the same LAN, using a private LAN address directly, with no internet upload at all.
- No waiting for upload complete before the other side can start. The receiver writes bytes as they arrive, and progress is live on both sides.
- Any file type, any size the disk allows. Riptide does not inspect, convert, or block file types, and it streams in chunks, so it does not need to load a whole file into memory.
- No terms of service scan of files, because there is no service in the data path.
