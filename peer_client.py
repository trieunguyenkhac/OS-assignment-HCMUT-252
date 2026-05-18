"""
Async P2P client helpers.

This module is intentionally standard-library only. It is the direct peer side
of the assignment: messages are sent with asyncio.open_connection(), so live
chat does not have to flow through the tracker after peers discover each other.
"""

import argparse
import asyncio
import json


async def send_peer_message(host, port, message, timeout=5):
    """Send one JSON message to a peer listener using asyncio streams."""
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(host, int(port)),
        timeout=timeout,
    )
    try:
        payload = json.dumps(message).encode("utf-8") + b"\n"
        writer.write(payload)
        await writer.drain()

        raw_ack = await asyncio.wait_for(reader.readline(), timeout=timeout)
        if not raw_ack:
            return {"ok": False, "error": "peer closed without ack"}
        return json.loads(raw_ack.decode("utf-8"))
    finally:
        writer.close()
        await writer.wait_closed()


async def broadcast_peer_messages(peers, message, timeout=5):
    """Broadcast one message to many peers concurrently."""
    tasks = [
        send_peer_message(peer["ip"], peer["port"], message, timeout=timeout)
        for peer in peers
    ]
    if not tasks:
        return []

    results = await asyncio.gather(*tasks, return_exceptions=True)
    normalized = []
    for peer, result in zip(peers, results):
        if isinstance(result, Exception):
            normalized.append({
                "peer_id": peer.get("peer_id"),
                "ok": False,
                "error": str(result),
            })
        else:
            normalized.append({
                "peer_id": peer.get("peer_id"),
                "ok": bool(result.get("ok")),
                "response": result,
            })
    return normalized


async def main():
    parser = argparse.ArgumentParser(prog="PeerClient")
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--from-peer", default="client")
    parser.add_argument("--to-peer", default=None)
    parser.add_argument("--text", required=True)
    args = parser.parse_args()

    message = {
        "from": args.from_peer,
        "to": args.to_peer,
        "text": args.text,
    }
    print(await send_peer_message(args.host, args.port, message))


if __name__ == "__main__":
    asyncio.run(main())
