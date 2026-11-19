# ADR 0002: Independent action state and a fenced send boundary

- Status: accepted via the project lead's explicit merge authorization for PR #2 on 2026-11-19.
- References: D19, D24, D44–46, D55–56, D68, D75, D82, D95–96; AC-01–AC-08, AC-10.
- Product amendments: none; makes the provisional v0.5 state model concrete.

## Context and decision

An operation's dispatch disposition, external-effect assessment, and reconciliation activity answer different questions. Keep them independent and constrain their combinations with the [lifecycle contract](../contracts/action-lifecycle.md). Attempt phase and provider observations are separate records. A terminal local disposition does not establish a terminal remote outcome.

Commit a typed immutable intent before admission. Prepare the exact request using the approved adapter. In one serialized transaction, validate current authoritative policy/evidence, operation and reservation identity, budgets, capability eligibility, state version, and worker generation; commit the operation-bound grant, new attempt, request digest, and journal event.

Immediately before the first potentially effectful transmission, execute a second short write transaction. Revalidate the attempt phase/generation, current policy, grant expiry and relevant evidence; record `send_possible` and its journal event before transport starts. Commit must succeed with a known outcome. Uncertain commit outcome requires recovery/read-back and must not fall through to sending. Never hold either transaction open during HTTP.

Transmit once under that attempt. The first implementation has no automatic transport retry, authentication retry, redirect following, or effectful status call. A subsequent transmission requires a newly admitted attempt and safe-repetition evaluation. Disable any retry behavior inherited from HTTP libraries or proxies.

Recovery can atomically fence and close an `admitted` attempt as `closed_without_send` if no send-boundary record exists. The same serialization prevents a stale worker from subsequently crossing that boundary. Once `send_possible` exists, assume remote execution remains possible until qualifying evidence says otherwise. Fencing local state cannot recall remote requests or stop an already released dispatcher atomically with revocation.

## Alternatives and consequences

A single success/failure enum loses uncertainty. Holding a database transaction across HTTP cannot make the remote operation atomic and harms recovery. A lease alone does not fence network effects. Treating every admitted attempt as permanently ambiguous is conservative but needlessly discards the proof available before a fenced send boundary.

## Validation and limitations

See [current implementation evidence](../IMPLEMENTATION_STATUS.md) for partial reference-model/simulator coverage; the full engine enforcement described here remains incomplete. Test crashes before/after both commits, revocation and lease takeover at each boundary, unsuccessful commits, duplicate controller commands, and late observations. The trusted dispatcher's adherence to the boundary is an assumption until implemented and tested. Revocation before admission blocks admission; revocation detected before the send-boundary commit also blocks sending. A revocation committed after that boundary may be too late, even if the physical send has not started.
