import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from work_steward.canonical import MAX_INPUT_BYTES, ValidationError
from work_steward.transport import Endpoint, exchange


@contextmanager
def reply_server(*, headers=(), status=200, body=b"{}"):
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            calls.append(self.path)
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            self.send_response(status)
            for name, value in headers:
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        worker = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
        worker.start()
        try:
            yield Endpoint(server.server_port), calls
        finally:
            server.shutdown()
            worker.join(timeout=5)


HEADERS = (
    ("Content-Type", "application/json"),
    ("Content-Length", "2"),
    ("X-WS-Provider-ID", "a" * 32),
)


@pytest.mark.parametrize(
    "headers",
    [
        (),
        (*HEADERS, ("Content-Length", "2")),
        (("Content-Length", str(MAX_INPUT_BYTES + 1)),),
        (*HEADERS, ("Transfer-Encoding", "chunked")),
    ],
)
def test_response_framing_is_bounded_and_unambiguous(headers):
    with reply_server(headers=headers) as (endpoint, calls):
        reply = exchange(endpoint, "POST", "/v1/effects", (("Content-Length", "0"),))
        assert reply.error == "invalid_response_headers"
        assert calls == ["/v1/effects"]


def test_truncated_response_is_not_a_receipt():
    headers = (HEADERS[0], ("Content-Length", "5"), HEADERS[2])
    with reply_server(headers=headers) as (endpoint, _):
        reply = exchange(endpoint, "POST", "/v1/effects", ())
        assert reply.error == "invalid_response_size" and reply.body == b"{}"


def test_redirects_and_environment_proxies_do_not_change_the_destination(monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    with reply_server(
        headers=(*HEADERS, ("Location", "http://example.invalid/effect")), status=302
    ) as (endpoint, calls):
        reply = exchange(endpoint, "POST", "/original", ())
        assert reply.status == 302 and reply.error is None
        assert calls == ["/original"]


@pytest.mark.parametrize(
    "port,host", [(65536, "127.0.0.1"), (1234, "example.com"), (True, "127.0.0.1")]
)
def test_only_explicit_loopback_destinations_are_supported(port, host):
    with pytest.raises(ValidationError):
        Endpoint(port, host)
