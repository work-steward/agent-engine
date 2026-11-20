"""Independent simulator process owned by the local demo harness."""

import json
import selectors
import subprocess
import sys
from pathlib import Path


class Warehouse:
    def __init__(self, directory: Path, *, port=0, profile="permanent", behavior="apply"):
        self.directory = directory
        self.port, self.profile, self.behavior = port, profile, behavior
        self.process = None
        self.log = None

    def start(self):
        self.log = (self.directory / "warehouse.log").open("a+")
        try:
            # Fixed interpreter/module, no shell; the directory is a data argument.
            self.process = subprocess.Popen(  # noqa: S603
                [
                    sys.executable,
                    "-m",
                    "work_steward.simulator.server",
                    "--database",
                    str(self.directory / "warehouse.sqlite"),
                    "--port",
                    str(self.port),
                    "--profile",
                    self.profile,
                    "--behavior",
                    self.behavior,
                ],
                stdout=subprocess.PIPE,
                stderr=self.log,
                text=True,
            )
            with selectors.DefaultSelector() as selector:
                selector.register(self.process.stdout, selectors.EVENT_READ)
                if not selector.select(timeout=10):
                    raise RuntimeError("Warehouse startup timed out")
                line = self.process.stdout.readline()
            if not line:
                raise RuntimeError("Warehouse failed to start; see warehouse.log")
            self.port = json.loads(line)["port"]
            return self
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
            self.process.stdout.close()
            self.process = None
        if self.log is not None:
            self.log.close()
            self.log = None

    def __enter__(self):
        return self.start()

    def __exit__(self, *_):
        self.close()
