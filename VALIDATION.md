# Release 1 validation report

Date: 2026-11-10
Scope: SPEC.md release 1. This is not certification of real Clio Grow behavior.

## Results

- Full automated suite: **50 passed**.
- All 13 scenario reference policies pass their structural criteria.
- All 13 do-nothing variants fail, rather than being rewarded for leaving state unchanged.
- Chromium browser acceptance: website submission, conversion, callback, local email delivery, consultation booking, scenario execution, result inspection and uploaded-audio decoding.
- Desktop and mobile screenshots generated in ignored artifacts/ and visually inspected during development.
- CLI smoke checks run against a real temporary HTTP server, using operations and world.list.
- Local startup via uv run --frozen firm-lab serve verified with GET /health and a CLI request.
- Persistent data survives application recreation; clone/reset cannot change another world.
- Package source distribution and wheel build successfully. Wheel includes browser assets and no runtime state, credentials or screenshots.
- JavaScript syntax checks and Python compilation pass.
- One upstream test-client deprecation warning remains; it does not affect test outcomes.

## Acceptance evidence

| Spec | Evidence |
|---|---|
| A01 Standalone startup/UI/API/CLI | test_health_auth_and_registry; test_browser_workflow; local startup and wheel build |
| A02 Grow-inspired CRM | test_public_form_conversion_existing_identity; new-inquiry and new-incident reference scenarios |
| A03 Tasks/escalations/roles | urgent-handoff fixture; test_role_scope_and_mcp; test_scripted_staff_and_trace |
| A04 Simulated communications | test_message_delivery_consent_failure_retry_and_immutability; browser delivery; scheduled-reply fixture |
| A05 Calendar and availability | test_booking_conflicts_and_cancellation; test_concurrent_booking_has_one_winner; staff-unavailable fixture |
| A06 Versioned documents/forms | test_documents_versions_and_no_path_access; public submission and workflow form tests |
| A07 Policies and workflows | test_workflow_waits_then_sends_draft; test_workflow_auto_mode_and_form_wait; test_form_cannot_be_bypassed_by_task_completion |
| A08 Website and persistence | test_browser_workflow; test_isolation_clone_reset_persistence |
| A09 Worlds, resets and isolation | test_isolation_clone_reset_persistence; test_role_scope_and_mcp |
| A10 Controller, events and faults | test_clock_scheduling_and_availability; test_postcommit_timeout_idempotency; transient/delivery failure fixtures |
| A11 Agent interfaces/private boundary | test_role_scope_and_mcp; test_revoke_and_caller_turn_permissions; test_world_no_leaked_private_facts; examples/agent_client.py |
| A12 Participants/role-play | actor.respond and staff.respond; no-op conversation test; test_scripted_staff_and_trace |
| A13 Scenario suite/reference runner | test_reference_scenarios_pass, parameterized across all 13 scenarios |
| A14 Independent grading | test_every_scenario_rejects_noop; test_collateral_damage_is_not_hidden_by_restore; explicit semantic-review uncertainty |
| A15 Observer/export/audio | browser evaluation and audio checks; test_noop_fails_freeze_and_review; recording and append-only turn test |
| A16 UI/API/CLI parity | test_operation_ui_parity checks UI calls and documented registry coverage; browser CLI smoke |
| A17 Frozen evidence/reviews | test_noop_fails_freeze_and_review; frozen writes/reset rejected; append-only review records |
| A18 Isolation/security | scope/revocation/role tests, cross-origin rejection, schema/table allowlists, record version checks, protected transcript writes |

## Verified end-to-end paths

### Human-operated firm

Public website -> persisted lead -> contact/matter conversion -> callback task -> acknowledgment draft -> local delivery -> consultation booking.

### Evaluation lab

Private scenario -> isolated seeded world -> scoped agent token -> participant conversation and tool actions -> frozen final state -> independent structural checks -> evidence report -> optional human review.

### Failure recovery

A mutation can commit and then return an injected 504. Retrying the same request with its idempotency key returns the saved response without repeating the mutation. A pre-action fault does not apply the business change. Message delivery failures remain visible and retryable.

### Negative behavior

Unchanged state does not satisfy the assignment. Wrong-record modifications remain detectable in history even if the final value is restored. An agent cannot access another world, change firm configuration, forge caller turns, inspect private scenario data, accept an attorney handoff as an intake user, reset a run, or mutate frozen evidence.

## Reset button verification — 2026-11-11

All 50 tests passed after adding the prominent empty-demo reset. The Chromium
workflow verifies visibility in the website demo world, cancel without deletion,
confirmed deletion of all business records, retained basic setup, navigation back
to Overview, unchanged other-world records, and hiding the shortcut in a run world.
Tests use a temporary database and do not reset the user's demo. JavaScript syntax
and Git whitespace checks passed. The existing Starlette/httpx deprecation warning
remains unrelated to this change.

## Deliberate limits; not represented as completed capabilities

Scenario-centered navigation (2026-11-12): 54 tests passed, including per-scenario numbering,
latest grade summaries, legacy test-world filtering, visibility of separately created firms,
and read-only record inspection. Browser tests cover passed and failed attempts while the
demo remains selected. A read-only live check found one selectable firm and both older attempts preserved.

Intake-only UI verification (2026-11-12): all 53 tests passed. Chromium verified that only the starter scenario is initially visible, its scripted conversion scores 5/5, an untouched external run scores 0/5, and the older scenarios remain accessible. The API negative test changes the location and drafts an unrequested message; both checks fail. Testing used temporary worlds. The live service was checked read-only for the installed scenario and updated UI.

- No live Clio integration or API-conformance certification; this is a Grow-inspired application.
- No real outbound email/SMS, phone calls, browser voice or automatic audio capture.
- Text participants are scripted fixtures or human role-play. No autonomous LLM participant has been deployed or tested.
- No model-generated semantic grades or PI-expert calibration have been performed. Structural pass is not a judgment of empathy, clinical/legal accuracy, or conversion effectiveness.
- The injury-update structural criterion checks that a new report was stored, not its semantic fidelity; that requires independent review.
- Documents are versioned text. Full PDF/OCR/e-signature workflows are outside release 1.
- External-agent model cost is unknown unless instrumented by that agent's harness. Reports show tool-call counts and elapsed run time, not invented token costs.
- Dockerfile is provided but Docker was unavailable on this host, so container execution was not tested. The local Python application and distributable wheel were tested.
- No production hosting, load test, adversarial-model sandbox certification, or long-term deployment readiness is claimed.
