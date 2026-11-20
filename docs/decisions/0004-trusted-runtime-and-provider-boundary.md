# ADR 0004: Trusted runtime and an independent provider

Status: accepted.

## Decision

Use trusted application code and one built-in synthetic capability first. No model-generated executable code or general plugin runner is supported. Typed proposals and provider responses remain data, never self-issued authority.

The [simulator](../../src/work_steward/simulator/server.py) runs over loopback HTTP with its own process and database. The [tests](../../tests/test_simulator.py) exercise independent termination, restart, delayed delivery, and response loss. Clock/completion controls and the hidden oracle belong only to the harness; controllers must use the public protocol.

## Rationale and limits

An in-process fake cannot establish independent failure durability. A real provider introduces side effects and undocumented guarantees before the local protocol is proven. Shared OS-user permissions make the simulator split a failure boundary, not a security sandbox. Dispatch must bind destination/account and reject proxy, redirect, credential, or material-field transformations. See the [threat model](../threat-model.md).
