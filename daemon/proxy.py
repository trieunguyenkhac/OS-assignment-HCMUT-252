#
# Copyright (C) 2026 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course.
#
# AsynapRous release
#
# The authors hereby grant to Licensee personal permission to use
# and modify the Licensed Source Code for the sole purpose of studying
# while attending the course
#

"""
daemon.proxy
~~~~~~~~~~~~~~~~~

This module implements a simple proxy server using Python's socket and threading libraries.
It routes incoming HTTP requests to backend services based on hostname mappings and returns
the corresponding responses to clients.

Requirement:
-----------------
- socket: provides socket networking interface.
- threading: enables concurrent client handling via threads.
- response: customized :class: `Response <Response>` utilities.
- httpadapter: :class: `HttpAdapter <HttpAdapter >` adapter for HTTP request processing.
- dictionary: :class: `CaseInsensitiveDict <CaseInsensitiveDict>` for managing headers and cookies.

"""
import threading
import itertools
import socket

from .response import Response

#: A dictionary mapping hostnames to backend IP and port tuples.
#: Used to determine routing targets for incoming requests.
PROXY_PASS = {
    "192.168.56.103:8080": ('192.168.56.103', 9000),
    "app1.local": ('192.168.56.103', 9001),
    "app2.local": ('192.168.56.103', 9002),
}

_ROUND_ROBIN = {}


def forward_request(host, port, request):
    """
    Forwards an HTTP request to a backend server and retrieves the response.

    :params host (str): IP address of the backend server.
    :params port (int): port number of the backend server.
    :params request (str): incoming HTTP request.

    :rtype bytes: Raw HTTP response from the backend server. If the connection
                  fails, returns a 404 Not Found response.
    """

    backend = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    backend.settimeout(10)

    try:
        with backend:
            backend.connect((host, port))
            backend.sendall(force_connection_close(request))
            response = b""
            while True:
                chunk = backend.recv(4096)
                if not chunk:
                    break
                response += chunk
            return response
    except socket.error as e:
        print("Socket error: {}".format(e))
        return Response().build_notfound()


def resolve_routing_policy(hostname, routes):
    """
    Handles an routing policy to return the matching proxy_pass.
    It determines the target backend to forward the request to.

    :params host (str): IP address of the request target server.
    :params port (int): port number of the request target server.
    :params routes (dict): dictionary mapping hostnames and location.
    """

    if hostname not in routes:
        return None, None

    proxy_map, policy = routes[hostname]

    proxy_host = ''
    proxy_port = '9000'
    if isinstance(proxy_map, list):
        if len(proxy_map) == 0:
            print("[Proxy] Emtpy resolved routing of hostname {}".format(hostname))
            print("Empty proxy_map result")
            return None, None
        elif len(proxy_map) == 1:
            proxy_host, proxy_port = proxy_map[0].rsplit(":", 1)
        else:
            if policy == "round-robin":
                counter = _ROUND_ROBIN.setdefault(hostname, itertools.count())
                target = proxy_map[next(counter) % len(proxy_map)]
            else:
                target = proxy_map[0]
            proxy_host, proxy_port = target.rsplit(":", 1)
    else:
        print("[Proxy] resolve route of hostname {} is a singulair to".format(hostname))
        proxy_host, proxy_port = proxy_map.rsplit(":", 1)

    return proxy_host, proxy_port

def handle_client(ip, port, conn, addr, routes):
    """
    Handles an individual client connection by parsing the request,
    determining the target backend, and forwarding the request.

    The handler extracts the Host header from the request to
    matches the hostname against known routes. In the matching
    condition,it forwards the request to the appropriate backend.

    The handler sends the backend response back to the client or
    returns 404 if the hostname is unreachable or is not recognized.

    :params ip (str): IP address of the proxy server.
    :params port (int): port number of the proxy server.
    :params conn (socket.socket): client connection socket.
    :params addr (tuple): client address (IP, port).
    :params routes (dict): dictionary mapping hostnames and location.
    """

    request = recv_http_message(conn)
    if not request:
        conn.close()
        return

    request_text = request.decode("iso-8859-1", errors="replace")

    # Extract hostname
    hostname = ""
    for line in request_text.splitlines():
        if line.lower().startswith('host:'):
            hostname = line.split(':', 1)[1].strip()

    print("[Proxy] {} at Host: {}".format(addr, hostname))

    # Resolve the matching destination in routes and need conver port
    # to integer value
    resolved_host, resolved_port = resolve_routing_policy(hostname, routes)
    try:
        resolved_port = int(resolved_port) if resolved_port is not None else None
    except ValueError:
        resolved_host = None
        resolved_port = None

    if resolved_host:
        print("[Proxy] Host name {} is forwarded to {}:{}".format(hostname,resolved_host, resolved_port))
        response = forward_request(resolved_host, resolved_port, request)
    else:
        response = Response().build_notfound()

    try:
        conn.sendall(response)
    finally:
        conn.close()

def run_proxy(ip, port, routes):
    """
    Starts the proxy server and listens for incoming connections. 

    The process dinds the proxy server to the specified IP and port.
    In each incomping connection, it accepts the connections and
    spawns a new thread for each client using `handle_client`.
 

    :params ip (str): IP address to bind the proxy server.
    :params port (int): port number to listen on.
    :params routes (dict): dictionary mapping hostnames and location.

    """

    proxy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    proxy.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        proxy.bind((ip, port))
        proxy.listen(50)
        print("[Proxy] Listening on IP {} port {}".format(ip,port))
        while True:
            conn, addr = proxy.accept()
            conn.settimeout(10)
            client_thread = threading.Thread(
                target=handle_client,
                args=(ip, port, conn, addr, routes),
                daemon=True,
            )
            client_thread.start()
    except socket.error as e:
      print("Socket error: {}".format(e))


def recv_http_message(conn):
    """Read one complete HTTP request before forwarding it."""
    data = b""
    while True:
        try:
            chunk = conn.recv(4096)
        except socket.timeout:
            break

        if not chunk:
            break

        data += chunk
        if b"\r\n\r\n" in data:
            break

    if b"\r\n\r\n" not in data:
        return data

    header, body = data.split(b"\r\n\r\n", 1)
    content_length = 0
    for line in header.decode("iso-8859-1", errors="replace").split("\r\n")[1:]:
        if line.lower().startswith("content-length:"):
            try:
                content_length = int(line.split(":", 1)[1].strip())
            except ValueError:
                content_length = 0
            break

    while len(body) < content_length:
        try:
            chunk = conn.recv(4096)
        except socket.timeout:
            break
        if not chunk:
            break
        body += chunk
    return header + b"\r\n\r\n" + body


def force_connection_close(request):
    """Rewrite forwarded HTTP request headers to avoid keep-alive waits."""
    if b"\r\n\r\n" not in request:
        return request

    header, body = request.split(b"\r\n\r\n", 1)
    lines = header.split(b"\r\n")
    rewritten = []
    saw_connection = False
    for line in lines:
        if line.lower().startswith(b"connection:"):
            rewritten.append(b"Connection: close")
            saw_connection = True
        else:
            rewritten.append(line)

    if not saw_connection:
        rewritten.append(b"Connection: close")

    return b"\r\n".join(rewritten) + b"\r\n\r\n" + body

def create_proxy(ip, port, routes):
    """
    Entry point for launching the proxy server.

    :params ip (str): IP address to bind the proxy server.
    :params port (int): port number to listen on.
    :params routes (dict): dictionary mapping hostnames and location.
    """

    run_proxy(ip, port, routes)
