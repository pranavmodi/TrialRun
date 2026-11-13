# TrialRun

TrialRun is an [MIT-licensed](LICENSE) personal injury firm simulator for evaluating AI agents on the work of a case. The first release focuses on intake and follow-up. Its workspace is inspired by Clio Grow; it is **not a Clio product or certified API emulator**.

Everything runs in this directory. No live Clio account, existing Intake Agent service, shared database, external email/SMS provider, or AI-provider account is required.

## Start

From this directory:

    uv sync --extra test
    uv run firm-lab serve

The default local address is http://127.0.0.1:8810.
Open the standalone Evaluation Lab at / or /lab, the manual practice workspace at /workspace, and the fictional PI website at /website.

In a second terminal, run:

    uv run firm-lab token

Paste the token into the workspace sign-in screen. This is the controller credential: do not give it to evaluated agents. Use Firm controls -> World controls & access -> Issue access token for a restricted intake, attorney, or observer account.

Without uv:

    python3 -m venv .venv
    .venv/bin/pip install -e '.[test]'
    .venv/bin/firm-lab serve

The first start creates a realistic demo world and a private .local/controller.token. Data persists in .local/. Never commit that directory.

For remote development, keep the service bound to loopback and forward the port:

    ssh -L 8810:127.0.0.1:8810 USER@SERVER

Open http://127.0.0.1:8810 on your own machine. Do not expose the service publicly without TLS, appropriate access controls, request limits, and an operational security review.

## What's included

- Grow-inspired leads inbox, separate contacts/matters, configurable pipeline, case facts, source tracking, custom fields and notes.
- Tasks, callbacks, attorney escalations and role-based acceptance.
- Local simulated email/SMS mailboxes: drafts, consent checks, delivery failure, retry and incoming messages.
- Staff availability and conflict-checked consultation booking.
- Case-linked text documents with version history.
- Configurable intake form and a fictional-firm website styled after Harbor & Stone’s PI Web demo. Photography and styles are served locally; the form uses TrialRun only.
- Workflow templates with task/form waits, draft or automatic local acknowledgments, and stage transitions.
- Conversations, scripted caller/staff fixtures, human role-play and uploaded audio playback.
- Independent worlds, clone/reset, a controlled business clock, scheduled external events and one-shot faults.
- Scenario runs with scoped agent tokens, frozen evidence, repeatable grading, expert-review annotations and JSON exports.
- A form-only intake conversion scenario plus thirteen broader fixtures, including repeat callers, new incidents, permission limits, failures and human changes.
- HTTP operations, a minimal MCP JSON-RPC tool endpoint, CLI parity, OpenAPI and an operation explorer.

## Manual end-to-end test

1. Open /website and click Load a fictional test example.
2. Submit. A private test reference appears; no real firm or recipient is contacted.
3. Sign in at /. Open Leads inbox and convert the lead to a contact and matter.
4. Open the matter. Create a callback task and draft a message.
5. Send locally. Verify its status is delivered in Communications.
6. Book a consultation in Calendar. Try an overlapping slot; it should be rejected.
7. Add a case document, edit it, and inspect the prior version.
8. Restart the server. Records remain.
9. Click **Reset demo** beside **Refresh** while viewing the website demo world. Confirm **Clear demo and start fresh** to remove all business records without adding samples. Cancel leaves everything unchanged. This restores basic staff, form, policy, workflow templates, and clock to defaults; access tokens, other worlds, and evaluation results remain untouched. The button is controller-only. Firm controls also offers a reset with a choice of empty or realistic sample data (empty is the default).

The public website always submits to the dedicated demo world. It does not silently switch to whatever run an operator is viewing.

In the lab’s **Attempts** table, click **View workspace** beside **View attempt**.
This shortcut, like **View attempt workspace** on the attempt page, opens the firm's read-only
inbox, pipeline, contacts and other records in a new tab. Follow an inquiry to
its case or contact. Open attempts update live; finished attempts use the saved
final snapshot. The practice firm and other attempts remain separate.

## Evaluate an agent

Evaluation lab opens on **Convert one website inquiry**. **Try scripted example**
opens a scenario page with the attempt’s live workspace state and action log side by side. Click **Submit Jamie’s website form**, then **Run scripted conversion**, then **Finish and evaluate**. Activity shows who made each change. Open the attempt URL in another tab or share it with another signed-in controller. No firm navigation is needed. No AI runs in the scripted example.
**Set up agent run** creates the same isolated intake test for your external
agent. Save its scoped token, submit Jamie’s form, connect the agent and watch its actions update live, then select
**Finish and evaluate**. The page shows the result and the evidence for each
check. Other scenarios and their run history are collapsed under **More scenarios
and other runs**.

Every run is a numbered attempt under its scenario. Attempt 1 and Attempt 2
start from the same scenario setup, not from the previous attempt. Open **View
attempt** to revisit its records and actions on the scenario page. The test never changes
your firm. The header shows Harbor & Stone as plain text when it is the only firm. A switcher appears only for multiple firms and never includes test attempts.

Choose **Run scenarios in parallel** in the library, select up to eight scenarios and click **Launch selected scenarios**. Up to four background scripts execute concurrently; additional jobs wait. Close a tab without stopping the work. Click **View attempt** for live records, actions and the final score. External-agent attempts can also overlap, each using its own token and agent process; the lab does not launch an LLM.

For those other scenarios:

1. Open Evaluation lab and choose Set up agent run on a scenario.
2. Copy the returned scoped token and assignment for the evaluated agent.
3. Connect that agent through HTTP, MCP, or a browser signed in with its scoped token.
4. Use Caller speaks for deterministic fixture speech, or Human role-play to supply natural caller messages. The agent writes its own turns and performs business operations.
5. Use **View attempt** under the scenario to inspect its activity; private scenario facts are visible only to the controller.
6. Use Finish and evaluate to freeze and grade the evidence.
7. Inspect each criterion and its evidence. Add an expert review if appropriate.

**Validate fixture is not an AI run.** It uses a scenario-specific reference policy to prove that the environment and programmatic checks can be satisfied. It never claims model intelligence or real-world success.

The semantic review status remains not_evaluated until a human review is separately recorded. A successful structural grade does not establish empathy, legal adequacy, or summary faithfulness.

## CLI and API

See API_CLI.md for the complete operation catalog and examples.

    uv run firm-lab operations
    uv run firm-lab schema
    uv run firm-lab call world.list
    uv run firm-lab call run.reference --json '{"scenario_id":"ambiguous-save"}'

Use FIRM_LAB_TOKEN (environment only) or --token-file for a scoped credential. FIRM_LAB_URL selects a server. JSON files are supported via --file. Keys are never required in shell arguments.

## Automated verification

    uv sync --extra test
    uv run playwright install chromium
    uv run pytest -q

Tests create temporary databases and a temporary browser-test server. They never reset the operator's demo world. Browser screenshots are generated in ignored artifacts/.

See SPEC.md for acceptance criteria and VALIDATION.md for verified results. ARCHITECTURE.md preserves the original broader design; release boundaries are defined in SPEC.md.

## Isolation and limitations

- SQLite database per world; a separate control DB stores private scenarios, grants and results.
- The API separates controller authority from world-scoped roles. Never run an adversarial evaluated agent with this application's filesystem access or controller credentials.
- External delivery is intentionally absent. delivered means a local simulated delivery, not SMTP/SMS acceptance.
- Text-first participants are scripted or human-controlled, not autonomous LLM people. Any model can connect as the evaluated agent through the documented interfaces.
- Recordings are explicitly uploaded artifacts, not automatically captured telephone calls.
- Documents are versioned text, not a full PDF/OCR/signature platform.
- Human review is supported; no uncalibrated LLM judge is silently treated as ground truth.
- Real-time calling, model-driven participant realism, automatic semantic judges, full vendor conformance and production hosting are follow-on capabilities.
- Scenario reset/snapshot changes are local only. Existing DocketSim, FilevineSim, Intake Agent and Clio configuration are unaffected.

## Design references

- [Clio Grow contact and quick-intake workflows](https://help.clio.com/hc/en-us/articles/40257491789467-Create-Contacts-in-Clio-Grow)
- [Clio Grow automated workflows](https://help.clio.com/hc/en-au/articles/17770743592219-Clio-Grow-Automated-Workflows)
- [Clio Grow public API reference](https://docs.developers.clio.com/clio-grow/api-reference/)
- [AppWorld state-based evaluation](https://github.com/StonyBrookNLP/appworld)
- [Mercor Archipelago environment separation](https://github.com/Mercor-Intelligence/archipelago)

These are design references, not dependencies or claims of equivalent behavior.
## Hosted access

Open [TrialRun Evaluation Lab](https://trialrun.getpossibleminds.com/lab) or the
[manual workspace](https://trialrun.getpossibleminds.com/workspace). No SSH
tunnel is needed. The controller signs in with the private server-side token
and should keep it in a password manager. Do not give it to evaluated agents.

The service and Nginx configurations are in `deploy/`. The server runs one
loopback application process as the dedicated `trialrun` user. systemd starts
it on boot; Nginx terminates TLS and gates the simulated website, APIs and MCP
with the existing session cookie or bearer token. Only the sign-in screens,
static assets and login endpoint are publicly reachable without a token.

To reproduce this deployment, use the existing checkout at
`/home/pranav/pi-firm-agent-lab`, provision the service user, and run
`UV_PROJECT_ENVIRONMENT=/opt/trialrun-venv uv sync --frozen --no-dev --python /usr/bin/python3`.
Give only the service user access to the private `.local` data directory.
Install the service in `/etc/systemd/system/`, reload systemd and enable it.
Issue a certificate for the DNS name before enabling the TLS server block;
install the executable certificate reload hook in
`/etc/letsencrypt/renewal-hooks/deploy/`. Never run two processes against the
same data directory or interrupt an active evaluation for deployment.
