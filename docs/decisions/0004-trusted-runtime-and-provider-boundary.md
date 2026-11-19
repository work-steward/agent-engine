# ADR 0004: Trusted runtime with an independently persisted simulator

- Status: accepted via the project lead's explicit merge authorization for PR #2 on 2026-11-19.
- References: D23, D43, D57, D63–65, D69–71, D79, D94, D96, D98; AC-01, AC-03, AC-06–AC-08, AC-12.
- Product amendments: none; initial proof supports no untrusted executable extensions.

## Context and decision

The initial engine/controller, dispatch function, built-in adapter, policy/evidence admission code, and database access are trusted application code. No arbitrary model-produced Python, executable plugin, or general tool runner executes in the proof. A typed proposal or provider response is data, not authority.

Run the simulator in a separate process with a separate database and loopback HTTP endpoint. Killing or rolling back the engine must not roll back an accepted provider effect. Use synthetic accounts, resources, quantities, and provider credentials only. The engine and provider may run under the same OS user for test convenience; this is a failure boundary, not an adversarial security sandbox.

The controller knows only the approved request/status protocol. Scenario configuration and the oracle inspecting provider state belong to the test harness. Keep control channels separate: no status method can expose a hidden fact that the modeled provider would not reveal. Reconciliation uses separately authorized read-only endpoints; a provider's effectful reconciliation mechanism would require a distinct action contract.

The first adapter uses the actual HTTP transport intended for this simulator, with strict request construction, response size limits, schema checks, and bounded timeouts. Bind the destination account/origin in the persisted run configuration; reject host/target overrides. Pin an approved loopback address and port without a proxy or redirect. This validates a narrow synthetic transport, not arbitrary production wire/signing behavior.

## Alternatives and consequences

An in-process fake is useful for reference-model tests but cannot alone establish independent crash durability. A real provider would introduce undocumented side effects and nondeterminism before the local protocol is proven. Building an executable-plugin sandbox now would expand the proof beyond the first milestone.

## Validation and limitations

See [current implementation evidence](../IMPLEMENTATION_STATUS.md) for partial reference-model/simulator coverage; the full engine enforcement described here remains incomplete. Verify the engine survives or reconstructs its state after forced termination while the provider remains alive; verify provider restart independently; reject malformed and unauthorized responses without changing authority. AC-12 is limited to not exposing secrets/effect channels through the supported typed proposal path. It does not establish arbitrary-code containment. Details and exclusions are in the [threat model](../threat-model.md).
