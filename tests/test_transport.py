import threading
from contextlib import contextmanager
from email.message import Message
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import Mock

import pytest

from work_steward.canonical import MAX_INPUT_BYTES, ValidationError
from work_steward.transport import Endpoint, Reply, exchange


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
        (HEADERS[0], ("Content-Length", str(MAX_INPUT_BYTES + 1)), HEADERS[2]),
        (*HEADERS, ("Transfer-Encoding", "chunked")),
        (HEADERS[0], ("Content-Length", "9" * 5000), HEADERS[2]),
        (HEADERS[0], ("Content-Length", "0" * 5000), HEADERS[2]),
        (HEADERS[0], ("Content-Length", "-1"), HEADERS[2]),
        (HEADERS[0], ("Content-Length", "nan"), HEADERS[2]),
        (HEADERS[0], ("Content-Length", "\u00b2"), HEADERS[2]),
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
        assert reply.provider_id == "a" * 32


def test_response_at_the_size_limit_is_preserved():
    body = b" " * (MAX_INPUT_BYTES - 2) + b"{}"
    headers = (HEADERS[0], ("Content-Length", str(MAX_INPUT_BYTES)), HEADERS[2])
    with reply_server(headers=headers, body=body) as (endpoint, calls):
        reply = exchange(endpoint, "POST", "/v1/effects", ())
        assert reply.error is None and reply.body == body
        assert reply.provider_id == "a" * 32
        assert calls == ["/v1/effects"]


def test_body_read_failure_retains_received_status_and_identity(monkeypatch):
    from work_steward import transport

    headers = Message()
    for name, value in HEADERS:
        headers[name] = value
    response = Mock(status=200, headers=headers)
    response.read.side_effect = TimeoutError("body timed out")
    connection = Mock()
    connection.getresponse.return_value = response
    monkeypatch.setattr(transport, "HTTPConnection", lambda *_, **__: connection)
    assert exchange(Endpoint(12345), "POST", "/v1/effects", ()) == Reply(
        200, b"", "a" * 32, "transport_unavailable"
    )
    connection.close.assert_called_once()


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
