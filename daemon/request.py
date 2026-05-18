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
daemon.request
~~~~~~~~~~~~~~~~~

This module provides a Request object to manage and persist 
request settings (cookies, auth, proxies).
"""
from urllib.parse import parse_qs
from urllib.parse import unquote

from .dictionary import CaseInsensitiveDict

class Request():
    """The fully mutable "class" `Request <Request>` object,
    containing the exact bytes that will be sent to the server.

    Instances are generated from a "class" `Request <Request>` object, and
    should not be instantiated manually; doing so may produce undesirable
    effects.

    Usage::

      >>> import deamon.request
      >>> req = request.Request()
      ## Incoming message obtain aka. incoming_msg
      >>> r = req.prepare(incoming_msg)
      >>> r
      <Request>
    """
    __attrs__ = [
        "method",
        "url",
        "headers",
        "body",
        "_raw_headers",
        "_raw_body",
        "reason",
        "cookies",
        "body",
        "routes",
        "hook",
    ]

    def __init__(self):
        #: HTTP verb to send to the server.
        self.method = None
        #: HTTP URL to send the request to.
        self.url = None
        #: dictionary of HTTP headers.
        self.headers = CaseInsensitiveDict()
        #: HTTP path
        self.path = None        
        # The cookies set used to create Cookie header
        self.cookies = None
        #: request body to send to the server.
        self.body = None
        # The raw header
        self._raw_headers = None
        #: The raw body
        self._raw_body = None
        #: Routes
        self.routes = {}
        #: Hook point for routed mapped-path
        self.hook = None
        self.query = {}

    def extract_request_line(self, request):
        try:
            lines = request.splitlines()
            if not lines:
                return None, None, None
            first_line = lines[0].strip()
            method, path, version = first_line.split()

            if path == '/':
                path = '/index.html'
            elif path == '/favicon.ico':
                path = '/images/favicon.ico'
        except Exception:
            return None, None, None

        return method.upper(), unquote(path), version
             
    def prepare_headers(self, request):
        """Prepares the given HTTP headers."""
        lines = request.split('\r\n')
        headers = CaseInsensitiveDict()
        for line in lines[1:]:
            if ':' in line:
                key, val = line.split(':', 1)
                headers[key.strip()] = val.strip()
        return headers

    def fetch_headers_body(self, request):
        """Prepares the given HTTP headers."""
        # Split request into header section and body section
        parts = request.split("\r\n\r\n", 1)  # split once at blank line

        _headers = parts[0]
        _body = parts[1] if len(parts) > 1 else ""
        return _headers, _body

    def prepare(self, request, routes=None):
        """Prepares the entire request with the given parameters."""

        # Prepare the request line from the request header
        print("[Request] prepare request missg {}".format(request))
        self.method, self.path, self.version = self.extract_request_line(request)
        print("[Request] {} path {} version {}".format(self.method, self.path, self.version))
        if self.method is None:
            return

        self._raw_headers, self._raw_body = self.fetch_headers_body(request)
        self.headers = self.prepare_headers(self._raw_headers)
        self.body = self._raw_body
        self.cookies = {}

        if self.path and "?" in self.path:
            self.path, query_string = self.path.split("?", 1)
            self.query = parse_qs(query_string)
            self.headers["X-AsynapRous-Query"] = query_string

        if routes:
            self.routes = routes
            print("[Request] Routing METHOD {} path {}".format(self.method, self.path))
            self.hook = routes.get((self.method, self.path))
            if self.hook is None and not self.path.endswith("/"):
                self.hook = routes.get((self.method, self.path + "/"))
            if self.hook is None and self.path.endswith("/") and self.path != "/":
                self.hook = routes.get((self.method, self.path.rstrip("/")))
            print("[Request] Hook has request {}".format(request))

        cookies = self.headers.get('Cookie', '')
        for pair in cookies.split(";"):
            if "=" in pair:
                key, value = pair.strip().split("=", 1)
                self.cookies[key] = value

        return

    def prepare_body(self, data, files, json=None):
        if json is not None:
            import json as jsonlib
            self.body = jsonlib.dumps(json)
        else:
            self.body = data or ""
        self.prepare_content_length(self.body)
        return


    def prepare_content_length(self, body):
        length = len(body) if body else 0
        self.headers["Content-Length"] = str(length)
        return


    def prepare_auth(self, auth, url=""):
        if auth:
            self.headers["Authorization"] = auth
        return

    def prepare_cookies(self, cookies):
        self.headers["Cookie"] = cookies
