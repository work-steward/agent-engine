"""Loopback-only synthetic HTTP provider. No harness/oracle control endpoints."""

import argparse
import json
import socket
import sqlite3
from contextlib import suppress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from ..canonical import MAX_INPUT_BYTES, ValidationError, canonical_bytes, parse_json
from ..model import Idempotency
from .store import Behavior, ProviderConflict, ProviderStore


class ProviderServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], store: ProviderStore):
        if address[0] != "127.0.0.1":
            raise ValueError("Simulator must bind to 127.0.0.1")
        self.store = store
        super().__init__(address, ProviderHandler)


class ProviderHandler(BaseHTTPRequestHandler):
    server: ProviderServer

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(2.0)

    def log_message(self, format: str, *args: object) -> None:
        # No request body, target, account, headers, or synthetic credentials in logs.
        pass

    def _reply(self, status: int, value: dict) -> None:
        payload = canonical_bytes(value)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(payload)

    def _validate(self, *, post: bool) -> tuple[dict, str | None]:
        allowed = {
            "host",
            "content-length",
            "content-type",
            "accept",
            "accept-encoding",
            "connection",
            "user-agent",
        }
        if post:
            allowed |= {"x-ws-attempt-id", "idempotency-key"}
        for name in self.headers:
            if name.lower() not in allowed or len(self.headers.get_all(name)) != 1:
                raise ValidationError("Unsupported or duplicate header")
        host, port = self.server.server_address
        if self.headers.get("Host") != f"{host}:{port}":
            raise ValidationError("Destination authority mismatch")
        parsed = urlsplit(self.path)
        if parsed.scheme or parsed.netloc or parsed.fragment or parsed.path != "/v1/effects":
            raise ValidationError("Unsupported request target")
        if post:
            if parsed.query or self.headers.get("Content-Type") != "application/json":
                raise ValidationError("Unsupported query or content type")
            length = self.headers.get("Content-Length", "")
            if (
                not length.isascii()
                or not length.isdecimal()
                or not 0 < int(length) <= MAX_INPUT_BYTES
            ):
                raise ValidationError("Invalid body size")
            data = self.rfile.read(int(length))
            if len(data) != int(length):
                raise ValidationError("Truncated body")
            return parse_json(data), self.headers.get("Idempotency-Key")
        if self.headers.get("Content-Length", "0") != "0":
            raise ValidationError("Lookup body unsupported")
        query = parse_qs(
            parsed.query,
            keep_blank_values=True,
            strict_parsing=True,
            max_num_fields=2,
            encoding="utf-8",
            errors="strict",
        )
        if set(query) != {"account", "operation_id"} or any(len(v) != 1 for v in query.values()):
            raise ValidationError("Unsupported lookup query")
        return {key: values[0] for key, values in query.items()}, None

    def do_POST(self) -> None:
        try:
            body, key = self._validate(post=True)
            result = self.server.store.submit(
                body,
                attempt_id=self.headers.get("X-WS-Attempt-ID"),
                provider_key=key,
            )
            if self.server.store.behavior is Behavior.DROP_AFTER_APPLY:
                self.close_connection = True
                self.connection.shutdown(socket.SHUT_RDWR)
                return
            self._reply(200, result)
        except ProviderConflict:
            self._reply(409, {"error": "idempotency_conflict"})
        except (ValidationError, ValueError, TimeoutError):
            self._reply(400, {"error": "invalid_request"})
        except sqlite3.Error:
            self._reply(503, {"error": "storage_unavailable"})

    def do_GET(self) -> None:
        try:
            query, _ = self._validate(post=False)
            self._reply(200, self.server.store.lookup(**query))
        except (ValidationError, ValueError, TimeoutError):
            self._reply(400, {"error": "invalid_request"})
        except sqlite3.Error:
            self._reply(503, {"error": "storage_unavailable"})


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Synthetic loopback provider; never for real actions"
    )
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--profile", choices=list(Idempotency), default=Idempotency.PERMANENT)
    parser.add_argument("--behavior", choices=list(Behavior), default=Behavior.APPLY)
    parser.add_argument("--retention-ticks", type=int, default=10)
    args = parser.parse_args()
    store = ProviderStore(
        args.database,
        idempotency=Idempotency(args.profile),
        behavior=Behavior(args.behavior),
        retention_ticks=args.retention_ticks,
    )
    with ProviderServer(("127.0.0.1", args.port), store) as server:
        print(json.dumps({"host": "127.0.0.1", "port": server.server_port}), flush=True)
        with suppress(KeyboardInterrupt):
            server.serve_forever()


if __name__ == "__main__":
    main()
