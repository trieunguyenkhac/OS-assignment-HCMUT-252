#
# Copyright (C) 2026 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course,
# and is released under the "MIT License Agreement". Please see the LICENSE
# file that should have been included as part of this package.
#
# AsynapRous release
#
# The authors hereby grant to Licensee personal permission to use
# and modify the Licensed Source Code for the sole purpose of studying
# while attending the course
#


"""
app.sampleapp
~~~~~~~~~~~~~~~~~

"""

import json
import base64
import threading
import time
import uuid
from urllib.parse import parse_qs

from daemon import AsynapRous
from peer_client import broadcast_peer_messages
from peer_client import send_peer_message
from .message_api import append_message
from .message_api import build_channel_message
from .message_api import build_direct_message
from .message_api import list_messages

app = AsynapRous()

USERS = {"admin": "admin", "guest": "guest"}
SESSIONS = {}
PEERS = {}
CHANNELS = {"general": set()}  # Membership: {"general": {"admin", "guest"}}
MESSAGES = {"general": []}     # Channel messages
DIRECT_MESSAGES = []            # Private messages: [{"from": ..., "to": ..., "text": ...}]
STATE_LOCK = threading.RLock()


def _json_response(data, status=200, headers=None):
    return json.dumps(data).encode("utf-8"), status, headers or {}


def _parse_body(body, headers=None):
    if not body:
        return _parse_query(headers)
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        form = parse_qs(body)
        return {key: values[-1] for key, values in form.items()}


def _parse_query(headers):
    query = headers.get("X-AsynapRous-Query", "") if headers else ""
    form = parse_qs(query)
    return {key: values[-1] for key, values in form.items()}


def _cookies(headers):
    raw_cookie = headers.get("Cookie", "") if headers else ""
    parsed = {}
    for item in raw_cookie.split(";"):
        if "=" in item:
            key, value = item.strip().split("=", 1)
            parsed[key] = value
    return parsed


def _basic_credentials(headers):
    auth = headers.get("Authorization", "") if headers else ""
    if not auth.startswith("Basic "):
        return None, None
    try:
        decoded = base64.b64decode(auth.split(" ", 1)[1]).decode("utf-8")
        if ":" not in decoded:
            return None, None
        return decoded.split(":", 1)
    except Exception:
        return None, None


def _current_user(headers):
    cookies = _cookies(headers)
    token = cookies.get("sessionid")
    with STATE_LOCK:
        if token in SESSIONS:
            return SESSIONS[token]

    username, password = _basic_credentials(headers)
    if USERS.get(username) == password:
        return username
    return None


def _require_user(headers):
    user = _current_user(headers)
    if user:
        return user, None
    return None, _json_response(
        {"error": "authentication required"},
        401,
        {"WWW-Authenticate": 'Basic realm="AsynapRous"'},
    )

@app.route('/whoami', methods=['GET', 'POST'])
@app.route('/whoami/', methods=['GET', 'POST'])
def whoami(headers="guest", body="anonymous"):
    """Check if user is authenticated and return current user info."""
    user = _current_user(headers)
    if user:
        return _json_response({"user": user, "authenticated": True})
    return _json_response({"error": "not authenticated"}, 401)

@app.route('/login', methods=['POST'])
def login(headers="guest", body="anonymous"):
    """
    Handle user login via POST request.

    This route simulates a login process and prints the provided headers and body
    to the console.

    :param headers (str): The request headers or user identifier.
    :param body (str): The request body or login payload.
    """
    print("[SampleApp] Logging in {} to {}".format(headers, body))
    data = _parse_body(body, headers)
    username, password = _basic_credentials(headers)
    username = username or data.get("username") or data.get("user") or "guest"
    password = password or data.get("password") or data.get("pass") or "guest"

    if USERS.get(username) != password:
        return _json_response(
            {"error": "invalid credentials"},
            401,
            {"WWW-Authenticate": 'Basic realm="AsynapRous"'},
        )

    token = uuid.uuid4().hex
    with STATE_LOCK:
        SESSIONS[token] = username
        # Auto-add user to "general" channel
        CHANNELS.setdefault("general", set()).add(username)
    return _json_response(
        {"message": "Welcome to the RESTful TCP WebApp", "user": username},
        200,
        {"Set-Cookie": "sessionid={}; Path=/; HttpOnly; SameSite=Lax".format(token)},
    )

@app.route("/echo", methods=["POST"])
def echo(headers="guest", body="anonymous"):
    print("[SampleApp] received body {}".format(body))

    try:
        message = json.loads(body)
        data = {"received": message }
        # Convert to JSON string
        return _json_response(data)[0]
    except json.JSONDecodeError:
        data = {"error": "Invalid JSON"}
        # Convert to JSON string
        return _json_response(data, 400)[0]


@app.route('/hello', methods=['PUT'])
async def hello(headers, body):
    """
    Handle greeting via PUT request.

    This route prints a greeting message to the console using the provided headers
    and body.

    :param headers (str): The request headers or user identifier.
    :param body (str): The request body or message payload.
    """
    print("[SampleApp] ['PUT'] **ASYNC** Hello in {} to {}".format(headers, body))
    data =  {"id": 1, "name": "Alice", "email": "alice@example.com"}

    # Convert to JSON string
    json_str = json.dumps(data)
    return (json_str.encode("utf-8"))


@app.route('/submit-info', methods=['POST'])
@app.route('/submit-info/', methods=['POST'])
def submit_info(headers="guest", body="anonymous"):
    user, error = _require_user(headers)
    if error:
        return error

    data = _parse_body(body, headers)
    peer_id = data.get("peer_id") or user
    ip = data.get("ip")
    port = data.get("port")
    if not ip or not port:
        return _json_response({"error": "ip and port are required"}, 400)

    try:
        port = int(port)
    except (TypeError, ValueError):
        return _json_response({"error": "port must be an integer"}, 400)

    with STATE_LOCK:
        PEERS[peer_id] = {
            "peer_id": peer_id,
            "user": user,
            "ip": ip,
            "port": port,
            "updated_at": time.time(),
        }
        CHANNELS.setdefault("general", set()).add(peer_id)
        peer = dict(PEERS[peer_id])
    return _json_response({"message": "peer registered", "peer": peer})


@app.route('/add-list', methods=['POST'])
@app.route('/add-list/', methods=['POST'])
def add_list(headers="guest", body="anonymous"):
    user, error = _require_user(headers)
    if error:
        return error

    data = _parse_body(body, headers)
    channel = data.get("channel", "general")
    peer_id = data.get("peer_id") or user
    with STATE_LOCK:
        CHANNELS.setdefault(channel, set()).add(peer_id)
        MESSAGES.setdefault(channel, [])
    return _json_response({"message": "channel joined", "channel": channel})


@app.route('/get-list', methods=['GET', 'POST'])
@app.route('/get-list/', methods=['GET', 'POST'])
def get_list(headers="guest", body="anonymous"):
    user, error = _require_user(headers)
    if error:
        return error

    with STATE_LOCK:
        peers = list(PEERS.values())
        channels = {name: sorted(peers) for name, peers in CHANNELS.items()}
    return _json_response({"peers": peers, "channels": channels})


@app.route('/channels', methods=['GET', 'POST'])
@app.route('/channels/', methods=['GET', 'POST'])
def channels(headers="guest", body="anonymous"):
    user, error = _require_user(headers)
    if error:
        return error

    with STATE_LOCK:
        channel_data = {name: sorted(peers) for name, peers in CHANNELS.items()}
    return _json_response({"channels": channel_data})


@app.route('/messages', methods=['GET', 'POST'])
@app.route('/messages/', methods=['GET', 'POST'])
def messages(headers="guest", body="anonymous"):
    user, error = _require_user(headers)
    if error:
        return error

    data = _parse_body(body, headers)
    channel = data.get("channel", "general")
    # Block fetching direct messages from /messages endpoint
    if channel == "direct":
        return _json_response({"error": "use /direct-messages endpoint instead"}, 400)
    
    with STATE_LOCK:
        # Kiểm tra xem user có join channel này không
        channel_members = CHANNELS.get(channel, set())
        if user not in channel_members:
            return _json_response({
                "error": f"user '{user}' not a member of channel '{channel}'",
                "channel": channel,
                "messages": []
            }, 403)
        
        # Chỉ trả messages của channel này
        result = list_messages(MESSAGES, channel)
    return _json_response({"channel": channel, "messages": result})


@app.route('/connect-peer', methods=['POST'])
@app.route('/connect-peer/', methods=['POST'])
def connect_peer(headers="guest", body="anonymous"):
    user, error = _require_user(headers)
    if error:
        return error

    data = _parse_body(body, headers)
    peer_id = data.get("peer_id")
    with STATE_LOCK:
        peer = PEERS.get(peer_id)
    if not peer:
        return _json_response({"error": "peer not found"}, 404)
    return _json_response({"message": "peer available", "peer": peer})


@app.route('/broadcast-peer', methods=['POST'])
@app.route('/broadcast-peer/', methods=['POST'])
async def broadcast_peer(headers="guest", body="anonymous"):
    user, error = _require_user(headers)
    if error:
        return error

    data = _parse_body(body, headers)
    channel = data.get("channel", "general")
    sender = data.get("peer_id") or user
    
    with STATE_LOCK:
        # Kiểm tra sender có trong channel không
        channel_members = CHANNELS.get(channel, set())
        if sender not in channel_members:
            return _json_response({
                "error": f"peer '{sender}' not a member of channel '{channel}'",
                "channel": channel
            }, 403)
    
    message = build_channel_message(
        sender,
        channel,
        data.get("message") or data.get("text", ""),
    )
    with STATE_LOCK:
        append_message(MESSAGES, channel, message)
        peer_ids = set(CHANNELS.get(channel, set()))
        peers = [
            dict(peer)
            for peer_id, peer in PEERS.items()
            if peer_id in peer_ids and peer_id != sender
        ]

    delivery = await broadcast_peer_messages(peers, message)
    return _json_response({
        "message": "broadcast stored and sent",
        "data": message,
        "delivery": delivery,
    })


@app.route('/send-peer', methods=['POST'])
@app.route('/send-peer/', methods=['POST'])
async def send_peer(headers="guest", body="anonymous"):
    print("[DEBUG] SEND-PEER CALLED")
    user, error = _require_user(headers)
    if error:
        return error

    data = _parse_body(body, headers)
    target_id = data.get("target") or data.get("peer_id")
    print(f"[DEBUG] target_id={target_id}, user={user}")
    print(f"[DEBUG] available peers: {list(PEERS.keys())}")
    
    with STATE_LOCK:
        peer = dict(PEERS[target_id]) if target_id in PEERS else None

    sender = data.get("from") or user
    message = build_direct_message(
        sender,
        target_id,
        data.get("message") or data.get("text", ""),
    )
    with STATE_LOCK:
        # Lưu vào global list - sẽ filter khi fetch theo sender/receiver
        DIRECT_MESSAGES.append(message)

    if peer:
        print(f"[DEBUG] CONNECTING TO {peer['ip']}:{peer['port']}")
        try:
            delivery = await send_peer_message(peer["ip"], peer["port"], message)
            print(f"[DEBUG] delivery result: {delivery}")
        except Exception as exc:
            print(f"[DEBUG] forward failed: {exc}")
            return _json_response(
                {"message": "stored locally, forward failed", "error": str(exc), "data": message},
                202,
            )
        return _json_response({
            "message": "direct message stored and sent",
            "data": message,
            "delivery": delivery,
        })

    print(f"[DEBUG] peer {target_id} not found in registry, storing locally only")
    return _json_response({"message": "direct message stored", "data": message})


@app.route('/receive-peer', methods=['POST'])
@app.route('/receive-peer/', methods=['POST'])
def receive_peer(headers="guest", body="anonymous"):
    data = _parse_body(body, headers)
    sender = data.get("from", "peer")
    receiver = data.get("to")
    message = {
        "from": sender,
        "to": receiver,
        "text": data.get("message") or data.get("text", ""),
        "created_at": data.get("created_at", time.time()),
        "source": "p2p",
    }
    with STATE_LOCK:
        # Lưu vào global list - sẽ filter khi fetch
        DIRECT_MESSAGES.append(message)
    return _json_response({"message": "peer message received", "data": message}, 201)


@app.route('/direct-messages', methods=['GET', 'POST'])
@app.route('/direct-messages/', methods=['GET', 'POST'])
def direct_messages(headers="guest", body="anonymous"):
    """Fetch direct/private messages cho user hiện tại.
    
    Chỉ trả những messages mà user là sender hoặc receiver.
    """
    user, error = _require_user(headers)
    if error:
        return error

    with STATE_LOCK:
        # Lọc: chỉ messages mà user là sender hoặc receiver
        result = [
            msg for msg in DIRECT_MESSAGES
            if msg.get("from") == user or msg.get("to") == user
        ]
    
    return _json_response({"user": user, "messages": result})


def create_sampleapp(ip, port):
    # Prepare and launch the RESTful application
    app.prepare_address(ip, port)
    app.run()
