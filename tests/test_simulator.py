import json
import socket
import sqlite3
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection, HTTPResponse, RemoteDisconnected
from urllib.parse import urlencode

import pytest
from conftest import read_line
from hypothesis import given, settings
from hypothesis import strategies as st

from work_steward.canonical import MAX_INPUT_BYTES, MAX_INTEGER, canonical_bytes
from work_steward.model import (
    Action,
    Disposition,
    Effect,
    Idempotency,
    Observation,
    TransitionError,
)
from work_steward.simulator.store import Behavior, ProviderConflict, ProviderStore


def test_permanent_key_survives_forced_provider_restart(provider):
    with provider() as p:
        status, record = p.submit()
        assert status == 200 and record["outcome"] == "effect_confirmed"
        database = p.database
        p.process.kill()
        p.process.wait(timeout=5)
    with provider(database=database) as restarted:
        status, cached = restarted.submit(attempt="attempt-2")
        assert status == 200 and cached == record
        assert restarted.oracle() == (1, 1)


def test_effect_survives_loss_of_response_and_client_termination(provider, tmp_path):
    # The provider commits before disconnecting; the client never receives a receipt.
    script = """
import http.client, json, sys
c = http.client.HTTPConnection('127.0.0.1', int(sys.argv[1]), timeout=3)
b = json.dumps(dict(operation_id='op-1', account='account-1', resource='resource-1',
                    quantity=1, resource_version=None))
c.request('POST', '/v1/effects', b, {'Content-Type':'application/json',
          'X-WS-Attempt-ID':'attempt-1','Idempotency-Key':'key-1'})
try:
    c.getresponse()
    raise AssertionError('A dropped response unexpectedly arrived')
except http.client.RemoteDisconnected:
    print('response-lost', flush=True)
sys.stdin.readline()
"""
    with provider(behavior="drop_after_apply") as p:
        client = subprocess.Popen(
            [sys.executable, "-c", script, str(p.port)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )
        try:
            assert read_line(client).strip() == "response-lost"
            client.kill()
            client.wait(timeout=5)
            assert p.process.poll() is None
            assert p.oracle() == (1, 1)
            assert p.lookup()[1]["records"][0]["outcome"] == "effect_confirmed"
            with pytest.raises(RemoteDisconnected):
                p.submit(attempt="attempt-2")
            assert p.oracle() == (1, 1)
        finally:
            if client.poll() is None:
                client.kill()
                client.wait(timeout=5)
            client.stdin.close()
            client.stdout.close()


def test_absent_lookup_does_not_rule_out_a_delayed_old_sender(provider, intent):
    script = """
import http.client, json, sys
print('before-send', flush=True)
sys.stdin.readline()
c = http.client.HTTPConnection('127.0.0.1', int(sys.argv[1]), timeout=3)
b = json.dumps(dict(operation_id='op-1', account='account-1', resource='resource-1',
                    quantity=1, resource_version=None))
c.request('POST','/v1/effects',b,{'Content-Type':'application/json',
          'X-WS-Attempt-ID':'attempt-1'})
print(c.getresponse().read().decode(), flush=True)
"""
    # This is a reference-model/transport scenario, not a durable engine-crash test.
    action = Action(intent, "unused").evaluate()
    action = action.admit("attempt-1", expected_version=action.version, generation=0)
    action = action.cross_send_boundary("attempt-1", expected_version=action.version, generation=0)
    with provider(profile="none") as p:
        client = subprocess.Popen(
            [sys.executable, "-c", script, str(p.port)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )
        try:
            assert read_line(client).strip() == "before-send"
            action = action.takeover()
            absent = p.lookup()[1]
            assert absent["records"] == [] and absent["final_absence"] is False
            with pytest.raises(TransitionError):
                action.admit(
                    "attempt-2", expected_version=action.version, generation=action.generation
                )
            client.stdin.write("release\n")
            client.stdin.flush()
            receipt = json.loads(read_line(client))
            client.wait(timeout=5)
            assert client.returncode == 0 and p.oracle() == (1, 1)
            late = Observation(
                "late-1",
                "attempt-1",
                intent.intent_digest,
                Effect.CONFIRMED,
                receipt["provider_effect_id"],
            )
            action = action.observe(late, expected_version=action.version)
            assert action.disposition is Disposition.CLOSED and action.effect is Effect.CONFIRMED
        finally:
            if client.poll() is None:
                client.kill()
                client.wait(timeout=5)
            client.stdin.close()
            client.stdout.close()


def test_permanent_dedup_is_atomic_under_concurrent_requests(provider):
    with provider() as p, ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda i: p.submit(attempt=f"attempt-{i}"), range(12)))
        assert all(status == 200 for status, _ in results)
        assert len({r["provider_effect_id"] for _, r in results}) == 1
        assert p.oracle() == (1, 1)


def test_key_parameter_matching_and_account_scope(provider):
    with provider() as p:
        assert p.submit()[0] == 200
        assert p.submit(quantity=10)[0] == 409
        assert p.oracle() == (1, 1)
        assert p.submit(account="account-2")[0] == 200
        assert p.oracle() == (2, 2)


def test_finite_retention_can_really_duplicate_effects(provider):
    with provider(profile="finite", retention=10) as p:
        assert p.submit()[0] == 200
        control = ProviderStore(p.database, idempotency=Idempotency.FINITE, retention_ticks=10)
        control.advance_clock(9)
        assert p.submit(attempt="attempt-2")[0] == 200
        assert p.oracle() == (1, 1)
        control.advance_clock(1)
        assert p.submit(attempt="attempt-3")[0] == 200
        assert p.oracle() == (2, 2)


def test_operation_id_is_not_a_hidden_provider_uniqueness_key(provider):
    with provider(profile="none") as p:
        assert p.submit(key=None)[0] == 200
        assert p.submit(key=None, attempt="attempt-2")[0] == 200
        assert p.oracle() == (2, 2)
        assert len(p.lookup()[1]["records"]) == 2


def test_c2_condition_is_atomic_under_competing_operations(provider):
    with provider() as p, ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda i: p.submit(
                    operation_id=f"op-{i}",
                    key=f"key-{i}",
                    attempt=f"attempt-{i}",
                    resource_version=0,
                ),
                range(2),
            )
        )
        assert sorted(r["outcome"] for _, r in results) == [
            "effect_confirmed",
            "no_effect_confirmed",
        ]
        assert p.oracle() == (1, 1)


def test_pending_is_not_final_and_condition_is_checked_at_effect_time(provider):
    with provider(behavior="pending") as p:
        assert p.submit(resource_version=0)[1]["outcome"] == "pending"
        assert (
            p.submit(operation_id="op-2", key="key-2", resource_version=0)[1]["outcome"]
            == "pending"
        )
        assert p.oracle() == (0, 0)
        control = ProviderStore(p.database, behavior=Behavior.PENDING)
        control.complete_pending()
        assert p.lookup()[1]["records"][0]["outcome"] == "effect_confirmed"
        assert p.lookup(operation_id="op-2")[1]["records"][0]["outcome"] == "no_effect_confirmed"
        assert p.oracle() == (1, 1)


@pytest.mark.parametrize("behavior", ["reject", "duplicate_status", "contradictory_status"])
def test_declared_fault_profiles_and_readonly_lookup(provider, behavior):
    with provider(behavior=behavior) as p:
        status, post = p.submit()
        assert status == 200
        before = p.oracle()
        first = p.lookup()[1]
        assert first == p.lookup()[1] and p.oracle() == before
        if behavior == "reject":
            assert first["records"][0]["outcome"] == "no_effect_confirmed" and before == (0, 0)
        elif behavior == "duplicate_status":
            assert len(first["records"]) == 2 and first["records"][0] == first["records"][1]
        else:
            assert post["outcome"] == "effect_confirmed"
            assert first["records"][0]["outcome"] == "no_effect_confirmed" and before == (1, 1)


@pytest.mark.parametrize(
    "body",
    [
        b'{"verified":true}',
        b'{"quantity":1,"quantity":2}',
        b"NaN",
        b"{}",
        b'{"operation_id":"op-1","account":"a","resource":"r","quantity":true,"resource_version":null}',
        b'{"operation_id":"op-1","account":"a","resource":"r","quantity":1.0,"resource_version":null}',
    ],
)
def test_malformed_effects_never_mutate_provider_state(provider, body):
    with provider() as p:
        status, _ = p.request(
            "POST",
            "/v1/effects",
            body=body,
            headers={
                "Content-Type": "application/json",
                "X-WS-Attempt-ID": "a1",
                "Idempotency-Key": "key-1",
            },
        )
        assert status == 400 and p.oracle() == (0, 0)


def test_duplicate_headers_overrides_and_control_endpoints_are_denied(provider):
    with provider() as p:
        connection = HTTPConnection(p.host, p.port, timeout=3)
        try:
            connection.putrequest("POST", "/v1/effects")
            connection.putheader("Content-Length", "2")
            connection.putheader("Content-Length", "2")
            connection.endheaders(b"{}")
            assert connection.getresponse().status == 400
        finally:
            connection.close()
        assert p.request("GET", "/__control/advance")[0] == 400
        assert p.request("GET", "/v1/effects?account=a&operation_id=x&extra=y")[0] == 400
        assert p.submit(resource="r", quantity=1, account="a")[0] == 200
        assert p.oracle() == (1, 1)


def test_bounded_lookup_does_not_claim_complete_history(provider):
    with provider(profile="none") as p:
        for i in range(18):
            assert p.submit(attempt=f"a{i}", key=None)[0] == 200
        result = p.lookup()[1]
        assert len(result["records"]) == 16 and result["truncated"] is True
        assert result["final_absence"] is False


@pytest.mark.parametrize("field", ["account", "operation_id"])
@pytest.mark.parametrize("invalid_utf8", ["%FF", "%C3%28"])
def test_lookup_utf8_is_strict_without_rejecting_valid_replacement_characters(
    provider, field, invalid_utf8
):
    with provider() as p:
        assert p.submit(account="\ufffd", operation_id="\ufffd")[0] == 200
        status, valid = p.lookup(account="\ufffd", operation_id="\ufffd")
        assert status == 200 and len(valid["records"]) == 1
        query = urlencode({"account": "\ufffd", "operation_id": "\ufffd"})
        query = query.replace(f"{field}=%EF%BF%BD", f"{field}={invalid_utf8}")
        status, invalid = p.request("GET", "/v1/effects?" + query)
        assert status == 400
        assert invalid == {"error": "invalid_request"}
        assert p.oracle() == (1, 1)


@pytest.mark.parametrize("behavior", ["apply", "duplicate_status"])
def test_lookup_encoded_byte_budget_handles_maximum_unicode_identifiers(provider, behavior):
    identifier = "😀" * 128
    with provider(behavior=behavior) as p:
        record_ids = set()
        for number in range(16):
            status, record = p.submit(
                account=identifier,
                operation_id=identifier,
                resource=identifier,
                attempt="é" * 128,
                key=f"unicode-key-{number}",
            )
            assert status == 200
            record_ids.add(record["provider_effect_id"])
        status, result = p.lookup(account=identifier, operation_id=identifier)
        assert status == 200
        assert 0 < len(result["records"]) <= 32
        assert len(canonical_bytes(result)) <= MAX_INPUT_BYTES
        assert {r["provider_effect_id"] for r in result["records"]} <= record_ids
        assert result["truncated"] is (behavior == "duplicate_status")
        assert result["final_absence"] is False
        assert p.lookup(account=identifier, operation_id=identifier)[1] == result
        assert p.oracle() == (16, 16)


def test_persisted_profile_cannot_silently_change(tmp_path):
    path = tmp_path / "provider.sqlite"
    ProviderStore(path)
    with pytest.raises(ProviderConflict):
        ProviderStore(path, idempotency=Idempotency.NONE)


def test_failed_provider_transaction_rolls_back_applied_effect_and_receipt(provider):
    with provider(profile="finite") as p:
        control = ProviderStore(p.database, idempotency=Idempotency.FINITE)
        control.advance_clock(MAX_INTEGER)
        # Expiry overflow is discovered after the effect write, before transaction commit.
        assert p.submit()[0] == 400
        assert p.oracle() == (0, 0)
        assert p.lookup()[1]["records"] == []


@settings(max_examples=30, deadline=None, derandomize=True, database=None)
@given(
    st.lists(
        st.tuples(st.integers(0, 1), st.integers(0, 3), st.integers(1, 5)), min_size=1, max_size=20
    )
)
def test_generated_permanent_keys_preserve_first_parameters_and_effect_count(commands):
    from pathlib import Path

    with tempfile.TemporaryDirectory() as directory:
        store = ProviderStore(Path(directory) / "provider.sqlite")
        expected = {}
        for index, (account, key, quantity) in enumerate(commands):
            identity = account, key
            body = {
                "operation_id": f"op-{key}",
                "account": f"account-{account}",
                "resource": "resource",
                "quantity": quantity,
                "resource_version": None,
            }
            if identity in expected and expected[identity] != quantity:
                with pytest.raises(ProviderConflict):
                    store.submit(body, attempt_id=f"a{index}", provider_key=f"key-{key}")
            else:
                expected.setdefault(identity, quantity)
                assert (
                    store.submit(body, attempt_id=f"a{index}", provider_key=f"key-{key}")["outcome"]
                    == "effect_confirmed"
                )
        with store.connection() as db:
            assert db.execute("SELECT count(*) FROM effects").fetchone()[0] == len(expected)
            assert db.execute("SELECT sum(quantity) FROM resources").fetchone()[0] == sum(
                expected.values()
            )


def test_simulator_refuses_non_loopback_binding(tmp_path):
    from work_steward.simulator.server import ProviderServer

    with pytest.raises(ValueError):
        # Negative test: the simulator must reject all-interface binding.
        ProviderServer(("0.0.0.0", 0), ProviderStore(tmp_path / "provider.sqlite"))  # noqa: S104


@pytest.mark.parametrize(
    "method,path,body,headers",
    [
        ("GET", "http://example.com/v1/effects", None, {}),
        ("GET", "/v1/effects?account=a", None, {}),
        ("GET", "/v1/effects?account=a&operation_id=x", b"x", {}),
        ("GET", "/v1/effects?account=a&operation_id=x", None, {"Host": "other"}),
        ("POST", "/v1/effects?override=x", b"{}", {"Content-Type": "application/json"}),
        ("POST", "/v1/effects", b"{}", {"Content-Type": "text/plain"}),
        ("POST", "/v1/effects", b"{}", {"Content-Type": "application/json", "Content-Length": "0"}),
    ],
)
def test_protocol_rejects_material_overrides_and_invalid_framing(
    provider, method, path, body, headers
):
    with provider() as p:
        assert p.request(method, path, body=body, headers=headers)[0] == 400
        assert p.oracle() == (0, 0)


def test_truncated_request_is_rejected_without_an_effect(provider):
    with provider() as p, socket.create_connection((p.host, p.port), timeout=3) as connection:
        connection.sendall(
            (
                f"POST /v1/effects HTTP/1.1\r\nHost: {p.host}:{p.port}\r\n"
                "Content-Type: application/json\r\nContent-Length: 10\r\n\r\n{}"
            ).encode()
        )
        connection.shutdown(socket.SHUT_WR)
        response = HTTPResponse(connection)
        response.begin()
        assert response.status == 400
        response.read()
        response.close()
        assert p.oracle() == (0, 0)


def test_provider_storage_failure_returns_503_and_rolls_back_effects(provider):
    with provider() as p:
        with sqlite3.connect(p.database) as db:
            db.execute("DROP TABLE effects")
        assert p.submit()[0] == 503
        assert p.lookup()[0] == 503
        with sqlite3.connect(p.database) as db:
            assert db.execute("SELECT count(*) FROM resources").fetchone()[0] == 0


def test_provider_rejects_invalid_profile_and_quantity_overflow(tmp_path):
    from work_steward.canonical import ValidationError

    path = tmp_path / "provider.sqlite"
    with pytest.raises(ValidationError):
        ProviderStore(path, idempotency="permanent")
    store = ProviderStore(path)
    body = {
        "operation_id": "op",
        "account": "a",
        "resource": "r",
        "quantity": MAX_INTEGER,
        "resource_version": None,
    }
    assert store.submit(body, attempt_id="a1", provider_key="key1")["outcome"] == "effect_confirmed"
    assert (
        store.submit(body, attempt_id="a2", provider_key="key2")["outcome"] == "no_effect_confirmed"
    )
    unkeyed = ProviderStore(tmp_path / "unkeyed.sqlite", idempotency=Idempotency.NONE)
    with pytest.raises(ValidationError):
        unkeyed.submit(body, attempt_id="a1", provider_key="unexpected")
