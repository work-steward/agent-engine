# Threat model

## Current boundary

The supported test environment is a trusted host with local SQLite storage and synthetic data. Python, SQLite/VFS, the OS, dependencies, HTTP stack, and application code are trusted. The future kernel starts with one engine instance and one organization per instance.

| Component | Boundary |
| --- | --- |
| Intent input | Closed schema; no free-form destination, credentials, or caller-supplied authorization. |
| Reference reducer | Trusted policy/evidence events; no persistence or actual network authority. |
| Engine ledger | Durable storage of trusted model commands; no caller authentication, policy verification, receipt verification, or transport. |
| Authority controller | Governed-mode policy/approval checks; host-authenticated caller identities, evidence provenance, and clock configuration remain trusted. |
| Provider simulator | Independent process/database with an unauthenticated loopback HTTP interface. |
| Test harness | May control faults and inspect hidden provider state; that oracle must never authorize controller actions. |

The process split tests independent failures. It does not isolate malicious processes running as the same OS user, execute arbitrary untrusted agent code, or establish production secrecy.

## Failures the kernel must handle

Malformed proposals and responses, material request substitution, stale authority/evidence, duplicates, concurrent or stale workers, revocation races, process crashes, lost/delayed responses, delayed request arrival, finite idempotency retention, and contradictory claims are covered by the [conformance obligations](conformance.md).

Fail closed on invalid authority, unsupported consistency, failed transactions, or request mismatch. Preserve possibly sent attempts and business reservations. Reconcile under separate current read authority; do not infer remote failure from local failure or erase an earlier effect during cancellation.

## Exclusions

Malicious host/root administrators, privileged runtime compromise, dishonest storage, provider violations of stated guarantees, arbitrary executable connectors with raw credentials/network access, and stale-backup restoration are outside the initial guarantee. Power-loss durability depends on the selected storage assumptions. A simulated contradiction can trigger escalation; it cannot establish independent truth about a dishonest provider.

There is no model integration, general prompt-injection immunity, arbitrary-code sandbox, production credential broker, encrypted context store, or real connector in the current package. Those require separate designs and adversarial tests before support is claimed.
