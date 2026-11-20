"""One HTTP exchange with a synthetic loopback destination; no retries or redirects."""

from dataclasses import dataclass
from http.client import HTTPConnection, HTTPException

from .canonical import MAX_INPUT_BYTES, ValidationError, integer


@dataclass(frozen=True)
class Endpoint:
    port: int
    host: str = "127.0.0.1"

    def __post_init__(self):
        integer(self.port, "port", minimum=1)
        if self.port > 65535 or self.host != "127.0.0.1":
            raise ValidationError("Only a synthetic loopback endpoint is supported")


@dataclass(frozen=True)
class Reply:
    status: int | None
    body: bytes
    provider_id: str | None = None
    error: str | None = None


def exchange(
    endpoint: Endpoint,
    method: str,
    path: str,
    headers: tuple[tuple[str, str], ...],
    body: bytes = b"",
) -> Reply:
    connection = HTTPConnection(endpoint.host, endpoint.port, timeout=3)
    try:
        connection.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
        for name, value in headers:
            connection.putheader(name, value)
        connection.endheaders(body)
        response = connection.getresponse()
        lengths = response.headers.get_all("Content-Length", [])
        types = response.headers.get_all("Content-Type", [])
        identities = response.headers.get_all("X-WS-Provider-ID", [])
        if (
            len(lengths) != 1
            or not lengths[0].isascii()
            or not lengths[0].isdecimal()
            or int(lengths[0]) > MAX_INPUT_BYTES
            or types != ["application/json"]
            or len(identities) != 1
            or len(identities[0]) != 32
            or response.headers.get("Transfer-Encoding") is not None
        ):
            return Reply(response.status, b"", error="invalid_response_headers")
        payload = response.read(MAX_INPUT_BYTES + 1)
        if len(payload) != int(lengths[0]):
            return Reply(response.status, payload[:MAX_INPUT_BYTES], error="invalid_response_size")
        return Reply(response.status, payload, identities[0])
    except (OSError, HTTPException):
        return Reply(None, b"", error="transport_unavailable")
    finally:
        connection.close()


def read(endpoint: Endpoint, path: str, provider_id: str | None = None) -> Reply:
    headers = (("Host", f"{endpoint.host}:{endpoint.port}"), ("Content-Length", "0"))
    if provider_id is not None:
        headers = (*headers, ("X-WS-Provider-ID", provider_id))
    return exchange(endpoint, "GET", path, headers)
