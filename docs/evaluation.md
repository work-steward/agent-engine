# External evaluation guide

Try to produce a counterexample within the [supported boundary](threat-model.md): one trusted host, surviving authoritative databases, the built-in adapter, and the declared synthetic provider contract. Use synthetic data. Record the Git revision, OS, Python/SQLite versions, commands, and fault ordering.

## Establish the baseline

Follow the [README walkthrough](../README.md), then run:

```sh
make check
uv run --frozen python -m pytest -q tests/test_engine.py tests/test_inventory.py
```

Expected `unsafe-retry` result: stock 10, one attempt, effect `unknown`, and `unsafe_retry_blocked`. [Reconciliation](../examples/inventory/README.md#resolve-the-lost-response) should confirm that operation without sending another adjustment. This case uses C0 with no key or resource-version condition.

## Questions that can falsify claims

| Question / perturbation | Required observation | A counterexample |
| --- | --- | --- |
| Drop an applied unkeyed response; request another attempt through `Engine.dispatch(..., repeat=True)`. | Unknown retained; no second POST. | Another send despite an unresolved outcome and no supported repetition proof. See [engine tests](../tests/test_engine.py). |
| Commit revocation or changed policy before the send boundary. | Dispatch denied; no effectful transmission. | A new send after that serialized change. Revocation after release cannot recall a released sender. See [authority](../tests/test_authority.py) and engine tests. |
| Kill an engine process before/after admission, release, or receipt persistence. | Atomic history/state; unsent attempts fenced; possibly sent attempts retained. | A partial durable record, replay of an old boundary, or unsupported certainty. See [ledger](../tests/test_ledger.py), engine, and [inventory](../tests/test_inventory.py) tests. |
| Resume an old sender after a permanent-key retry. Use C0, without a version condition. | One provider effect; both attempts attributable. | Two effects for that operation under the declared permanent-key contract. See `test_permanent_retry_and_resumed_sender_deduplicate_without_a_version_condition`. |
| Delay an old request; make lookup empty or expire a finite key window. | Empty lookup leaves unknown; uncertain finite-key repetition blocked. | Missing status or retention expiry treated as no-effect finality or permission to resend. See [simulator](../tests/test_simulator.py) and engine tests. |
| Substitute receipt scope/key/digest, or revoke read permission before admission. | No unverified observation; bounded response/transport record retained. | Confirmation from mismatched evidence or admission without current read authority. Prior valid observations remain valid after revocation. See [wire](../tests/test_synthetic.py) and engine tests. |
| Inject a SQL failure at an attempt, send-boundary, or observation commit. | Changed rows and journal roll back. Receipt failure preserves the earlier possibly-sent boundary. | A POST after failed admission/release, or partially committed state/journal. See engine storage-failure tests. |

Use independent connections/processes and explicit barriers to control schedules. Preserve shrinking seeds/traces for generated cases. Judge effects using independent provider persistence; the controller must never use that hidden oracle as permission or evidence.

## Check that the experiment can fail

```sh
uv run --frozen python -m pytest -q tests/test_engine.py::test_unkeyed_retry_guard_prevents_a_real_unconditional_duplicate
```

This test first verifies the engine blocks a repeat. Its harness then deliberately bypasses the engine and demonstrates two unconditional provider effects. That bypass is a positive control for the experiment, not a counterexample to controller mediation. A C2 condition could otherwise hide a broken repetition guard.

## Interpret and report results

An unknown outcome after an applied effect is correct when the controller lacks admissible evidence. Cancellation need not undo an effect. A direct HTTP write, privileged database edit, dishonest provider with valid-looking lies, or stale database restore changes the documented boundary; label such experiments separately. Business acceptance and permission correctness also do not prove that an approved quantity was commercially correct.

For a counterexample, include a minimal synthetic test, exact event order, expected/observed state, attempt count, journal, and independent effect count. Report vulnerabilities through [SECURITY.md](../SECURITY.md); ordinary reproductions can use the [bug template](../.github/ISSUE_TEMPLATE/bug_report.md). The [contributor issues](../CONTRIBUTING.md#starting-points) offer bounded documentation, protocol, and test work.
