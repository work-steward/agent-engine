# ADR 0002: Independent state and a fenced send boundary

Status: accepted; durable enforcement pending.

## Decision

Keep dispatch disposition, effect assessment, reconciliation, and attempt phase separate. Their reference relation and guards are in [model.py](../../src/work_steward/model.py), exercised by [model tests](../../tests/test_model.py). Local closure does not establish remote finality.

The engine must first co-commit intent/request binding, grant, attempt, and journal. A second short transaction revalidates current policy/evidence, expiry, state version, and worker generation before recording `send_possible`. Only the uniquely acknowledged winner may invoke transport once; reading an existing boundary after restart does not grant send authority. Disable implicit retries and redirects.

Recovery may atomically fence an admitted attempt without a send boundary as `closed_without_send`. After the boundary, preserve possible remote execution. Final or conflicting evidence stops an unsent retry; a nonterminal old status report alone does not invalidate its proven coverage.

## Rationale

A single success/failure enum hides uncertainty. A lease cannot recall a remote request, and a database lock across HTTP cannot make the provider transactional. Revocation committed before admission blocks admission; a later revocation may be too late for a released sender.
