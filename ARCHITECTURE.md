# Simulated PI Firm: Agent Evaluation Environment

Status: Proposed architecture; not an implemented system.
Date: 2026-11-10

## 1. Purpose and boundaries

Build a small, functioning personal-injury law-firm workspace, surrounded by a test controller and an independent evaluator. AI agents perform realistic intake and follow-up work inside it, and the evaluator checks what actually happened.

Our Intake Agent is one possible participant, not part of the environment itself. Other agents must be able to attempt the same work through supported interfaces.

The applications actually store records, deliver messages into test mailboxes, schedule appointments, and enforce permissions. The fictional elements are the people, cases, documents, and business events. Passing requires evidence of completed work, not merely a convincing conversation or a claim of completion.

Evaluation measures an agent. It does not itself train or update the underlying model. Training is a separate future capability.

## 2. The simulated firm is working software

The initial implementation should use a modular backend, PostgreSQL, a background event worker, a browser dashboard, and isolated execution containers. A separate microservice for every feature is unnecessary initially.

| Subsystem | Working functionality | Main stored records |
|---|---|---|
| Intake CRM | Search, create, update, assign, change status, manage tasks | People, incidents, intakes, assignments, tasks, notes |
| Communications | Email/SMS threads, drafts, delivery failures, replies | Messages, recipients, delivery events, conversations |
| Calendar | Availability, bookings, cancellations, callback windows | Staff schedules, appointments, reservations |
| Documents | Upload, retrieve, version, associate with cases | Documents, versions, case associations |
| Staff workspace | Escalations, approvals, handoffs, internal messages | Staff, roles, escalation requests, decisions |
| Firm knowledge | Readable policies and operating instructions | Qualification policies, escalation rules, office hours |

The CRM owns intake status. Communications owns delivery state. The calendar owns availability. Durable events connect these subsystems, allowing realistic intermediate states such as a successful CRM update whose notification has not yet arrived.

### Existing components to assess for reuse

- DocketSim: initial intake workspace.
- PIWeb: website-form and browser-call entry points.
- Call Lab: voice transport and recording machinery.
- FilevineSim: transition from accepted intake to matter management.

These are reuse candidates, not verified implementation commitments. Audit their current code and behavior before choosing integration boundaries. The environment must remain independent of the particular agent being evaluated.

Use working software where practical, stateful vendor simulators where controlled resets matter, and separate integration-conformance checks against real vendor sandboxes. Similar-looking endpoints alone do not establish vendor fidelity.

## 3. Run isolation and reproducible starting state

Every run starts from a versioned firm snapshot. For example:

> Harbor & Stone, Friday at 8:30 p.m. Two intake staff are off duty. An attorney is on call. Existing prospects, open follow-ups, older closed inquiries, and tomorrow's calendar commitments are already present.

Each run gets an isolated database or database namespace, document storage, message store, and restricted credentials. Agents cannot access other runs.

The snapshot contains realistic background records, not only the target case. Otherwise, finding the correct person becomes artificially easy.

A reset restores:

- Database records.
- Documents and messages.
- Scheduled events.
- Staff availability.
- Simulated time.
- Firm and agent configuration versions.

A realistic reset restores a known workplace; it does not necessarily empty the workplace. A shared demo-wide reset is insufficient for concurrent independent evaluations.

## 4. Scenario packages and information boundaries

Each scenario is a versioned package with explicit access boundaries.

| Scenario element | Visibility |
|---|---|
| Assignment and firm policies | Agent |
| Existing CRM records and documents | Agent, subject to permissions |
| Caller's personal facts and objectives | Caller simulator |
| Staff member's knowledge and authority | That staff simulator |
| Scheduled events and injected failures | Test controller |
| Expected outcomes and prohibited changes | Evaluator |

### Example: returning caller and ambiguous write failure

**Agent assignment:** Handle tonight's incoming inquiries. Maintain accurate records, arrange requested follow-ups, and escalate according to firm policy.

**Caller's private situation:** Pranav called last week about the same accident. His email has changed. His pain has worsened. He wants someone to speak with him tomorrow morning.

**Hidden complication:** A different person has a similar name. The first CRM update commits successfully, but its response times out.

**Evaluator expectations:** Update the existing incident, preserve the unrelated person's record, capture the corrected email, arrange the callback, and avoid duplicate actions.

The agent never receives the expected record ID or hidden complication.

Ground truth can include uncertainty. If the caller does not know a fact, an acceptable result may be "unknown; follow up required." The evaluator must not reward invention merely because it fills a field.

## 5. Simulated people

People are separate role-limited participants, not extensions of the agent under evaluation.

### Prospects

Each prospect has an identity, circumstances, preferences, emotional context, and objective. For example:

> You are worried that nobody has taken your inquiry seriously. You want the firm to understand that your symptoms have changed and arrange a callback tomorrow. You previously contacted this firm about this accident.

The prompt does not prescribe every utterance or reveal which tools the intake agent should use. Stable identity facts remain independently grounded; a caller should not confirm an incorrect email simply because the agent sounds confident.

### Firm staff

An intake coordinator, attorney, or manager can respond to messages and take actions permitted by their role. The on-call attorney might ask for a summary, accept an escalation, request a later callback, or decline immediate availability without rejecting the case.

### External participants

Later scenarios may include medical providers, referral partners, or document custodians.

### Separation of language and state

Models generate human communication; application code governs actual effects. A simulated attorney saying "I accepted the handoff" does not change an assignment unless an authorized operation succeeds.

Participants have limited knowledge. Callers cannot see the CRM. Staff cannot read the evaluator's answer key. Their behavior should reflect observable state rather than private grading expectations.

Validate the people simulators separately for factual drift, leaked answers, unrealistic cooperation, and accommodation of agent mistakes. Success against one user-simulator model is not sufficient evidence of competence with real people.

## 6. The agent under evaluation

The agent runs separately and receives:

- A role, such as after-hours intake coordinator.
- Firm policies and its assignment.
- Credentials for permitted operations.
- Time and cost budgets.
- Incoming events such as calls or form submissions.

It receives no database-administrator access, private scenario facts, or grading code.

An illustrative tool surface is:

    search_contacts
    get_intake
    create_intake
    update_intake
    add_case_note

    get_staff_availability
    request_escalation
    create_callback_task
    book_appointment

    create_email_draft
    send_email
    read_message_thread

Tools invoke the same application services as the UI and CLI. They must not bypass business rules using direct database mutations.

### Access modes

- **API/MCP:** structured tool use.
- **Browser:** operating the actual web interface.
- **Hybrid:** whichever interfaces the real deployment permits.

Report these modes separately. Convenient API access and screenshot-only interaction are different evaluation conditions.

Our Intake Agent connects through an adapter. Other agents can connect through the same supported interfaces. The agent chooses how to investigate and conduct conversations; the environment does not impose a fixed question sequence.

## 7. Event controller and time

The scenario controller drives external events:

- **Time-based:** an attorney becomes unavailable at 9 p.m.
- **Action-based:** a prospect replies after receiving an email.
- **State-based:** staff review an escalation once sufficient information exists.
- **Fault events:** a tool times out, a message bounces, or another actor changes a record.

Events and conditions are defined before a run. The controller does not invent obstacles simply because the agent appears to be succeeding.

Every change produces an audit event with fields such as:

    event_id
    run_id
    business_timestamp
    wall_clock_timestamp
    actor
    action
    affected_record
    before_version
    after_version
    correlation_id
    result

This distinguishes an attempted save, a successful save, and a later overwrite by another actor.

### Two clocks

Business workflows use a controlled clock. A run can advance to tomorrow morning to test a callback without waiting a day.

Live voice preserves real elapsed time for interruptions, silence, latency, and disconnection behavior. Accelerated text tests must not be represented as measurements of real-time conversational performance.

## 8. Run lifecycle

For the returning-caller scenario:

1. **Create the workplace:** restore the snapshot and create restricted accounts.
2. **Start the agent:** provide its role and assignment, without hidden test details.
3. **Introduce the caller:** connect through text or voice.
4. **Allow investigation:** the agent asks questions, searches records, and determines whether this is the existing incident.
5. **Apply the configured complication:** the first update commits, but the response times out.
6. **Observe recovery:** the agent may inspect current state, retry safely, or seek help. No single exact recovery sequence is mandated.
7. **Continue the workflow:** acknowledgment, callback, and escalation as appropriate.
8. **Run later events:** advance business time to test due tasks and whether inappropriate follow-ups continue.
9. **Close and grade:** freeze relevant state, retain the trace, and run the evaluator.

A conversation ending is not necessarily a workflow ending. Some evaluations must continue until a promised follow-up should have occurred.

## 9. Independent evaluation

The evaluator runs outside the agent's workspace with read-only access to:

- Initial and final application state.
- Intermediate state changes.
- Tool requests and responses.
- Messages and transcripts.
- Audio for voice-specific criteria.
- Private scenario facts.
- The grading specification.

The agent cannot modify the grader or its evidence.

### Layer A: programmatic business checks

Verify objective facts:

- Correct intake updated.
- No duplicate created.
- Callback scheduled within the requested window.
- Unrelated records unchanged.
- Email state correctly distinguished as drafted, sent, or delivered.
- Permissions and required approvals respected.
- Retries did not create duplicate appointments or messages.

Final state alone is insufficient. An agent could disclose confidential information and then delete the message. Evaluate the event history as well.

These checks verify outcomes and constraints; they do not hardcode conversational wording or require a fixed path through the task.

### Layer B: evidence-based semantic grading

An independent judge model handles interpretive criteria:

- Summary faithfulness.
- Distinguishing uncertainty from established facts.
- Recognizing corrections to earlier answers.
- Considerate communication without unsupported promises.

Each judgment must cite evidence. Example:

    {
      "criterion": "summary_preserves_reported_symptoms",
      "verdict": "fail",
      "evidence": ["transcript:turn_18", "crm_update:event_42"],
      "reason": "The caller reported worsening pain, but the note says symptoms were unchanged."
    }

The judge can return insufficient evidence. Transcripts, documents, and agent outputs are evidence, not instructions to the judge.

### Layer C: expert calibration

PI intake specialists review sampled runs and disputed results. Measure agreement between automated and expert grading and revise ambiguous criteria.

A second LLM is not automatically a trustworthy evaluator. Expert review also checks whether scenarios represent real work rather than product-builder assumptions.

### Test the tests

Every scenario needs a known-valid solution. Deliberately wrong solutions must fail. Accept different valid methods, test graders for shortcuts, and keep held-out scenarios separate from examples used to improve the agent.

Repeat trials under comparable resource budgets. Restoring the same snapshot makes conditions comparable but does not guarantee identical model behavior.

## 10. Results and failure classification

Produce evidence-backed reports rather than only aggregate percentages. Example:

> **Failed: callback commitment not fulfilled.** Correct existing intake updated. Contact details corrected. No duplicates. Appropriate escalation created. However, the agent promised a callback tomorrow morning without creating a task or appointment.

| Dimension | Example evidence |
|---|---|
| Business outcome | Required callback exists or is missing |
| Data integrity | Correct case updated; unrelated records preserved |
| Authority and privacy | No unauthorized disclosure or action |
| Communication | Faithful explanation and appropriate handling |
| Reliability | Recovery from injected timeout |
| Efficiency | Time, tool calls, model cost, human interventions |

Critical failures remain visible rather than disappearing inside a high average score.

Classify agent failure, environment failure, and grading uncertainty separately. A broken test server is not an agent mistake.

## 11. Dashboard, API, and CLI

The operator dashboard has five areas:

- **Worlds:** inspect the firm, records, staff, and policies.
- **Scenarios:** author assignments, participant goals, events, and expectations.
- **Agents:** configure systems under evaluation.
- **Runs:** observe conversations, tool calls, state changes, and recordings.
- **Results:** investigate failures and compare repeated runs.

Every management operation must have documented API and CLI parity. UI, API, and CLI use the same service layer. Maintain an operation registry and parity tests so a feature is not considered complete when it exists only in the UI.

Illustrative commands below are proposed, not implemented:

    firm-lab run create --world harbor-stone-v1 --scenario returning-caller-timeout-v1 --agent intake-agent-v1
    firm-lab run inspect RUN_ID
    firm-lab run grade RUN_ID
    firm-lab run replay RUN_ID

Distinguish viewing a recorded execution from rerunning an agent. Preserve environment, scenario, agent, prompt, model, tool, and evaluator versions in run metadata.

## 12. Initial scope and implementation sequence

Start with one coherent firm's intake and follow-up desk, not every legal workflow. A first suite should contain approximately 10–15 expert-reviewed scenarios covering new inquiries, returning callers, contact corrections, escalation, follow-up, human takeover, and service failures.

Suggested sequence:

1. Audit existing components and select reuse boundaries.
2. Implement isolated worlds, snapshots, permissions, and audit events.
3. Deliver one complete text/API scenario with an independent agent adapter and programmatic evaluator.
4. Add private-role caller and staff simulators, event scheduling, and fault injection.
5. Add semantic grading and expert calibration.
6. Expand the scenario suite and repeated-run reporting.
7. Add browser and real-time voice variants, with channel-specific metrics.
8. Verify selected simulator behaviors against vendor sandboxes before making fidelity claims.

Medical-record collection, document/CRM reconciliation, and accepted-intake-to-matter workflows are later extensions.

## 13. Core architectural rule

**The firm supplies the world. The agent does the work. The evaluator independently checks the consequences.**

Preserve these boundaries so the environment can evaluate different agents fairly and so success represents completed business work rather than cooperation between an agent and its own test machinery.
