# PI Firm Lab — release 1 specification

Status: implementation acceptance contract. Date: 2026-11-10.

## Scope
A standalone, persistent miniature PI firm and evaluation laboratory. Grow-inspired functionality, not a Clio product or certified emulator. No live vendor credentials, external email/SMS, existing-system imports, or shared databases. Local software must work without any AI-provider account.

Release 1 implements text/API/browser workflows. Real-time telephone/browser audio, actual signatures, real message delivery, production multi-tenancy, and full Clio API compatibility are explicitly out of scope. Optional model integrations must not be claimed as verified without provider tests.

Architecture adjustment: isolated SQLite databases per world replace the proposed shared PostgreSQL deployment for the self-contained release. A separate control database stores scenarios, runs, access grants, and evaluator results. Business state is persistent, versioned, and audited. Only the controller has reset/snapshot/fault authority.

## Acceptance matrix
- A01 Standalone install and server; health, browser console, public PI website, OpenAPI, documented CLI.
- A02 Contacts separate from matters. Leads inbox supports conversion to existing/new contact plus matter. Multiple matters per contact. Configurable pipeline, matter types, source, notes and PI custom fields.
- A03 Tasks, assignees, deadlines, completion, escalation and attorney acceptance; roles enforced server-side.
- A04 Local email/SMS: draft, send, received, failed, retry; delivery does not reach the public internet.
- A05 Staff availability and appointments with conflict checking; callbacks represented as tasks.
- A06 Documents stored persistently with versions; forms collect public submissions into the leads inbox.
- A07 Firm policy controls and workflow templates: email, task, form request and status steps, waits for completion; changes observable.
- A08 Public website submission through same business rules. Errors visible, persistence verified across restart.
- A09 Create/reset/clone isolated worlds with realistic seed or empty state; reset preserves access while restoring configured starting state; no cross-world agent access. A controller-only Reset demo button beside Refresh is visible in the dedicated website world. It confirms deletion then resets with empty seed, clears selected-record navigation, and returns to Overview. Other worlds/results are untouched; firm settings and base setup return to defaults. Advanced reset defaults to empty, with realistic samples opt-in.
- A10 Scenario controller with versioned private facts, predefined events, advanceable business clock, scheduled replies/staff changes and one-shot faults (before action, after-commit timeout, failed message).
- A11 Separate restricted agent account with HTTP and MCP tools; no access to private scenarios, control tables, faults, answer keys, evaluator or reset.
- A12 Text participant sessions with private persona facts, goals, distinct speaker turns, human role-play and a clearly labeled scripted simulator for deterministic tests. No claim that scripted actors measure natural-language intelligence.
- A13 At least 10 scenario variants and a reference runner that uses only public business APIs plus an explicitly declared scenario-specific reference policy. Reference runs are fixture validation, not AI benchmark scores.
- A14 Independent deterministic evaluator uses frozen state and event history; checks business outcomes, duplicates, collateral changes and permissions. Evidence links and failure dimensions. Judge uncertainty/human review recorded separately, never counted as an automatic pass.
- A15 Observer UI displays conversation, actions, state deltas and criterion results; exportable run artifacts; recording playback only for uploaded audio, labeled as such.
- A16 All browser mutations/read capabilities have API/CLI mapping through a machine-readable operation registry. Tests verify parity, permissions, persistence, concurrency/version conflicts, failure recovery, run isolation and positive/negative grading.
- A17 Scenario runs have immutable evaluation snapshots. New evaluations create result records; human reviews are appended, not edits to historical evidence. Stop/freeze prevents continued agent mutation.
- A18 No arbitrary code from scenario files, no raw SQL API, no file path traversal, escaped browser text, scoped opaque bearer tokens and local binding by default. Agents should run outside host filesystem with only their token and URL.

## Concrete data and operations
Business tables: contacts, leads, matters, notes, staff, tasks, messages, appointments, documents, escalations, forms, workflows, workflow_instances, conversations, turns. Tables have JSON documents with typed service validation, IDs, version, created/updated business timestamps, and foreign-reference checks.
Internal business tables: meta, events, idempotency, scheduled, faults. Not exposed to agents.
Control tables: worlds, grants, scenarios, runs, results, reviews. Never exposed via business record APIs.

Three roles: intake, attorney, observer; controller token owns lab administration. Intake can perform ordinary business operations but cannot accept attorney escalations or change policy/staff. Observer cannot mutate. Attorney can accept escalations. Public form endpoints can only create leads in the designated demo world.

UI/API/CLI all invoke the same operation registry and service layer. Generic resource operations use explicit entity allowlists and field schemas. Additional semantic operations handle conversion, message delivery, booking, workflow stepping and actor turns.

## Evaluation
Show a plain firm name for a single workspace, with no demo suffix for Harbor & Stone. Show a selector only for multiple ordinary firms. Present attempts (including legacy runs) numbered within each scenario, with mode and latest outcome. Inspect their current/frozen records and post-setup changes read-only from the attempt itself; never mutate the operator's manual firm. The standalone Lab at /lab shows record state alongside action history on each attempt URL, never in the manual firm's sidebar. Independent worlds, grants, clocks, snapshots and grades allow overlapping runs. Shared infrastructure includes the scenario catalog, control database and bounded worker pool. Keep unfiltered world enumeration for administrative compatibility and restricted agents scoped to their own attempt.
The Evaluation lab landing page highlights only the intake-only scenario and its attempts. The full library and old runs remain available in a closed disclosure. Starter attempts show conversion status and grader results, without caller controls. Scripted examples are distinguished from external-agent runs.
A watched intake opens before submission. The operator triggers Jamie’s simulated website form using the same validation and persistence path as the public website. Distinguish the website visitor, fixture script, and external agent, and follow live external changes. Grade against the original submitted values and before-attempt history. Non-interactive intake runs start with one fictional website submission, unrelated background records, and no prior contact for Jamie. Convert exactly once through the scoped agent account, preserving the submitted contact and accident fields. No callback, conversation, case acceptance, assignment, or outreach is required. Grade the linked lead/contact/matter and collateral writes against the original snapshot. Existing scenarios and historical runs retain their own contracts.

Pass requires all required programmatic criteria, not a favorable mean. Return passes/failures/uncertain dimensions individually. Never treat unavailable semantic judgment as a pass. Reference solutions demonstrate solvability. Broken runs are classified as environment errors where appropriate. Held-out scenario generation and expert validation are future research steps, not claims of this release.

## Verification plan
1. Unit/integration tests for each A requirement; temporary state directories only.
2. Golden reference solutions pass each scenario, do-nothing and deliberate bad states fail.
3. Permission and fault tests including post-commit timeout and safe retry.
4. Browser test public form -> lead conversion -> task/message/appointment -> run -> results.
5. CLI smoke tests against a real local server, OpenAPI and registry parity.
6. Restart server and verify data; reset one world and confirm other worlds/results unchanged.
7. Document exact results and limitations in VALIDATION.md before marking goal complete.
