import json
import multiprocessing
import selectors
import sqlite3
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from http.client import HTTPConnection
from pathlib import Path
from urllib.parse import urlencode

import pytest

from work_steward.intent import Consistency, Intent


@pytest.fixture
def intent():
    return Intent(
        organization_id="org-1",
        execution_id="exec-1",
        node_instance_id="node-1",
        operation_id="op-1",
        business_effect_namespace="sim.resource",
        business_effect_key="event-1",
        account="account-1",
        resource="resource-1",
        quantity=1,
        resource_version=None,
        consistency=Consistency.C0,
        adapter_id="simulator-1",
        adapter_digest="a" * 64,
    )


def read_line(process: subprocess.Popen) -> str:
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        if not selector.select(timeout=10):
            raise AssertionError("Subprocess did not reach its deterministic readiness barrier")
        line = process.stdout.readline()
    if not line:
        raise AssertionError(f"Subprocess exited before readiness: {process.poll()}")
    return line


@dataclass
class RunningProvider:
    process: subprocess.Popen
    database: Path
    host: str
    port: int

    def request(self, method, path, *, body=None, headers=None):
        connection = HTTPConnection(self.host, self.port, timeout=3)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def submit(self, *, attempt="attempt-1", key="key-1", **changes):
        body = {
            "operation_id": "op-1",
            "account": "account-1",
            "resource": "resource-1",
            "quantity": 1,
            "resource_version": None,
            **changes,
        }
        headers = {"Content-Type": "application/json", "X-WS-Attempt-ID": attempt}
        if key is not None:
            headers["Idempotency-Key"] = key
        return self.request("POST", "/v1/effects", body=json.dumps(body).encode(), headers=headers)

    def lookup(self, **changes):
        query = urlencode({"account": "account-1", "operation_id": "op-1", **changes})
        return self.request("GET", "/v1/effects?" + query)

    def oracle(self):
        # Harness-only observation. The controller's HTTP protocol never exposes this connection.
        with sqlite3.connect(f"file:{self.database}?mode=ro", uri=True) as db:
            count = db.execute(
                "SELECT count(*) FROM effects WHERE outcome='effect_confirmed'"
            ).fetchone()[0]
            total = db.execute("SELECT coalesce(sum(quantity),0) FROM resources").fetchone()[0]
            return count, total


@pytest.fixture
def provider(tmp_path):
    @contextmanager
    def start(*, database=None, profile="permanent", behavior="apply", retention=10):
        path = database or tmp_path / "provider.sqlite"
        with (tmp_path / "provider-stderr.log").open("w+") as error_log:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "work_steward.simulator.server",
                    "--database",
                    str(path),
                    "--profile",
                    profile,
                    "--behavior",
                    behavior,
                    "--retention-ticks",
                    str(retention),
                ],
                stdout=subprocess.PIPE,
                stderr=error_log,
                text=True,
            )
            try:
                address = json.loads(read_line(process))
                yield RunningProvider(process, path, address["host"], address["port"])
            except Exception:
                error_log.seek(0)
                print(error_log.read())
                raise
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                process.stdout.close()

    return start


@contextmanager
def process(target, *arguments):
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    worker = context.Process(target=target, args=(*arguments, child))
    worker.start()
    child.close()
    try:
        yield worker, parent
    finally:
        parent.close()
        if worker.is_alive():
            worker.kill()
        worker.join(timeout=10)
        assert not worker.is_alive()
        worker.close()


def receive(connection):
    assert connection.poll(10), "Worker did not reach its explicit synchronization barrier"
    return connection.recv()
