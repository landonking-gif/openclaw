"""Transparent TCP proxy: *:18789 (IPv4+IPv6) → 127.0.0.1:18830.

Lets VisionClaw (old build pointing at gateway port 18789) reach the
orchestrator on 18830 without auth issues.  Listens on both IPv4 and
IPv6 so iPhones on cellular/bridge100 can connect via either protocol.

Kill this once VisionClaw is rebuilt with port 18830 in Secrets.swift.
"""
import asyncio, socket

LISTEN_PORT = 18789
TARGET_HOST, TARGET_PORT = "127.0.0.1", 18830


async def _pipe(reader, writer):
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except (ConnectionResetError, BrokenPipeError, asyncio.CancelledError):
        pass
    finally:
        writer.close()


async def _handle(client_r, client_w):
    try:
        upstream_r, upstream_w = await asyncio.open_connection(TARGET_HOST, TARGET_PORT)
    except OSError as e:
        print(f"[proxy] upstream connect failed: {e}")
        client_w.close()
        return
    await asyncio.gather(_pipe(client_r, upstream_w), _pipe(upstream_r, client_w))


async def main():
    # Listen on both IPv4 and IPv6
    servers = []

    # IPv6 on all interfaces (includes link-local fe80:: on bridge100)
    try:
        srv6 = await asyncio.start_server(_handle, "::", LISTEN_PORT,
                                           family=socket.AF_INET6)
        servers.append(srv6)
    except OSError as e:
        print(f"[proxy] IPv6 bind failed: {e}")

    # IPv4 on all interfaces
    try:
        srv4 = await asyncio.start_server(_handle, "0.0.0.0", LISTEN_PORT,
                                           family=socket.AF_INET)
        servers.append(srv4)
    except OSError as e:
        print(f"[proxy] IPv4 bind failed: {e}")

    if not servers:
        print("[proxy] FATAL: could not bind on any address")
        return

    all_addrs = []
    for s in servers:
        for sock in s.sockets:
            all_addrs.append(str(sock.getsockname()))
    print(f"[proxy] listening on {', '.join(all_addrs)} → {TARGET_HOST}:{TARGET_PORT}")

    await asyncio.gather(*(s.serve_forever() for s in servers))

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
