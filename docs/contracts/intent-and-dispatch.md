# Intent and dispatch binding contract, proof profile 1

Status: proposed; synthetic simulator capability only.

## Typed immutable intent

The first schema includes schema/canonicalization versions, organization/execution/node/operation identifiers, business-effect namespace/key, capability `sim.effect.create`, destination account/resource identity, integer quantity, pinned resource version when required, consistency requirement, approved adapter identity/artifact digest, verification requirements and pinned material evidence references. Each field has a defined type and bounded length/range. The first implementation PR must encode this contract as a closed machine-checkable schema before any accepted intent is persisted.

No unknown fields, duplicate JSON object keys, implicit defaults, string-to-number coercion, booleans accepted as integers, non-finite numbers, floating-point quantities, or invalid Unicode scalar sequences. Bound total input size, nesting, strings, and collection sizes before canonicalization. JSON integers must be within `[-(2^53-1), 2^53-1]`; the synthetic quantity is a positive integer within that range. Material optional fields have explicit schema semantics: required keys with `null` only when explicitly allowed. Null and omission are not interchangeable.

Preserve Unicode scalar values exactly; do not silently normalize provider identifiers, trim strings, change case, or normalize URLs to make them match. Only approved typed enumerations and literal target grammar are accepted. The first target is a fixed simulator endpoint with a validated resource identifier; no free-form URL comes from a proposal. Test composed/decomposed Unicode and visually similar strings as distinct values unless a field's explicit schema excludes them.

Use [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785) canonical bytes after schema validation. Intent digest is SHA-256 of the byte prefix `work-steward:intent:1` followed by one zero byte and canonical intent bytes. The digest is stored outside the hashed object. Persist the canonical bytes and schema version; never recompute old identity with a new canonicalization algorithm. Unsupported versions are rejected pending a migration design.

Pinned material evidence references establish approved facts/versions. Eligibility may require fresh verification observations of those same facts; the grant binds those observation IDs/versions without mutating the intent. A changed material fact or precondition is a new proposed intent, subject to reservation/supersession rules. Historical approval is not current authorization.

## Exact dispatch request

The adapter constructs and persists a separate dispatch representation containing:

- Schema version, operation and new attempt IDs, intent digest, approved adapter artifact digest.
- Method `POST`, a single approved loopback origin fixed by trusted test-run configuration, and path `/v1/effects`; no query, fragment, userinfo, or proposal-selected host/port.
- Exact UTF-8 canonical JSON body bytes for `operation_id`, `account`, `resource`, `quantity`, and `resource_version` (explicit null when not required). The operation ID is a correlation identity; a non-idempotent provider profile must not secretly deduplicate on it. Send the stable provider key in `Idempotency-Key` when the selected profile supports keyed idempotency, and the attempt ID in `X-WS-Attempt-ID` for observation correlation. The latter may change between attempts and is explicitly excluded from the provider's effect-parameter comparison; it remains covered by the dispatch digest.
- Explicit material header values and the SHA-256 digest of the exact body bytes. Persist body bytes and verify their digest immediately before transport.
- A scoped synthetic credential reference, if that simulator profile requires one. Never persist or expose a secret token as part of the intent, journal, or public trace.

Dispatch digest is SHA-256 of `work-steward:dispatch:1`, one zero byte, and RFC 8785 bytes of this dispatch metadata. Represent body bytes by their digest in the metadata, with stored byte length and encoding; the stored byte sequence must match that digest. Hashing a body does not replace validation of its typed meaning. Reject unknown effect-bearing headers, query/body fields, duplicate headers, or unsupported provider flags.

`AllowedMapping` independently compares stored intent against parsed exact body, account, resource, quantity, preconditions, key scope, destination, method, path, adapter artifact, and capability profile. The mapping validator must not simply compare a request to another copy of the adapter's output. A mismatch denies admission. Policy/evidence admission also validates current authority and required consistency; matching bytes alone is insufficient.

Only protocol framing declared non-effect-bearing by this simulator contract may be supplied by the HTTP library (for example body length and connection framing). Fix JSON content type; explicitly bind the idempotency and correlation headers when used. Conditional resource version is conveyed in the bound body, with an atomic provider-side condition check for C2. Authentication may select only the approved synthetic account; a real signer or account-changing credential transform is unsupported. Disable proxies/environment proxy inheritance, redirects, automatic retries, and middleware body reserialization. Transmit the validated stored bytes through one transport invocation per attempt.

## Provider observations

Accept only bounded, well-formed responses matching the requested account, operation/attempt or provider key, material request identity, and predicate required by the capability contract. Journal transport failure separately from provider observations. Duplicate provider observation identities with different content are contradictions, not valid overwrites.

The simulator profiles distinguish accepted/pending, final effect, final rejection/no-effect, absent/inconclusive, and contradictory evidence. Provide a read-only lookup scoped to account and operation ID, with attempt/provider-key evidence where the profile makes it available. A lookup may expose zero, one, or multiple synthetic effect records; an operation ID is not itself a uniqueness guarantee. A lost POST response must remain reconcilable only to the extent that this declared lookup actually supports it. Each profile declares its idempotency scope/retention/concurrency, status visibility/finality, conditional effect support, and whether reconciliation methods are read-only. Capability requirements select explicit guarantees; C2 requires the provider to check the condition atomically with applying the effect. C1 status/source rechecks cannot stand in for it.

## Before a real connector

Review actual destination resolution/TLS, request signing, authorization/credential-account binding, redirects/proxies, idempotency guarantees, data retention, status finality, and conditional-update semantics. Document which claims are declared, provider-documented, tested, or operationally verified. The loopback transport and synthetic credentials prove none of those real-provider properties.
