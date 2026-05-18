#
# Copyright (C) 2026 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course.
#
# AsynApRous release
#
# The authors hereby grant to Licensee personal permission to use
# and modify the Licensed Source Code for the sole purpose of studying
# while attending the course
#

"""
daemon.response
~~~~~~~~~~~~~~~~~

This module provides a :class: `Response <Response>` object to manage and persist 
response settings (cookies, auth, proxies), and to construct HTTP responses
based on incoming requests. 

The current version supports MIME type detection, content loading and header formatting
"""
import datetime
import os
import mimetypes
import json
from .dictionary import CaseInsensitiveDict

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

STATUS_REASONS = {
    200: "OK",
    201: "Created",
    202: "Accepted",
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    408: "Request Timeout",
    500: "Internal Server Error",
}

class Response():   
    """The :class:`Response <Response>` object, which contains a
    server's response to an HTTP request.

    Instances are generated from a :class:`Request <Request>` object, and
    should not be instantiated manually; doing so may produce undesirable
    effects.

    :class:`Response <Response>` object encapsulates headers, content, 
    status code, cookies, and metadata related to the request-response cycle.
    It is used to construct and serve HTTP responses in a custom web server.

    :attrs status_code (int): HTTP status code (e.g., 200, 404).
    :attrs headers (dict): dictionary of response headers.
    :attrs url (str): url of the response.
    :attrsencoding (str): encoding used for decoding response content.
    :attrs history (list): list of previous Response objects (for redirects).
    :attrs reason (str): textual reason for the status code (e.g., "OK", "Not Found").
    :attrs cookies (CaseInsensitiveDict): response cookies.
    :attrs elapsed (datetime.timedelta): time taken to complete the request.
    :attrs request (PreparedRequest): the original request object.

    Usage::

      >>> import Response
      >>> resp = Response()
      >>> resp.build_response(req)
      >>> resp
      <Response>
    """

    __attrs__ = [
        "_content",
        "_header",
        "status_code",
        "method",
        "headers",
        "url",
        "history",
        "encoding",
        "reason",
        "cookies",
        "elapsed",
        "request",
        "body",
        "reason",
    ]


    def __init__(self, request=None):
        """
        Initializes a new :class:`Response <Response>` object.

        : params request : The originating request object.
        """

        self._content = False
        self._content_consumed = False
        self._next = None

        #: Integer Code of responded HTTP Status, e.g. 404 or 200.
        self.status_code = None

        #: Case-insensitive Dictionary of Response Headers.
        #: For example, ``headers['content-type']`` will return the
        #: value of a ``'Content-Type'`` response header.
        self.headers = {}

        #: URL location of Response.
        self.url = None

        #: Encoding to decode with when accessing response text.
        self.encoding = None

        #: A list of :class:`Response <Response>` objects from
        #: the history of the Request.
        self.history = []

        #: Textual reason of responded HTTP Status, e.g. "Not Found" or "OK".
        self.reason = None

        #: A of Cookies the response headers.
        self.cookies = CaseInsensitiveDict()

        #: The amount of time elapsed between sending the request
        self.elapsed = datetime.timedelta(0)

        #: The :class:`PreparedRequest <PreparedRequest>` object to which this
        #: is a response.
        self.request = None

    def make_response(self, content=b"", status_code=200, content_type="text/plain",
                      headers=None):
        """Build a complete HTTP response from bytes or text content."""
        if isinstance(content, (dict, list)):
            content = json.dumps(content).encode("utf-8")
            content_type = "application/json"
        elif isinstance(content, str):
            content = content.encode("utf-8")

        reason = STATUS_REASONS.get(status_code, "OK")
        response_headers = {
            "Date": datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT"),
            "Server": "AsynapRous/1.0",
            "Content-Type": content_type,
            "Content-Length": str(len(content)),
            "Connection": "close",
        }
        if headers:
            response_headers.update(headers)

        header_lines = ["HTTP/1.1 {} {}".format(status_code, reason)]
        header_lines.extend(
            "{}: {}".format(key, value) for key, value in response_headers.items()
        )
        return ("\r\n".join(header_lines) + "\r\n\r\n").encode("utf-8") + content


    def get_mime_type(self, path):
        """
        Determines the MIME type of a file based on its path.

        "params path (str): Path to the file.

        :rtype str: MIME type string (e.g., 'text/html', 'image/png').
        """

        try:
            mime_type, _ = mimetypes.guess_type(path)
        except Exception:
            return 'application/octet-stream'
        return mime_type or 'application/octet-stream'


    def prepare_content_type(self, mime_type='text/html'):
        """
        Prepares the Content-Type header and determines the base directory
        for serving the file based on its MIME type.

        :params mime_type (str): MIME type of the requested resource.

        :rtype str: Base directory path for locating the resource.

        :raises ValueError: If the MIME type is unsupported.
        """
        
        base_dir = ""

        # Validate header attr existence
        if not hasattr(self, "headers") or self.headers is None:
            self.headers = {}

        main_type, sub_type = mime_type.split('/', 1)
        print("[Response] Processing main_type={} sub_type={}".format(main_type,sub_type))
        if main_type == 'text':
            self.headers['Content-Type']='text/{}'.format(sub_type)
            if sub_type == 'plain' or sub_type == 'css':
                base_dir = os.path.join(BASE_DIR, "static")
            elif sub_type == 'html':
                base_dir = os.path.join(BASE_DIR, "www")
            else:
                base_dir = os.path.join(BASE_DIR, "static")
        elif main_type == 'image':
            base_dir = os.path.join(BASE_DIR, "static")
            self.headers['Content-Type']='image/{}'.format(sub_type)
        elif main_type == 'application':
            base_dir = os.path.join(BASE_DIR, "static")
            self.headers['Content-Type']='application/{}'.format(sub_type)
        else:
            raise ValueError("Invalid MEME type: main_type={} sub_type={}".format(main_type,sub_type))

        return base_dir


    def build_content(self, path, base_dir):
        """
        Loads the objects file from storage space.

        :params path (str): relative path to the file.
        :params base_dir (str): base directory where the file is located.

        :rtype tuple: (int, bytes) representing content length and content data.
        """

        requested = path.lstrip('/')
        filepath = os.path.abspath(os.path.join(base_dir, requested))
        allowed_root = os.path.abspath(base_dir)

        if not filepath.startswith(allowed_root + os.sep):
            print("[Response] blocked path traversal {}".format(path))
            return -1, b""

        print("[Response] Serving the object at location {}".format(filepath))
        try:
            with open(filepath, "rb") as f:
               content = f.read()
        except Exception as e:
            print("[Response] build_content exception: {}".format(e))
            return -1, b""
        return len(content), content


    def build_response_header(self, request):
        """
        Constructs the HTTP response headers based on the class:`Request <Request>
        and internal attributes.

        :params request (class:`Request <Request>`): incoming request object.

        :rtypes bytes: encoded HTTP response header.
        """
        headers = {
                "Cache-Control": "no-cache",
                "Content-Type": "{}".format(self.headers['Content-Type']),
                "Content-Length": "{}".format(len(self._content)),
                "Date": "{}".format(datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")),
                "Server": "AsynapRous/1.0",
            }

        lines = ["HTTP/1.1 200 OK"]
        for key, value in headers.items():
            lines.append("{}: {}".format(key, value))
        lines.append("Connection: close")
        return ("\r\n".join(lines) + "\r\n\r\n").encode('utf-8')


    def build_notfound(self):
        """
        Constructs a standard 404 Not Found HTTP response.

        :rtype bytes: Encoded 404 response.
        """

        return self.make_response("404 Not Found", 404, "text/plain")

    def build_unauthorized(self, message="Unauthorized"):
        return self.make_response(
            message,
            401,
            "text/plain",
            {"WWW-Authenticate": 'Basic realm="AsynapRous"'},
        )


    def build_response(self, request, envelop_content=None):
        """
        Builds a full HTTP response including headers and content based on the request.

        :params request (class:`Request <Request>`): incoming request object.

        :rtype bytes: complete HTTP response using prepared headers and content.
        """
        print("[Response] Start build response with req {}".format(request))

        if request.method is None or request.path is None:
            return self.make_response("400 Bad Request", 400, "text/plain")

        if request.hook:
            return self.build_app_response(request)

        path = request.path

        mime_type = self.get_mime_type(path)
        print("[Response] {} path {} mime_type {}".format(request.method, request.path, mime_type))

        base_dir = ""

        #If HTML, parse and serve embedded objects
        if path.endswith('.html') or mime_type == 'text/html':
            base_dir = self.prepare_content_type(mime_type = 'text/html')
        elif mime_type == 'text/css':
            base_dir = self.prepare_content_type(mime_type = 'text/css')
        elif mime_type.startswith('image/'):
            base_dir = self.prepare_content_type(mime_type=mime_type)
        elif mime_type in ('application/javascript', 'text/javascript'):
            base_dir = self.prepare_content_type(mime_type='application/javascript')
        elif mime_type == 'application/json':
            base_dir = self.prepare_content_type(mime_type=mime_type)
        elif mime_type == 'application/octet-stream':
            base_dir = self.prepare_content_type(mime_type='application/octet-stream')
        else:
            return self.build_notfound()

        length, content = self.build_content(path, base_dir)
        if length < 0:
            return self.build_notfound()

        self._content = content
        self._header = self.build_response_header(request)
        if request.method == "HEAD":
            return self._header
        return self._header + self._content

    async def build_response_async(self, request, envelop_content=None):
        """
        Async variant used by the coroutine backend.

        It awaits REST hooks directly instead of calling asyncio.run() inside an
        already-running event loop.
        """
        if request.method is None or request.path is None:
            return self.make_response("400 Bad Request", 400, "text/plain")

        if request.hook:
            return await self.build_app_response_async(request)

        return self.build_response(request, envelop_content)

    def build_app_response(self, request):
        """Invoke a routed webapp hook and wrap its return value in HTTP."""
        try:
            result = request.hook(request.headers, request.body)
            if hasattr(result, "__await__"):
                import asyncio
                result = asyncio.run(result)
        except Exception as exc:
            print("[Response] app hook exception: {}".format(exc))
            return self.make_response(
                {"error": "Internal Server Error", "detail": str(exc)},
                500,
                "application/json",
            )

        headers = {}
        status_code = 200
        content_type = "application/json"
        content = result

        if isinstance(result, tuple):
            content = result[0]
            if len(result) > 1 and result[1] is not None:
                status_code = result[1]
            if len(result) > 2 and result[2] is not None:
                headers = result[2]

        if isinstance(content, bytes):
            payload = content
        elif isinstance(content, (dict, list)):
            payload = json.dumps(content).encode("utf-8")
        else:
            payload = str(content).encode("utf-8")
            if content_type == "application/json":
                content_type = "text/plain"

        return self.make_response(payload, status_code, content_type, headers)

    async def build_app_response_async(self, request):
        """Invoke a routed webapp hook from an asyncio server."""
        try:
            result = request.hook(request.headers, request.body)
            if hasattr(result, "__await__"):
                result = await result
        except Exception as exc:
            print("[Response] app hook exception: {}".format(exc))
            return self.make_response(
                {"error": "Internal Server Error", "detail": str(exc)},
                500,
                "application/json",
            )

        headers = {}
        status_code = 200
        content_type = "application/json"
        content = result

        if isinstance(result, tuple):
            content = result[0]
            if len(result) > 1 and result[1] is not None:
                status_code = result[1]
            if len(result) > 2 and result[2] is not None:
                headers = result[2]

        if isinstance(content, bytes):
            payload = content
        elif isinstance(content, (dict, list)):
            payload = json.dumps(content).encode("utf-8")
        else:
            payload = str(content).encode("utf-8")
            if content_type == "application/json":
                content_type = "text/plain"

        return self.make_response(payload, status_code, content_type, headers)
