"""
Async P2P peer listener.

Run one listener per peer. It accepts newline-delimited JSON messages directly
from other peers and stores them locally, independent of the tracker/web app.
"""

import argparse
import asyncio
import json
import os
import time


def _message_path(peer_id):
    safe_peer = "".join(ch for ch in peer_id if ch.isalnum() or ch in ("-", "_"))
    return os.path.join("db", "peer_{}_messages.jsonl".format(safe_peer or "default"))


async def append_message(peer_id, message):
    """Persist received P2P messages in a simple JSONL file."""
    os.makedirs("db", exist_ok=True)
    message.setdefault("created_at", time.time())
    message.setdefault("source", "p2p")
    path = _message_path(peer_id)
    line = json.dumps(message) + "\n"
    await asyncio.to_thread(_append_line, path, line)
    print("[PeerServer] saved message for {} at {}".format(peer_id, path))


def _append_line(path, line):
    with open(path, "a", encoding="utf-8") as f:
        f.write(line)


async def handle_peer(reader, writer, peer_id):
    """Handle one direct peer connection using asyncio streams."""
    addr = writer.get_extra_info("peername")
    print("[PeerServer] accepted connection from {}".format(addr))
    try:
        raw = await reader.readline()
        if not raw:
            print("[PeerServer] empty message from {}".format(addr))
            return

        message = json.loads(raw.decode("utf-8"))
        print("[PeerServer] received message: {}".format(message))
        await append_message(peer_id, message)
        ack = {
            "ok": True,
            "peer_id": peer_id,
            "received_from": message.get("from"),
            "addr": str(addr),
        }
        writer.write(json.dumps(ack).encode("utf-8") + b"\n")
        await writer.drain()
        print("[PeerServer] sent ack to {}".format(addr))
    except json.JSONDecodeError:
        print("[PeerServer] invalid JSON from {}".format(addr))
        writer.write(json.dumps({"ok": False, "error": "invalid json"}).encode("utf-8") + b"\n")
        await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()
        print("[PeerServer] closed connection from {}".format(addr))


async def peer_server(host="127.0.0.1", port=9101, peer_id="peer"):
    """Start the non-blocking P2P listener."""
    server = await asyncio.start_server(
        lambda reader, writer: handle_peer(reader, writer, peer_id),
        host,
        int(port),
    )
    sockets = ", ".join(str(sock.getsockname()) for sock in server.sockets or [])
    print("[PeerServer] {} listening at {}".format(peer_id, sockets))
    try:
        async with server:
            await server.serve_forever()
    except asyncio.CancelledError:
        print("[PeerServer] {} stopped".format(peer_id))


def main():
    parser = argparse.ArgumentParser(prog="PeerServer")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9101)
    parser.add_argument("--peer-id", default="peer")
    args = parser.parse_args()
    try:
        asyncio.run(peer_server(args.host, args.port, args.peer_id))
    except KeyboardInterrupt:
        print("\n[PeerServer] shutdown requested")


if __name__ == "__main__":
    main()
