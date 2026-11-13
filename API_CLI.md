# API, MCP and CLI reference

All product operations use the same registry and service layer. The UI calls POST /api/ops/{operation}; the CLI calls that same route. No CLI business action writes directly to a database.

## Authentication and transport

- Controller credential: .local/controller.token, generated on first server start.
- Agent credentials: issue using grant.create. Grants bind role, actor and one world.
- HTTP: Authorization: Bearer TOKEN.
- Browser: POST /api/login with {"token":"TOKEN"} establishes an HttpOnly SameSite=Strict session. POST /api/logout clears it.
- GET /api/session reports role and scope. GET /api/operations returns the permitted operation registry; GET /api/schema returns entity fields.
- GET /health and /website are public. GET /openapi.json documents HTTP routes.
- HTTP writes may include Idempotency-Key. Same key/actor/arguments returns the earlier successful response. Reuse with a different request returns 409.
- JSON errors have an error string. Typical codes: 400 validation, 401 unauthenticated, 403 role/scope violation, 404 absent record, 409 state/version conflict, 504 injected timeout.
- All business timestamps are ISO 8601 with timezone. The initial business clock is 2026-11-07T04:30:00+00:00 (Friday evening in California).
- All IDs are opaque strings. Never infer an ID from a display name.

## CLI syntax

    firm-lab [--url URL] [--token-file PATH] call OPERATION --json '{"world":"WORLD_ID",...}'
    firm-lab call OPERATION --file arguments.json
    firm-lab call OPERATION --json '{...}' --key UNIQUE_REQUEST_KEY
    firm-lab operations
    firm-lab schema
    firm-lab submit --json '{"name":"Jamie Rivera","phone":"+14155550199","email":"jamie@example.test","summary":"Rear-ended at a traffic light","consent":true}'

FIRM_LAB_URL and FIRM_LAB_TOKEN_FILE set defaults. FIRM_LAB_TOKEN overrides the token file. Avoid putting tokens into command-line arguments or committing them.

A world-scoped agent may omit world; it defaults to its assigned world. A controller must supply world for business operations. In the catalog, C means controller, I intake, A attorney, O observer.

## Operation catalog

Every operation has CLI form: firm-lab call OPERATION --json 'ARGUMENTS'.

| Operation | Roles | Arguments beyond world | Behavior |
|---|---|---|---|
| world.list | C | scope optional | List all worlds (default); `scope: "firms"` returns ordinary firms only. The UI displays a plain name for one firm and a selector for multiple firms. Evaluation attempts are excluded. |
| world.create | C | name, seed: realistic or empty | Create isolated world |
| world.reset | C | seed optional | Reset demo/ordinary world; run worlds are protected. Header Reset demo uses explicit seed=empty on the website demo world. |
| world.clone | C | name optional | Copy business state to a new independently writable world |
| grant.create | C | role, actor optional | Return a scoped token once |
| grant.list | C | none | List grants without token hashes |
| grant.revoke | C | id | Revoke scoped access |
| world.state | C/I/A/O | none | Read business data, clock and policy; no private scenario/fault data |
| schema.get | C/I/A/O | none | Read entity field constraints through HTTP, MCP or CLI |
| records.list | C/I/A/O | entity, query, matter_id, offset, limit | Search with pagination (max 200) |
| records.get | C/I/A/O | entity, id | Read a record |
| records.create | C/I/A | entity, data | Create a typed record; configuration tables require C |
| records.update | C/I/A | entity, id, version, data | Optimistic update; dedicated state transitions protected |
| lead.convert | C/I/A | id, contact_id optional, matter_id optional | Create/reuse contact; create matter or add existing-matter note |
| lead.ignore | C/I/A | id | Ignore an unconverted lead |
| message.send | C/I/A | id | Deliver locally or retry; consent required for external-facing channels |
| escalation.accept | C/A | id | Record attorney acceptance |
| staff.respond | C | id, decision: accept or defer optional, conversation_id optional | Scripted attorney response respecting availability |
| policy.update | C | data | Update firm policy and stages; cannot remove occupied stages |
| events.list | C/I/A/O | record_id optional | Audit events; agents do not see controller fault events |
| clock.advance | C | minutes | Advance virtual time and execute due external events |
| event.schedule | C | kind, due_at, data | Schedule incoming_message or staff_availability |
| controller.inspect | C | none | Inspect scheduled events and injected faults |
| fault.add | C | kind, operation optional | Inject before, after_commit or delivery failure |
| workflow.start | C/I/A | template_id, matter_id | Snapshot and start template |
| workflow.form.submit | C/I/A | id (instance), data | Store requested form answers and advance |
| recording.attach | C | id (conversation), mime, base64 | Attach up to 5 MB of test audio |
| scenario.list | C | none | Scenario catalog including controller-private facts |
| scenario.save | C | base_id, name, description, persona, options | Create a new scenario variant, preserving old version |
| run.launch | C | scenario_ids | Start 1–8 independent scripted attempts, return IDs immediately. Four concurrent server workers; inspect job_state via run.list or run.inspect. |
| run.create | C | scenario_id, agent_metadata, watch_mode optional | Create an isolated attempt. For intake-only, watch_mode scripted or external starts before website submission. Only external setup returns an agent token. |
| run.list | C | none | Run summaries with scenario ID, per-scenario attempt number and most recent grade outcome (null before grading). |
| run.submit | C | id | Simulate the visitor submitting the form to this watched intake. Safe to retry. |
| run.script | C | id | Convert the submitted inquiry using the scoped reference policy; scripted attempts only. Safe to retry. |
| run.inspect | C | id | Read-only attempt number, state, business-record changes since setup, results and reviews; finished attempts use frozen evidence. |
| actor.respond | C | id (run), text optional | Next scripted caller turn or human role-play |
| run.finish | C | id | Freeze business state and evaluation evidence |
| run.grade | C | id | Append deterministic structural evaluation of frozen evidence |
| review.add | C | id (run), reviewer, verdict, reason | Append human review (pass/fail/uncertain) |
| run.export | C | id | Export scenario, snapshots, events, results and reviews |
| run.reference | C | scenario_id | Create/run/grade a reference fixture; not AI performance |

## Entity fields

Read the complete machine-readable schema using firm-lab schema. Records include id, version, created_at and updated_at.

- contacts: name, email, phone, source, tags, custom_fields.
- leads: name, phone, email, summary, injury, incident_date, location, source, consent. status and matter_id are managed by lead operations.
- matters: title, contact_id, stage, matter_type, summary, injury, incident_date, location, priority, severity, shopping, owner_id, consent, custom_fields.
- notes: matter_id, body.
- staff (controller writes): name, role, available, available_from, available_until.
- tasks: matter_id, title, assignee_id, due_at, kind, status.
- messages: matter_id, channel, to, subject, body; controller may create direction=inbound. Delivery status/attempts are managed by message.send. Sent/failed messages cannot be rewritten.
- appointments: matter_id, staff_id, title, start_at, end_at, status.
- documents: matter_id, name, content, kind. Content edits retain earlier text in history.
- escalations: matter_id, reason, assignee_id (attorney). Acceptance uses escalation.accept.
- forms (controller writes): name, fields array with key, label, required. Supported keys: summary, injury, incident_date, location; summary must exist.
- workflows (controller writes): name, steps array.
- conversations: title, optional matter_id; audio attachment uses recording.attach.
- turns: conversation_id, speaker, text. Evaluated agents may create only their own agent turns; turns cannot be updated.
- workflow_instances: read-only execution state.

### Workflow step examples

    {"type":"task","title":"Review inquiry","kind":"review","hours":1}
    {"type":"form","form_id":"FORM_ID"}
    {"type":"email","subject":"Acknowledgment","body":"We received your inquiry."}
    {"type":"status","stage":"Screening"}

Task steps wait for completion. Form steps require workflow.form.submit rather than manually completing their tracking task. Email steps use policy templates when omitted. Draft mode waits for local delivery; automatic mode sends only when contact permission exists. Failure keeps the message available for retry.

## Common examples

Create and convert a lead:

    firm-lab call records.create --json '{"world":"WORLD","entity":"leads","data":{"name":"Jamie Rivera","phone":"+14155550199","summary":"Rear-end collision","consent":true}}'
    firm-lab call lead.convert --json '{"world":"WORLD","id":"LEAD_ID"}'

To perform the same empty reset as the workspace's **Reset demo** button, use the
demo world ID returned by `world.list` (the dedicated website world is also
reported by `GET /api/session` as `demo_world`):

    firm-lab call world.reset --json '{"world":"DEMO_WORLD_ID","seed":"empty"}'

This deletes business records and restores base staff, form, policy, workflow
templates, and clock defaults. It preserves access and does not reset other
worlds or historical evaluations. The CLI applies immediately; the UI shows a
confirmation dialog without requiring a typed phrase.

Update with concurrency protection:

    firm-lab call records.update --key contact-correction-1 --json '{"world":"WORLD","entity":"contacts","id":"CONTACT_ID","version":1,"data":{"email":"correct@example.test"}}'

Create a callback:

    firm-lab call records.create --json '{"world":"WORLD","entity":"tasks","data":{"matter_id":"MATTER_ID","title":"Call tomorrow morning","kind":"callback","due_at":"2026-11-07T17:30:00+00:00"}}'

Inject an ambiguous successful write:

    firm-lab call fault.add --json '{"world":"WORLD","kind":"after_commit","operation":"records.update"}'

The next matching write commits, then returns 504. Inspect state or retry with the same idempotency key; do not blindly create another record.

Schedule a reply:

    firm-lab call event.schedule --json '{"world":"WORLD","kind":"incoming_message","due_at":"2026-11-07T05:00:00+00:00","data":{"matter_id":"MATTER_ID","to":"intake desk","body":"Please call me in the morning.","channel":"sms"}}'
    firm-lab call clock.advance --json '{"world":"WORLD","minutes":31}'

Create and observe an external-agent run:

    firm-lab call run.create --json '{"scenario_id":"intake-only","agent_metadata":{"name":"my-agent","model":"record-the-exact-model-version"}}'

For the form-only scenario, the scoped agent can list leads and call `lead.convert` on the new lead. No conversation or follow-up actions are needed. The controller calls `run.finish` then `run.grade` with the run ID. To test the grader without an AI agent, run:

    firm-lab call run.reference --json '{"scenario_id":"intake-only"}'

Parallel example: `firm-lab call run.launch --json '{"scenario_ids":["intake-only","returning-caller"]}'`. Each returned ID has a controller-only observer at `/lab/attempts/ID` (authenticated data via `run.inspect`). Navigation never starts, stops or switches a worker. Interrupted jobs are marked on service restart; launch a fresh attempt to retry.

UI equivalents: **Try scripted example** → `run.create` with `watch_mode: "scripted"`; **Set up agent run** uses `watch_mode: "external"`. Next call `run.submit` with the run ID. For scripted runs call `run.script`; otherwise connect your own agent. Use `run.inspect` between steps to see the current records and events since `timeline_start`. The noninteractive `run.reference` still runs the whole fixture at once; **Finish and evaluate** → `run.finish`, then `run.grade`. `run.list` includes `scenario_id` so the dashboard or a CLI client can group new and historical attempts.
    firm-lab call run.inspect --json '{"id":"RUN_ID"}'
    firm-lab call actor.respond --json '{"id":"RUN_ID","text":"My email has changed. Can you update it?"}'
    firm-lab call run.finish --json '{"id":"RUN_ID"}'
    firm-lab call run.grade --json '{"id":"RUN_ID"}'
    firm-lab call run.export --json '{"id":"RUN_ID"}'

## MCP tool endpoint

POST /mcp with the same bearer credential. Supported methods: initialize, notifications/initialized, tools/list, tools/call. Operations map dots to double underscores, e.g. records.list -> records__list.

    {"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"records__list","arguments":{"entity":"contacts","query":"Alex"}}}

Only allowed business operations are exposed, never lab-control operations. Tools return JSON text content and isError on domain failures. This is a minimal stateless JSON-RPC endpoint; resumable sessions, SSE and every MCP capability are not claimed.

## Public website submission

GET /api/public returns the demo firm's form configuration.
POST /api/public/intakes accepts name, phone, email, summary, injury, incident_date, location, consent.
It returns reference and message. It always targets the dedicated demo world.
The CLI equivalent is firm-lab submit. Idempotency-Key is supported.

## Browser and transport support

The browser uses the registry plus GET /api/schema. Login/logout are session transport helpers rather than business operations; the CLI uses bearer tokens instead. Source-of-truth operation definitions are in firm_lab/service.py and firm_lab/lab.py. Tests assert that this catalog contains every registered operation.
### Hosted endpoint

Use `--url https://trialrun.getpossibleminds.com` for remote CLI access.
Authenticated API and MCP clients use their existing role-scoped bearer
tokens. The hosting gateway also requires a session or bearer token for the
simulated website and public-intake endpoint; anonymous CLI `submit` remains
a local demo command. The gateway does not change operation permissions.
### Read-only attempt workspace

`/lab/attempts/<run-id>/workspace` displays the controller-only `run.inspect`
projection. Each lab attempt row links directly to this route. The same live or frozen records are available from
`POST /api/ops/run.inspect` or `firm-lab call run.inspect --json '{"id":"<run-id>"}'`
under `state`. Navigation in the view does not call business operations.
