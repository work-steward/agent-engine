# ADR 0001: Python and SQLite for the kernel proof

- Status: proposed; implementation direction approved by the project lead on 2026-11-19.
- References: D12, D42–44, D60–64, D73, D78, D97–98; AC-01, AC-02, AC-04, AC-07, AC-09, AC-10.
- Product amendments: none. This chooses a first supported topology and storage implementation.

## Context and decision

Use CPython 3.13, standard-library SQLite access, pytest, and Hypothesis. Pin supported patched interpreter, SQLite, and package versions in the implementation environment and lockfile before claiming reproducibility. Python is suited to the state model and property tests; the core correctness contract remains deterministic and independent of model output.

Support one engine instance, one organization per instance, and one authoritative SQLite database on a local filesystem. Require SQLite 3.37 or later for STRICT tables, foreign keys on every connection, WAL journaling, `synchronous=FULL`, and an explicit bounded busy timeout. Verify effective settings rather than trusting defaults. No network filesystems, multi-host database access, or multiple independent engine instances sharing the file.

Use `BEGIN IMMEDIATE` for every transaction that admits an intent/attempt, changes policy or evidence authority, fences a worker, changes a reservation, or mutates authoritative action state. Recheck required predicates after acquiring the write transaction. Reject stale state versions and lease generations with conditional updates; require the expected affected-row count. A writer serializes against competing admissions and revocations. Pure reads must not later authorize a write using an unchecked snapshot.

Co-commit every material state mutation and its append-only journal events, new immutable records, reservations, and per-operation event sequence in the same transaction. Roll back the entire transaction on failure. Journal payloads contain synthetic identifiers and evidence references, not arbitrary raw context or credentials. Remote I/O happens only after the appropriate commit, never inside a database transaction.

Use an explicitly allocated transactional event sequence for authoritative ordering; gaps or wall-clock timestamps are not evidence of a missing effect. Do not use timestamps as fencing tokens. Checkpoints are optional read accelerators and cannot override later committed rows/events. SQLite storage and the trusted controller enforce application-level append-only behavior; this is not host-admin tamper resistance.

## Alternatives and consequences

PostgreSQL is viable but adds a service and deployment burden for a solo-led single-node proof. Select it later only if workload or topology justifies a reviewed migration. Supporting both databases immediately would multiply conformance obligations. Pure in-memory state cannot prove restart recovery. Event sourcing alone would introduce a replay design without eliminating transaction requirements.

Serialized writes trade throughput for simpler admission semantics. Busy timeout or storage failure denies new admission; it never authorizes a retry of a remote action. Disk exhaustion must fail closed. Schema migrations require exclusive engine maintenance, explicit schema versions, and fixtures proving supported upgrades; initial releases may refuse unsupported versions. No automatic action resume after restoring a stale backup.

## Validation and limitations

Designed only. Implementation must test concurrent claims/revocations using separate connections, journal rollback, stale updates, restart after forced process exit, and connection settings. `synchronous=FULL` is a configuration obligation, not proof against failed hardware, dishonest storage, power loss on every platform, or stale backup restoration. These guarantees depend on the documented SQLite/VFS/filesystem assumptions.
