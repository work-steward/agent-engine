# ADR 0005: Versioned typed canonicalization and exact simulator dispatch

- Status: accepted via the project lead's explicit merge authorization for PR #2 on 2026-11-19.
- References: D19, D23–25, D39, D67, D70, D72, D79, D95, D97; AC-02–AC-04, AC-06, AC-11.
- Product amendments: none.

## Context and decision

Use the [intent and dispatch contract](../contracts/intent-and-dispatch.md). Validate strict schemas before canonicalizing. Use an RFC 8785 JSON Canonicalization Scheme implementation pinned and tested against published vectors, restricted further to exact integer quantities and a closed schema. Do not implement canonicalization by ordinary `json.dumps` plus hashing.

Create domain-separated SHA-256 digests for immutable intent and exact dispatch metadata. Store canonical bytes and the exact body bytes as well as digests. Bind each attempt to its original intent, approved adapter artifact digest, destination, account, material fields, consistency requirement, and idempotency key. Adapter changes cannot reinterpret an existing intent implicitly.

The initial adapter has a single fixed synthetic capability and closed request mapping. Cover every effect-bearing URL, body, and header field; reject unknown fields rather than passing them through. Dispatch validation reads stored immutable intent and its required authoritative evidence. It does not trust a worker's claimed hash or `verified=true` flag. Changing evidence or policy requires re-evaluation; a new material intent needs a new operation and a permitted business identity.

The transport may add only explicitly non-effect-bearing protocol framing fields. No effect-changing middleware, signer, proxy rewrite, automatic redirect, or hidden retransmission is supported. No real authorization credentials or production signing scheme are introduced. Declare the interpreter, library, adapter build, and network runtime trusted; hashing the adapter is not a sandbox or a proof of the whole environment.

## Alternatives and consequences

Natural-language approval or a body-only hash omits material account/destination effects. An unrestricted JSON schema invites ambiguous fields and number coercions. RFC 8785 supplies serialization rules, but schema and semantic validation remain the project's responsibility. A narrow mapping makes rejection common and intentional until another capability receives its own contract.

## Validation and limitations

See [current implementation evidence](../IMPLEMENTATION_STATUS.md) for partial reference-model/simulator coverage; the full engine enforcement described here remains incomplete. Test canonical golden vectors, duplicate keys, integer/boolean confusion, unsupported floats, omitted/null fields, Unicode, hash-domain separation, request mutation, account substitution, headers/query injection, redirect attempts, and adapter mismatch. Before a real adapter is supported, review its actual authentication, signing, destination resolution, HTTP transformations, and provider evidence semantics separately.
