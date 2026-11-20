# ADR 0008: Bound synthetic dispatch

Status: accepted.

## Decision

Use one built-in loopback adapter. Persist its provider instance, account, contract, and code digest; bind approval to prepared request bytes and destination. Admission commits the concrete attempt request and approval link. Only the caller that acknowledges a new send-boundary commit may invoke transport once. A stored boundary never grants replay authority.

Recheck current policy and evidence at release. Generation, attempt identity, and phase fence stale senders; harmless old status polls need not consume another attempt. Provider identity and resource-version conditions are enforced at the destination.

Admit receipts only after matching instance, operation, account, parameters, provider key, body digest, and known attempt. Reconciliation needs separate current read permission. Preserve raw responses and conflicting observations. Empty lookups prove nothing. Uncertain repetition requires the verified permanent-key contract and complete prior-request coverage; finite retention supplies no arrival bound.

## Limits

The adapter digest covers its mapping/verifier and transport source; the remaining runtime stays trusted. Instance headers prevent accidental replacement, not malicious local impersonation. Synthetic protocol contracts assume an honest provider. Legacy receipts without key evidence are not backfilled; existing approvals need fresh request binding. Real connectors require separate evidence. The inventory scenario and process faults remain under `examples/`.
