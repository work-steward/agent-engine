# ADR 0001: Python and local SQLite

Status: accepted.

## Decision

Use Python for the reference model and property tests, and SQLite on a local filesystem for the single-node kernel proof. Versions and dependencies live in [.python-version](../../.python-version) and [pyproject.toml](../../pyproject.toml). [Engine storage](../../src/work_steward/ledger.py) and [provider storage](../../src/work_steward/simulator/store.py) use separate databases.

Require STRICT tables, foreign keys, WAL, FULL synchronization, and bounded lock waits. Engine admission, revocation, fencing, reservations, and state/journal updates must serialize through short write transactions with current predicates and conditional version checks. Commit remote-I/O prerequisites first; never hold a database transaction across HTTP. Checkpoints cannot override newer authoritative records.

Bind an engine database to one organization, mode, application identifier, and schema version. Upgrade known v1/v2 databases atomically to v3; reject unknown formats and conversion into governed mode. Persist closed commands, not replacement snapshots. [Governed admission](0007-local-authority.md) and [synthetic dispatch](0008-synthetic-dispatch.md) use these transactions.

## Rationale and consequences

Serialized writes simplify the first proof. PostgreSQL would add a service; multiple backends would multiply conformance obligations before workload justifies them. This choice excludes network filesystems and multi-host access. Busy/storage failures deny new admission. Durability depends on SQLite/VFS/filesystem assumptions, and stale-backup restoration needs a separate recovery protocol.
