# ADR 0005: Canonical intent and exact dispatch binding

Status: accepted; dispatch mapping pending.

## Decision

Validate a closed typed intent before [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785) canonicalization. [intent.py](../../src/work_steward/intent.py) and [canonical.py](../../src/work_steward/canonical.py) define the schema, bounds, and domain-separated hashes; [tests](../../tests/test_intent.py) contain golden vectors and rejection cases.

The trusted adapter must separately bind the exact request to stored intent: account, destination, method/path/query, effect-bearing body/headers, preconditions, stable provider key, and approved adapter artifact. Persist exact body bytes and dispatch metadata alongside their digest. Validate material mapping independently of the adapter's own output. A new adapter or changed evidence cannot silently reinterpret old intent.

## Rationale

A body-only hash or natural-language approval omits material authority. Canonical serialization does not itself validate business meaning or provide isolation. Hashing the adapter does not make its interpreter, dependencies, transport, or signer untrusted. Real connectors need their own wire, credential-account, and provider-semantics review.
