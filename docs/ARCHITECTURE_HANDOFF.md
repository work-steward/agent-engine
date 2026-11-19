# Reliable Agent Execution Harness — Architecture & Codex Handoff

**Document version:** 0.1 (handoff consolidation)
**Architecture baseline:** Execution Kernel v0.3; Action Controller **v0.5** supersedes v0.4
**Decision record:** 100 confirmed product decisions; Question 101 proposed but **not answered**
**Status:** Provisional design, **not** approved for production consequential actions
**Date:** 2026-11-19

> This is the repository-ready source-of-truth *starting point*, reconstructed from the product-discovery and architecture-review conversation. The numbered decisions below preserve the intent of the user's choices. Architectural refinements are **proposals**, not retroactive amendments of those choices. Do not infer guarantees beyond the documented trust assumptions or describe open design details as resolved.

## 1. Mission and non-goals

Build an open-source, fully self-hostable **reliable AI agent execution harness** that can eventually empower **nontechnical teams** to create, validate, execute, supervise, and improve agent-driven business workflows. The primary technical contribution is dependable, inspectable, contract-governed agent execution; a nontechnical workbench is a later access layer. This is **not a startup/business plan**. Favor an open ecosystem, portable workflow definitions, transparent guarantees, and no mandatory closed SaaS service.

Non-goals for the first kernel proof: a polished UI; general multi-agent orchestration; broad connector/plugin marketplace; automated autonomy certification; distributed orchestration; production shared-runtime multi-tenancy; automatic model-provider failover; full disaster-recovery guarantees; comprehensive information-flow tracking across arbitrary generated text.

## 2. Core architectural posture

- **AI proposes; trusted execution authority disposes.** LLM output is untrusted as an authorization source and cannot directly enlarge authority or dispatch consequential external effects.
- Start as a **single-node modular monolith** backed by transactional persistence, not a microservice system. Components below are logical seams, not mandatory processes.
- Build and own execution semantics, state-transition enforcement, authorization/verification admission, action control, and recovery contracts; **reuse mature infrastructure** when it satisfies the invariants. Avoid reinventing storage engines, cryptography, or schedulers by default.
- Constrain the first release's supported adapter and threat model. The system cannot guarantee exactly-once external effects against arbitrary APIs; a timeout is not proof of failure.
- Maintain distinct representations for **workflow definition, workflow execution, business action intent, dispatch request, dispatch attempt, external-effect assessment, and business outcome**.
- Deliver invariant-first vertical slices with independently reproducible conformance tests; defer broad extensibility until the trusted boundary and effect semantics are demonstrated.

## 3. All 100 confirmed decisions

The following summarizes the selected decisions, one per decision number. Numbers are stable references for ADRs and design reviews.

### Product mission, experience, governance (1–21)

1. **Mission:** Democratize *reliable* AI agents for nontechnical people rather than generic no-code automation.
2. **Audience:** Nontechnical teams/departments/small organizations with shared agents, knowledge, workflows, approvals.
3. **Authoring:** AI drafts workflows; humans visually configure, review, and approve rules and permissions.
4. **Autonomy:** Progressive, earned autonomy; initially supervised, increased against measured reliability.
5. **Correctness:** Explicit hybrid verification contracts based on documents, domain expertise/packs and reviewed executions; consequential uncertainty escalates.
6. **Execution:** Structured, inspectable workflows containing dynamic agentic reasoning stages and checkpoints.
7. **Interface:** Progressive disclosure from simple business goals to advanced contracts, traces, and controls.
8. **Failure UX:** Safe automatic recovery where justified; plain-language explanations, guided intervention, proposed/tested improvements.
9. **Governance:** Organization-specific roles, policies, approvals and autonomy with non-bypassable core security.
10. **Extensibility:** Shared harness plus installable domain packs, reusable integrations/validators/workflows/UI extensions, community catalog.
11. **Contributions:** Nontechnical domain experts author declarative packs with AI assistance; executable extensions have stricter controls.
12. **Deployment:** Fully open source, self-hostable; optional third-party/community managed hosting, no closed-service lock-in.
13. **Models:** Provider-agnostic, policy-governed routing among commercial/open/local models with compatibility validation.
14. **Context:** Governed adaptive organizational knowledge distinct from execution state and memory; provenance, permissions, retention, approved trusted memory.
15. **Work objects:** Connected goals, projects, cases, tasks, workflows and agents, with domain-native presentations.
16. **Delivery:** Experience-first complete nontechnical vertical slice; only essential harness capability initially.
17. **Success:** Nontechnical participants independently create, validate, execute and supervise workflows meeting defined safety/correctness thresholds.
18. **Actions:** First meaningful integrated experience performs approved external actions, not merely recommendations.
19. **Authorization:** Risk-adaptive, bounded action authorization; exact high-risk operations, preconditions, expiry and audit.
20. **Assurance:** Layered platform checks, domain verification, organizational acceptance, supervised-execution evidence; distinguish established and unverified assurances.
21. **Autonomy lifecycle:** Organization-authorized progression/regression, risk-based monitoring, reversible scoped autonomy.

### Agent/workflow platform and ecosystem (22–40)

22. **Triggers:** Event-driven execution from connected systems, documents, email, business events.
23. **Trust boundary:** Separate instruction from data; provenance, prompt-injection defenses, least privilege and authority enforced outside LLM text.
24. **Reliability:** Durable resumable execution, deduplication, reconciliation and explicit state; compensations only when supported; no universal exactly-once claim.
25. **Connectors:** Layered standards/community/curated integrations; visual configuration, AI-assisted authoring, declared/tested capabilities, stricter executable extensions.
26. **Observability:** Business-level outcomes, objects, timelines, evidence-grounded explanations and optional technical traces.
27. **Boundary:** Opinionated agent workbench, replaceable infrastructure, integrate existing business apps rather than replace them.
28. **Accessibility:** Supported core journey can be completed without engineering; specialized advanced integration/infrastructure work may require developers.
29. **Agent composition:** Use simplest agent architecture by default; multiple agents only where demonstrated benefit outweighs coordination cost.
30. **Workflow evolution:** Governed versioning, change-impact analysis, migration proposals, tests, staged rollout and autonomy revalidation.
31. **Testing UX:** Progressive validation studio with AI-suggested scenarios, domain review, simulated connectors, shadow comparisons and readiness gaps.
32. **Onboarding:** Conversational goal/process discovery generates the initial workflow.
33. **Elicitation:** Early partial visual drafts with iterative questions and updates; no guessed critical requirements.
34. **Source of truth:** Structured, versioned workflow model shared by conversation and visual editor; distinguish draft authority from activation.
35. **Sessions:** Interactive agent sessions and reusable automated workflows share execution, verification and governance; reviewed sessions can become workflows.
36. **Cost:** Policy-governed budgets and business-facing costs; model routing optimizes under hard reliability/security constraints.
37. **Reference workflow:** Recognizable cross-industry process with meaningful checks and external actions, synthetic data, reviewed with domain experts.
38. **Catalog trust:** Federated distribution with provenance, signatures, tests, status, capability declarations and org trust policy; executables stricter.
39. **Portability:** Versioned privacy-preserving workflow packages with contracts/tests/dependencies, not secrets/private data/policies; revalidate locally.
40. **Collaboration:** Shared human-agent workspaces/queues, assignments, handoffs, escalation, role-based delegation and audit trails.

### Engine ownership, trust and operations (41–59)

41. **Original contribution:** Reusable reliable agent execution harness; workbench is access layer.
42. **Ownership:** Build/own the complete execution engine semantics, scheduler/persistence/retry/orchestration/tool auth/verification; later review refines *ownership* vs infrastructure reinvention.
43. **First topology:** Single-node, production-quality *semantics* (durability, auth, verification, retries, recovery), with future distributed boundaries.
44. **Persistence:** Checkpoint-based journal and append-only consequential audit; review clarifies atomic state/event commits and checkpoint role.
45. **Ambiguous effects:** Conservative evidence-based reconciliation, never blind retry of consequential non-idempotent unknown outcomes; suspend/escalate.
46. **Agentic stages:** Contract-governed dynamic planning/tool use with deterministic checks at action boundaries; pause/inspect/resume/terminate.
47. **Business correctness authority:** Human reviewers initially assess business correctness.
48. **Human review reduction:** Begin with human review; user suggested initial **500 successful supervised executions** as a threshold hypothesis.
49. **Certification:** Evidence-based; combine 500-success hypothesis, coverage, risk, confidence, organizational approval; scoped/revocable.
50. **Trust scope:** Capability/work-category and dependency-aware certification by versions/models/connectors/policies/contracts; targeted revalidation.
51. **Initial labels:** Final-result human approval counts as initial acceptance/success signal; later decisions explicitly separate acceptance from objective correctness.
52. **Corrections:** Preserve original approvals but retrospectively update reliability and reduce/suspend autonomy as appropriate.
53. **Monitoring:** Continuous risk-adaptive automatic checks, random audits, drift detection, exception review and recertification.
54. **Incidents:** Risk-scoped containment, preserve evidence, inspect completed/in-flight effects, compensate only when verified/authorized.
55. **Current authority:** Recheck live permissions and policies before each external action; revocation blocks subsequent unauthorized actions.
56. **Strong auth:** Layered local atomic admission/dispatch records, scoped credentials, revocation awareness, destination-side enforcement where possible; cannot revoke already accepted remote effects.
57. **Extension isolation:** Declarative constrained interpretation; executable adapters sandboxed/out-of-process/service with scoped resources, engine-mediated effects.
58. **Upgrades:** Compatibility-governed contracts, validated state migration and revalidation of material reliability dependencies.
59. **Scheduling:** Bounded policy-governed concurrency with priority, isolation, backpressure, rate limits and budgets.

### Delivery and kernel (60–65)

60. **Team:** Solo-led principal development with AI assistants; later recruit open-source maintainers.
61. **Time:** Variable weekly availability; independent small milestones rather than rigid long deadlines.
62. **Milestones:** Independently usable reliable engine first; thin nontechnical workbench second, on the *same real engine*.
63. **Engine acceptance:** End-to-end fault-injected authorized action, approvals, checkpoints, crashes, ambiguous effects and controlled recovery.
64. **Conformance:** Deterministic simulation, fault injection, property-based state-machine invariants, connector tests, reproducible suite.
65. **Primitives:** Small typed kernel for computation, inference, external action, human review, verification and flow; review separates task kinds, control constructs and contracts.

### Versioning, security, consistency and outcome (66–77)

66. **Interview process:** No fixed question limit, but only meaningful discovery questions; subsequent conversation agreed architecture can proceed now.
67. **Workflow versioning:** Active executions pin immutable definitions; authorized validated migration; immediate mandatory policy/security changes.
68. **Inference recovery:** Journal committed model responses, tool decisions, model config and context refs; replay committed results; safely rerun uncommitted inference.
69. **Sensitive storage:** Privacy-aware tiered storage with minimal journal; segregate recovery state, sensitive context and audit evidence; configurable retention.
70. **Identity:** Contextual least-privilege agent/workflow identities, scoped delegation, separate access and disclosure checks.
71. **Data flow:** Classify and track provenance, approved destinations, minimization, disclosure rules; do not claim perfect taint tracking through arbitrary LLM text.
72. **Evidence consistency:** Version-bound evidence/preconditions; revalidate changes; destination-enforced conditions when supported; suspend if guarantees not established.
73. **Concurrency:** Contract-governed resource IDs, optimistic conditions by default, targeted locks/reservations, external atomic ops where available.
74. **Events:** Durable intake, transport dedup, business-effect idempotency, version/order checks and controlled acknowledgments; not exactly-once delivery.
75. **Human tasks:** First-class durable suspension, deadlines, delegation/escalation, revalidation, auditable lifecycle.
76. **Progress:** Hard budgets/limits, progress signals and loops, completion criteria; pause/stop/human guidance; no self-expanding authority.
77. **Completion:** Evidence-based per-stage contracts, deterministic checks, supplementary independent evaluation and human handling of unresolved consequential judgments.

### Architecture, certification and release gates (78–89)

78. **Implementation:** Invariant-first, contract-driven vertical slice; prove essential guarantees under injected faults, defer speculative abstractions.
79. **Connector eligibility:** Verify claimed capabilities; match required contract/risk; authorized compensating controls only when sufficient, else block/suspend.
80. **Adaptation:** Contract-bounded dynamic planning; material deviations separately authorized; reusable changes go through governed versioning.
81. **Plan verification:** Hierarchical, risk-adaptive checks of each capability and composed plan, revalidate changes, don't assume safe composition.
82. **Outcomes:** Separate execution state, terminal disposition, objective satisfaction, verification status, and human acceptance; partial and blocked states.
83. **Autonomy:** Risk-scoped evidence-based certification; 500 successes configurable hypothesis, not proof; coverage/statistics/outcomes/approval/rollout.
84. **Ground truth:** Triangulate reviewer acceptance, expert adjudication, deterministic evidence, benchmarks, downstream outcomes and corrections; track label uncertainty.
85. **Engine release:** Documented developer interface, realistic reference workflow, reusable contracts, reproducible security/recovery/action conformance; disclose experimental gaps.
86. **Workbench release:** Independently tested nontechnical end-to-end journey on real engine: conversation, visual review, setup, validation, supervision, approvals, recovery, outcomes.
87. **Reference choice:** Explicit rubric (familiarity, usability, expert access, verification, external effects, recovery, cost); one workflow across milestones unless justified.
88. **Rule authoring:** Conversational elicitation + domain rules + AI structured contracts + visual review/examples; distinguish subjective vs enforceable.
89. **Activation:** Draft/simulated/supervised/authorized lifecycle; structural, evidence, policy, connector, risk gates; supervised not a security bypass.

### Bootstrap, audit, operations and extensibility (90–100)

90. **Bootstrap:** Installation-controlled one-time authority, verified initial admin, local simple setup/optional IdP, credential recovery, multi-party high-risk controls.
91. **Audit:** Access controls, tamper-evident commitments, signed checkpoints, optional independent anchoring/portable verification; compromised host can fabricate evidence.
92. **Model failover:** Approved fallback only when capability, data-flow, budget, and trust contracts remain satisfied; else pause/authorize.
93. **Disaster recovery:** New recovery epoch after potentially stale restore; validate continuity, quarantine uncertain effects, reconcile before resuming.
94. **Credentials:** Brokered encrypted storage or pluggable secrets managers, short-lived scopes when possible, no model-facing secrets, rotate/revoke/revalidate.
95. **Action binding:** Validate business intent and actual dispatch, single-use scoped grants, mediated effects; constrain/reject unverifiable guarantees.
96. **Trusted core:** State, authorization, verification admission, credential brokerage, consequential dispatch in minimal trusted enforcement; declarative extensions preferred, executable adapters isolated.
97. **Dependency upgrades:** Pin runtime dependencies, validated migrations, immediate quarantine of vulnerable versions, trust revalidation.
98. **Organization isolation:** Tenant-aware immutable org boundary in identities/state/credentials/data/policies/audit; initially one org per engine; shared-runtime multi-tenancy later with tests.
99. **Delegation:** Durable, traceable child executions with bounded authority/resources, safe cancellation and reconciliation, ownership transfer explicitly authorized.
100. **Interfaces:** Reusable core; persistent service API, CLI and SDK on shared contracts; embedding later if it preserves trust/recovery semantics.

**Decision 101:** A proposal was presented about consequence-oriented transparency, but the user **did not answer** before switching to architecture. It is not a confirmed decision. Treat as a design recommendation derived from Decisions 7, 26, 28 and 88.

## 4. Architecture v0.5 — logical boundaries

```text
Clients: Workbench (later) | CLI | SDK | Other applications
            |
     Authenticated service API / workflow command boundary
            |
       Trusted execution authority
       - transition + durable commit coordinator
       - organization, policy, capability enforcement
       - verification evidence admission
       - Action Controller (admission, ledger, dispatch control, outcome assessment)
       - resource/lease/budget enforcement
            |
   +--------+-----------+-------------------+
   |                    |                   |
Model/task workers    Domain verifiers   Trusted dispatch adapter
(untrusted output)    (typed claims)     (bounded creds/network)
   |                    |                   |
Model providers        Evidence sources   External systems
            |
    Transactional authoritative persistence
    Execution state, journal, action ledger, attempts,
    uniqueness claims, leases, human tasks, evidence refs
            |
 Separate governed sensitive-context store / secret provider
```

These are **logical responsibility boundaries**. A single-node modular monolith is the initial deployment. The trusted computing base also includes persistence atomicity, host/process isolation, credentials, network dispatch library, and build/supply-chain dependencies; drawing a box does not make dependencies untrusted. In-process embedding and shared-runtime multi-tenancy are later options.

### 4.1 Workflow and execution abstractions

- **Immutable WorkflowDefinition:** organization, workflow identity/version/content digest, typed nodes, edges/control structures, permitted capabilities, contracts, budgets, executable dependencies.
- **ExecutionInstance:** organization, execution ID, pinned definition, lifecycle status, node instance/attempt IDs, state version, lease generation, outcome dimensions.
- **Task kinds (initial conceptual types):** compute (pure), infer (model), interact (external action), human (durable request). Verification is normally a **contract evaluated at a boundary**; explicit verification tasks are permitted when evaluation needs work.
- **Control constructs:** branch, bounded loop, completion; eventually parallel join and child delegation. First kernel may start with one active branch.
- **Distinct outcomes:** terminal execution disposition, business-objective satisfaction, claim verification, human acceptance. Do not conflate.

### 4.2 Transactional durability and fencing

State transitions and corresponding journal events must be committed **atomically** within the supported transactional persistence boundary, together with newly admitted action intents or work records when required. Use state-version compare-and-set and worker lease generations to reject stale writes. A lease expiration does not prove a previously launched network request had no effect. Checkpoints are acceleration/recovery aids and never override later committed records. Ordinary crash recovery assumes the durability substrate survived; restoring stale backups is a separate, partially deferred protocol.

## 5. Action Controller v0.5 — normative conceptual contract

### 5.1 Responsibilities

1. **Admission:** Validate typed immutable business intent, organization identity, capability, business uniqueness, policy and required evidence.
2. **Durable ledger:** Record intent, attempts, grants, observations, effect assessments and event trail atomically with authoritative transitions.
3. **Controlled dispatch:** Map approved intent into exact provider-specific request through an approved trusted adapter, validate all material effect parameters and approved destination, admit and record attempt before send.
4. **Reconciliation:** Interpret evidence of remote effect, decide safe retry or suspension, distinguish observable transport response from business outcome.

### 5.2 Four distinct identities

- `execution_id`: one workflow execution.
- `operation_id`: one immutable intended external effect; stable across retries.
- `business_effect_key`: domain-defined uniqueness identity spanning executions, where required (e.g., single settlement of an invoice); must not be inferred automatically from matching amounts.
- `provider_idempotency_key`: provider-scoped identifier with documented deduplication and retention semantics. **Not interchangeable** with operation ID.
- `attempt_id`: new ID for each authorized network transmission attempt.

Atomic business-effect key admission can prevent conflicting effects **within shared engine state**. It cannot stop another system making an equivalent external effect unless the destination enforces uniqueness.

### 5.3 Two-level canonicalization

**BusinessActionIntent (immutable):** organization, execution and node, operation/business-effect key, capability, business target, typed material parameters, verification/evidence refs, consistency requirement, approved adapter identity/artifact digest, canonicalization version and intent digest.

**DispatchRequest (one attempt):** operation/attempt IDs, approved destination authority/path/method/query, target account, typed effect-bearing body/headers, stable idempotency key, adapter digest, intent digest and dispatch digest.

The trusted dispatch path MUST validate `AllowedMapping(intent, request, adapter, policy)`. All security-relevant recipient, amount, account, destination, method, currency, query/body fields and provider-specific effect flags must be covered. Unknown material fields are rejected. The validated request must not undergo unvalidated effect-changing transformations before transmission (including redirects, proxy behavior or signer modification). Use a deterministic, versioned canonical serialization; **do not assume ordinary JSON hashing is canonical**.

### 5.4 Independent action-state dimensions

Do **not** implement one enum combining all concepts.

- **Dispatch disposition:** proposed, blocked, eligible, attempt_admitted, paused, closed (future dispatch authority).
- **External effect assessment:** not_attempted, unknown, pending, no_effect_confirmed, effect_confirmed, conflicting (what evidence supports).
- **Reconciliation activity:** idle, scheduled, investigating, awaiting_human (how uncertainty is handled).

Constrain valid combinations with a formal transition table. An operation may have `closed` dispatch authority while `unknown` effect and `scheduled` reconciliation; cancellation does not erase prior external effects. Individual attempts and observations are append-only provenance records. An effect assessment requires admissible typed evidence.

### 5.5 Authorization and revocation

Distinct artifacts: human approval of specific proposal; policy authorization decision; short-lived, operation-bound dispatch grant. A grant binds org, operation/intent digest, approved adapter/destination, credential reference, policy and evidence versions, validity/attempt limits. Local cryptographic signatures are not required merely to enforce a locally persisted grant.

**Local linearization point:** atomic transaction that validates authoritative current policy and evidence and commits one dispatch attempt (serialized consistently with revocations and competing claims). Revocation committed before this point blocks admission. A pre-send check can stop detected revocations after admission **where still preventable**. Revocation does **not** atomically cancel a remote request already admitted or accepted. Do not hold database transactions open during remote calls; remote destination-side enforcement is required for stronger guarantees.

### 5.6 Dispatch sequence

1. Validate and commit immutable business intent and any business uniqueness claim, with journal event, without network effect.
2. Evaluate eligibility: required typed evidence, authorization, freshness, connector capabilities, budgets, policy.
3. Trusted adapter constructs exact provider dispatch request; validate material mapping and destination.
4. In one transaction: recheck authoritative policy and relevant preconditions, claim an eligible attempt, bind request digest and grant, commit attempt + journal event.
5. Pre-send check; durably record `may_have_sent` **before first potentially effectful transmission**. Perform remote call **outside** database transaction.
6. Persist transport/provider observations; admit effect assessment only on evidence meeting contract.
7. If unknown, reconcile through separately authorized read-only/status methods, repeat only if proven safe, otherwise suspend/escalate.

**Crash windows:** After attempt admitted or `may_have_sent`, a crash can make “not transmitted” and “remote effect accepted” indistinguishable. Treat as potentially sent unless reliable proof rules it out. Never infer remote failure from a timeout. Stale workers cannot overwrite state; their trustworthy late observations may still be admitted as evidence.

### 5.7 Retry safety

Classes: pure read; intrinsically idempotent effect; provider-keyed idempotent effect with scoped/limited guarantees; reconciliation-before-retry; non-reconcilable effect. A new effectful attempt with any prior unknown outcome requires **safe-repetition proof** covering all relevant attempts, plus current authorization, valid preconditions and budgets. Idempotency guarantees must include scope, parameter matching, time window and concurrent request behavior. If unknown and unsafe to retry: **suspend indefinitely or escalate**; never manufacture finality.

### 5.8 Evidence and consistency

Typed claims identify subject, predicate, method (`deterministic`, `human`, `model_assessment`, `external_attestation`), verifier/version, versioned evidence refs, outcome (`passed`, `failed`, `indeterminate`) and validity conditions. Generic `verified=true` is not sufficient. Provider request accepted != payment settled; human accepted != objective achieved; two correlated models != independent ground truth.

Consistency requirements (per capability):
- **C0** snapshot/versioned evidence only;
- **C1** recent pre-send source recheck (**not atomic**);
- **C2** destination-side *atomic* conditional effect (e.g., compare-and-set);
- **C3** stronger transactional destination semantics under documented scope.

A workflow requiring C2 cannot be considered satisfied by C1 rechecking. Connector support must be documented/tested; unsupported mandatory consistency blocks the action.

### 5.9 Capability profiles and trust

Each connector action declares typed request mapping, allowed destinations, idempotency scope/window/concurrency behavior, outcome lookup/finality, conditional effects, reconciliation methods (including whether effectful), and evidence. Distinguish **declared**, **tested**, **provider-documented**, and **operationally verified** capabilities. This is not a universal rank; the engine matches **specific** proven guarantees to each required operation contract. An adapter may be safe for reads but ineligible for high-risk payments.

### 5.10 Reference threat model

**In scope:** malicious/malformed model output, prompt injection, untrusted documents/results, unauthorized requests, duplicate commands, concurrent/stale workers, process crashes, dropped responses, stale evidence, local policy revocation, accidental secret leakage, supported trusted-adapter mapping defects detectable by tests.

**Out of scope for initial protection guarantee:** malicious root/host administrator; compromised privileged dispatcher with unrestricted bypass; dishonest external provider; provider violation of its declared guarantees; arbitrary executable plugins with raw credentials/network access.

**Trusted dependencies:** transactional database and configuration, transition/authorization controller, privileged dispatcher and built-in adapter, credential provider, process isolation, network stack and build artifacts. The trusted computing base is larger than the logical controller. No untrusted model/worker/extension may obtain a capability that bypasses consequential dispatch.

### 5.11 Key invariants

- **AC-01** Potentially effectful transmission implies previously committed immutable intent and attempt record.
- **AC-02** Operation identity cannot be rebound to different material parameters.
- **AC-03** Validated dispatch request realizes the approved canonical intent under approved adapter/policy.
- **AC-04** Current policy is verified at the serialized attempt-admission point; revocation committed before admission blocks it.
- **AC-05** Unknown prior effect + no safe repetition proof implies no new effectful attempt.
- **AC-06** Outcome confirmation requires typed admissible evidence meeting contract.
- **AC-07** Stale worker cannot overwrite newer authoritative state; accepted late observations still attach to original attempts.
- **AC-08** Cancellation/revocation stops future unauthorized dispatch, does not roll back remote effects or erase uncertainty.
- **AC-09** Business uniqueness claims prevent conflicting admissions within the declared engine scope.
- **AC-10** Material state change and corresponding journal event commit atomically.
- **AC-11** Required C2 consistency is never silently downgraded to C1.
- **AC-12** No privileged secret or unmediated external effect channel is given to untrusted agent code within supported threat model.

## 6. Targeted conformance plan

Use a deterministic simulated external system with controlled responses: success, definitive no-effect, pending, timeout, accepted-then-dropped-response, delayed observation, duplicated status, contradictory outcome, idempotency expiry, changed remote state. Inject crashes **before and after each durable boundary**; generate concurrent worker and revocation races.

**Gate A — Mapping integrity:** $500 cannot become $5,000, supplier A cannot become supplier B, unapproved accounts/redirects/headers/body effect fields rejected, adapter artifact mismatch handled.

**Gate B — Deduplication:** duplicate events/executions with same domain effect key cannot both admit conflicting effect; legitimate separate installments permitted under distinct domain identities.

**Gate C — Authorization:** serializable revocation versus dispatch admission; stale approvals or changed evidence block dispatch; clear documentation of post-admission race.

**Gate D — Durability:** atomic intent/event/attempt commits, restart recovery; remote acceptance without response -> unknown, never automatic new effect; stale worker response becomes evidence without stale state-write privilege; expired idempotency window forbids unsafe retry.

**Gate E — Evidence:** provider accepted != final settlement, C1 != C2, contradictory records suspend, unrelated typed claim cannot satisfy required predicate.

**Property tests:** random sequences of crashes, retries, cancellations, revocations, worker lease expirations, provider responses and evidence invalidations; assert AC-01 through AC-12 under modeled assumptions. A green simulator test is *not* proof against arbitrary live providers.

## 7. Delivery plan and release gates

### Stage 1 — Kernel proof (first coding target)

- Typed immutable intent and deterministic canonicalization version.
- Transactional execution/action ledger with event co-commits and state-version/lease fencing.
- Domain-scoped uniqueness reservation, small action state model, attempt preparation, claimed dispatch, and outcome evidence.
- One **trusted simulated adapter**, with controlled external-system failure injection.
- Basic fixed policy, explicit capability requirement and denial; no generalized policy language.
- Reconciliation and conservative retry/suspend behavior.
- A reproducible conformance suite covering documented invariants.

**Exit gate:** All supported invariants survive deterministic failure injection; no unacknowledged remote result is misclassified as definitive non-effect.

### Stage 2 — Independently usable engine

- Add at least one supported **real** trusted adapter; verify its actual provider guarantees.
- Durable workflow nodes, model inference with journaled accepted results, persistent human approval and revalidation.
- Stable developer-facing service API and CLI; optional SDK over same contracts.
- Reference workflow and documented conformance/limitations; no production-risk claims beyond demonstrated guarantees.

### Stage 3 — Nontechnical workbench

- Conversational elicitation, visual review, progressive contract authoring, simulation, supervised real actions, human queue, understandable outcomes/recovery.
- Independent nontechnical usability tests without silent engineer setup.

### Deferred, not discarded

General multi-agent execution, community executable plugins, sophisticated certification, distributed scheduling, comprehensive disaster restoration, shared-runtime multi-tenancy, advanced model routing and automatic cross-provider failover, independent audit anchoring. Defer implementation but ensure initial *supported paths* do not bypass mandatory protections.

## 8. Proposed refinements to prior decisions (not yet ratified amendments)

- **D42:** Own core execution semantics and enforcement; do not automatically build every infrastructure component from scratch.
- **D44:** Transactional authoritative state + atomic event journal; checkpoints are recovery optimizations, not conflicting sources of truth.
- **D19/D55/D56/D95:** Local dispatch admission is linearized with policy; remote cancellation/finality needs provider-side guarantees. Action grants bind precise request intent and dispatch, not merely a verbal approval.
- **D24/D45/D73/D74:** Domain business-effect uniqueness is separate from local operation ID and provider idempotency, and consistency levels must be explicit.
- **D50/D51/D82–84:** Reviewer acceptance, evidence verification and objective success are independent signals; label uncertainty and provenance.
- **D57/D65/D96:** Trust boundary includes actual privileged runtime dependencies; separate task kinds/control structures/contracts; built-in trusted adapter initially.
- **D78/D85/D86:** Internal kernel proof, independently usable engine and workbench are distinct acceptance gates; all product features do not block the first proof.

## 9. Open engineering gaps — must be resolved in implementation ADRs

1. **Canonicalization:** exact typed serialization standard, null/omission handling, numeric normalization, URI normalization, digest versioning, and migration compatibility.
2. **Wire binding:** exact request fields/bytes vs validated representations; HTTP transport transformations, redirects, DNS/proxies, signing and credentials; which mappings can be proven for first adapter.
3. **Database transactions:** isolation levels, conditional update semantics, authoritative journal sequencing, uniqueness reservation lifecycle, worker fencing and recovery from partial worker work.
4. **Formal state machine:** legal combinations and transitions across disposition/effect/reconciliation; attempt lifecycle; completion and cancellation transitions.
5. **Revocation:** race specification and deterministic concurrency tests, especially admission vs send; avoid claiming retroactive remote cancellation.
6. **Reference connector:** select a real external integration only after testing idempotency, conditional updates and reconciliation evidence relevant to the reference action; do not manufacture support.
7. **Trust and secrets:** concrete initial process boundary, secret-store threat model, deployment assumptions; no requirement for sophisticated enterprise setup in kernel proof.
8. **Data lifecycle:** sensitive context encryption/retention and whether deletion affects replay, audit and recovery; precise first-release scope.
9. **Disaster recovery:** advanced recovery-epoch and off-host evidence anchors are not part of the initial normal process-crash guarantee.
10. **Reference workflow:** apply Decision 87 rubric later; do not prematurely lock to payments/invoices just because they illustrate risks.

## 10. Codex execution instructions

**First principle:** Treat this document as an architecture baseline, not a mandate to implement the full long-term platform. Do not reinterpret unresolved points as decided or weaken documented safety contracts to make a demo pass.

**Initial Codex sequence:**

1. Inspect the repository and identify existing language, build system and dependencies. If no repository exists, propose a minimal project structure; select technology *after* clarifying persistence and test needs, not from product-domain assumptions.
2. Save this handoff and create concise ADRs for concrete implementation choices. Record which decisions are confirmed, proposed, and deferred. Do not silently alter the numbered product decisions.
3. Write a **machine-checkable reference state model** for action disposition, effect assessment, reconciliation activity, and attempts, with explicit transition guards.
4. Write the **deterministic external-system simulator** and failure-injection controls, including crash boundaries and provider idempotency variants.
5. Specify transaction boundaries and create a minimal durable action ledger. Make journal and state commits atomic; enforce uniqueness and fencing.
6. Implement the narrowly scoped trusted adapter and action-to-request mapping, then dispatch admission, observation, reconciliation and safe retry decisions.
7. Implement and run property-based/concurrency/failure conformance tests; report what has been demonstrated and what remains unverified.
8. Stop for targeted architecture review when a critical guarantee cannot be enforced under the chosen storage, adapter or process boundary. Suggest a narrowly scoped ADR instead of speculative framework abstractions.

**Explicitly do not start with:** a full workbench UI, open connector marketplace, general delegation/multi-agent system, broad model provider support, autonomous certification engine, or distributed deployment.

**First pull request / milestone acceptance checklist:**

- [ ] Documented threat model and supported trust boundary.
- [ ] Versioned canonical intent and dispatch mapping contract.
- [ ] Typed action-state reference model with illegal transitions tested.
- [ ] Durable intent, business-effect uniqueness and attempt commits.
- [ ] No effectful transmission before durable dispatch-attempt and send-boundary records.
- [ ] Unknown-outcome handling, reconciliation and safe-retry policy.
- [ ] Deterministic simulator and crash/revocation/concurrency tests.
- [ ] Explicit record of unsupported guarantees, including arbitrary API exactly-once, malicious host admin, and untrusted executable connectors.

## 11. Suggested repository organization (conceptual, not language-specific)

```text
/docs/
  ARCHITECTURE_HANDOFF.md
  decisions/                    # ADRs with status and references to D1–D100
  threat-model.md
  contracts/                    # Canonical action, evidence, execution and capability contracts
  conformance.md
/core/                          # Transition and action authority
/adapters/                      # Only supported trusted adapters at first
/simulator/                     # Deterministic provider / fault injection
/tests/                         # State-model, property and crash/recovery tests
/examples/                      # Reference workflow when selected
```

## 12. Change-control protocol

- Preserve the numbered **100 confirmed decisions** as user choices. Only modify them upon explicit review/approval; record amendments as ADRs referencing the original numbers.
- The Action Controller **v0.5** is the latest provisional architecture; v0.4 is superseded.
- A design change affecting authorization, external effects, recovery, evidence, or secrecy must identify changed invariants and update conformance tests before being accepted.
- Report separately **designed**, **implemented**, **tested**, and **provider-dependent** guarantees. Avoid vague labels such as “secure,” “exactly once,” or “fully autonomous” without precise scope.
- Keep documents in the repository; do not rely on ChatGPT/Codex conversation history alone.
