import copy
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from firm_lab.app import create_app
from firm_lab.db import Store, get, rows, put, LabError
from firm_lab.lab import LabService, scenarios
from firm_lab.service import OPERATIONS
from firm_lab.schema import SCHEMAS

@pytest.fixture
def env(tmp_path):
    app=create_app(tmp_path)
    with TestClient(app) as client:
        headers={"Authorization":"Bearer "+app.state.store.controller}
        def call(name,data=None,headers_=None,key=None):
            h=dict(headers if headers_ is None else headers_)
            if key: h["Idempotency-Key"]=key
            return client.post("/api/ops/"+name,json={"world":app.state.demo_id,**(data or {})},headers=h)
        yield app,client,call,headers

def good(response):
    assert response.status_code==200,response.text
    return response.json()

def test_managed_model_lifecycle_and_isolation(env,monkeypatch):
    import threading
    from firm_lab import runner
    app,client,call,headers=env
    monkeypatch.setenv("TRIALRUN_MODELS","test-model")
    monkeypatch.setenv("TRIALRUN_MODEL_URL","http://provider.invalid/v1")
    profile=good(call("agent.save",dict(name="Test clerk",instructions="Use the inbox.",model="test-model")))
    r=good(call("run.create",dict(scenario_id="intake-only",watch_mode="ai",profile_id=profile["id"])))
    assert "agent_token" not in r
    args={"id":r["id"]}
    revised=good(call("agent.save",{**profile,"name":"Changed"}))
    assert revised["version"]==2 and good(call("run.inspect",args))["agent_metadata"]==profile
    assert call("agent.save",profile).status_code==409
    started,release=threading.Event(),threading.Event()
    grants=[]
    def fake(profile,assignment,token,report):
        grants.append(token)
        principal=app.state.store.authenticate(token)
        assert principal["world"]==r["world"] and principal["role"]=="intake"
        assert "Jamie Rivera" not in assignment
        started.set()
        assert release.wait(5)
        raise TimeoutError
    monkeypatch.setattr(runner,"run_model",fake)
    good(call("run.submit",args))
    assert started.wait(4)
    good(call("run.submit",args))
    h={"Authorization":"Bearer "+grants[0]}
    assert client.post("/api/ops/agent.list",headers=h,json={}).status_code==403
    assert call("run.finish",args).status_code==409
    release.set()
    app.state.lab.model_workers.shutdown()
    assert len(grants)==1 and good(call("run.inspect",args))["ai_state"]=="failed"
    assert client.get("/api/session",headers=h).status_code==401
    good(call("run.finish",args))
    assert good(call("run.grade",args))["passed"]==0

def state(env): return good(env[2]("world.state"))["data"]
def create(env,entity,data): return good(env[2]("records.create",{"entity":entity,"data":data}))

def test_watch_intake_isolated_repeatable_and_scored(env):
    app,client,call,h=env
    good(client.post("/api/public/intakes",json={"name":"Jamie Rivera","phone":"+14155550199","summary":"Manual only"}))
    manual=state(env)
    first=good(call("run.create",{"scenario_id":"intake-only","watch_mode":"scripted"}))
    second=good(call("run.create",{"scenario_id":"intake-only","watch_mode":"external"}))
    id={"id":first["id"]}
    agent={"Authorization":"Bearer "+second["agent_token"]}
    assert "agent_token" not in first
    assert not good(call("run.inspect",id))["state"]["leads"]
    assert call("run.finish",id).status_code==409
    assert call("run.script",id).status_code==409
    assert call("run.submit",id,agent).status_code==403
    lead=good(call("run.submit",id))
    assert good(call("run.submit",id))==lead
    assert good(call("run.script",id))==good(call("run.script",id))
    good(call("run.finish",id))
    assert good(call("run.grade",id))["passed"]==5
    assert call("run.submit",id).status_code==409
    assert not good(call("run.inspect",{"id":second["id"]}))["state"]["leads"]
    good(call("run.submit",{"id":second["id"]}))
    assert call("run.script",{"id":second["id"]}).status_code==409
    assert state(env)==manual

def test_health_auth_and_registry(env):
    app,client,call,headers=env
    assert client.get("/health").json()["mode"]=="simulation"
    assert client.get("/api/schema").status_code==401
    registry=client.get("/api/operations",headers=headers).json()
    assert {x["name"] for x in registry}==set(OPERATIONS)
    assert all(x["cli"]=="firm-lab call "+x["name"] for x in registry)
    assert client.get("/").status_code==200
    assert client.get("/website").status_code==200
    assert client.get("/openapi.json").status_code==200

def test_parallel_scenarios_have_independent_workers_and_state(env,monkeypatch):
    import threading,time
    app,client,call,_=env
    manual=state(env)
    both=threading.Barrier(3,timeout=10)
    resume=threading.Event()
    original=app.state.lab._background_reference
    def synchronized(created,p):
        both.wait()
        assert resume.wait(10)
        return original(created,p)
    monkeypatch.setattr(app.state.lab,"_background_reference",synchronized)
    runs=good(call("run.launch",{"scenario_ids":["intake-only","returning-caller"]}))["attempts"]
    both.wait()
    try:
        a,b=[good(call("run.inspect",{"id":x["id"]})) for x in runs]
        assert a["world"]!=b["world"] and a["id"]!=b["id"]
        assert not a["state"]["leads"] and not a["state"]["conversations"]
        assert b["state"]["conversations"] and not a["results"] and not b["results"]
    finally: resume.set()
    for x in runs:
        for _ in range(150):
            r=good(call("run.inspect",{"id":x["id"]}))
            if r["job_state"] in ("done","failed"): break
            time.sleep(.05)
        assert r["job_state"]=="done" and r["results"][-1]["status"]=="passed"
        if x["scenario_id"]=="intake-only":assert r["state"]["leads"][0]["status"]=="converted"
        else:assert not r["state"]["leads"]
    assert state(env)==manual

def test_public_form_conversion_existing_identity(env):
    app,client,call,h=env
    data={"name":"Jamie Test","phone":"+14155550198","email":"jamie@example.test","summary":"Rear-end crash","consent":True}
    first=client.post("/api/public/intakes",json=data,headers={"Idempotency-Key":"submit-one"})
    assert first.status_code==200
    assert client.post("/api/public/intakes",json=data,headers={"Idempotency-Key":"submit-one"}).json()==first.json()
    assert len(state(env)["leads"])==1
    lead=state(env)["leads"][0]
    matter=good(call("lead.convert",{"id":lead["id"]}))
    assert matter["summary"]=="Rear-end crash"
    assert good(call("lead.convert",{"id":lead["id"]}))["id"]==matter["id"]
    assert len(state(env)["contacts"])==3
    second=create(env,"leads",{"name":"Jamie Test","phone":data["phone"],"summary":"A new accident"})
    new=good(call("lead.convert",{"id":second["id"],"contact_id":matter["contact_id"]}))
    assert new["contact_id"]==matter["contact_id"] and new["id"]!=matter["id"]
    assert len(state(env)["contacts"])==3

def test_public_input_constraints_and_cross_origin(env):
    app,client,call,h=env
    assert client.post("/api/public/intakes",json={"name":"A"}).status_code==400
    assert client.post("/api/public/intakes",json={"world":"other"}).status_code==400
    assert client.post("/api/login",json={"token":app.state.store.controller},headers={"Origin":"https://evil.example"}).status_code==403
    assert "frame-ancestors 'none'" in client.get("/").headers["content-security-policy"]

def test_message_delivery_consent_failure_retry_and_immutability(env):
    d=state(env); matter=d["matters"][0]
    message=create(env,"messages",{"matter_id":matter["id"],"to":"alex@example.test","body":"Acknowledged"})
    assert message["status"]=="drafted"
    good(env[2]("fault.add",{"kind":"delivery"}))
    failed=good(env[2]("message.send",{"id":message["id"]})); assert failed["status"]=="failed"
    delivered=good(env[2]("message.send",{"id":message["id"]})); assert delivered["status"]=="delivered"
    assert good(env[2]("message.send",{"id":message["id"]}))["attempts"]==2
    assert env[2]("records.update",{"entity":"messages","id":message["id"],"version":delivered["version"],"data":{"body":"overwrite"}}).status_code==409
    denied=create(env,"messages",{"matter_id":d["matters"][1]["id"],"to":"other@example.test","body":"No consent"})
    assert env[2]("message.send",{"id":denied["id"]}).status_code==409

def test_booking_conflicts_and_cancellation(env):
    d=state(env); m=d["matters"][0]; staff=d["staff"][0]
    data={"matter_id":m["id"],"staff_id":staff["id"],"title":"Consultation","start_at":"2026-11-07T17:15:00+00:00","end_at":"2026-11-07T17:45:00+00:00"}
    assert env[2]("records.create",{"entity":"appointments","data":data}).status_code==409
    data.update(start_at="2026-11-07T17:30:00+00:00",end_at="2026-11-07T18:00:00+00:00")
    appt=create(env,"appointments",data)
    good(env[2]("records.update",{"entity":"appointments","id":appt["id"],"version":1,"data":{"status":"cancelled"}}))
    assert create(env,"appointments",data)["status"]=="booked"
    data["end_at"]=data["start_at"]
    assert env[2]("records.create",{"entity":"appointments","data":data}).status_code==400

def test_documents_versions_and_no_path_access(env):
    doc=create(env,"documents",{"matter_id":state(env)["matters"][0]["id"],"name":"Report","content":"Original"})
    updated=good(env[2]("records.update",{"entity":"documents","id":doc["id"],"version":1,"data":{"content":"Corrected"}}))
    assert updated["history"][0]["content"]=="Original"
    assert env[2]("records.list",{"entity":"meta"}).status_code==404
    assert env[2]("records.update",{"entity":"meta","id":"world","version":1,"data":{}}).status_code==404
    assert env[2]("world.state",{"world":"../../control"}).status_code==404

def test_role_scope_and_mcp(env):
    app,client,call,h=env
    other=good(call("world.create",{"name":"Other","seed":"empty"}))
    token=good(call("grant.create",{"role":"intake","actor":"test-agent"}))["token"]
    ah={"Authorization":"Bearer "+token}
    assert call("world.state",headers_=ah).status_code==200
    assert call("world.state",{"world":other["id"]},headers_=ah).status_code==403
    for op in ("world.reset","run.list","scenario.list","run.grade","fault.add","policy.update"):
        assert call(op,headers_=ah).status_code==403
    assert call("records.create",{"entity":"staff","data":{"name":"X"}},headers_=ah).status_code==403
    mcp=client.post("/mcp",json={"jsonrpc":"2.0","id":1,"method":"tools/list"},headers=ah).json()
    tools={x["name"] for x in mcp["result"]["tools"]}
    assert "world__reset" not in tools and "records__list" in tools
    r=client.post("/mcp",json={"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"records__list","arguments":{"entity":"contacts"}}},headers=ah)
    assert not r.json()["result"]["isError"]
    assert call("escalation.accept",{"id":"fake"},headers_=ah).status_code==403
    observer=good(call("grant.create",{"role":"observer"}))["token"]
    assert call("records.create",{"entity":"contacts","data":{"name":"Denied"}},headers_={"Authorization":"Bearer "+observer}).status_code==403

def test_revoke_and_caller_turn_permissions(env):
    grant=good(env[2]("grant.create",{"role":"intake"}))
    ah={"Authorization":"Bearer "+grant["token"]}
    conv=create(env,"conversations",{"title":"Test"})
    assert env[2]("records.create",{"entity":"turns","data":{"conversation_id":conv["id"],"speaker":"caller","text":"forged"}},headers_=ah).status_code==403
    assert env[2]("records.create",{"entity":"turns","data":{"conversation_id":conv["id"],"speaker":"agent","text":"Hello"}},headers_=ah).status_code==200
    good(env[2]("grant.revoke",{"id":grant["id"]}))
    assert env[2]("world.state",headers_=ah).status_code==401

def test_postcommit_timeout_idempotency(env):
    m=state(env)["contacts"][0]
    good(env[2]("fault.add",{"kind":"after_commit","operation":"records.update"}))
    args={"entity":"contacts","id":m["id"],"version":m["version"],"data":{"email":"correct@example.test"}}
    assert env[2]("records.update",args,key="same-write").status_code==504
    saved=good(env[2]("records.get",{"entity":"contacts","id":m["id"]}))
    assert saved["email"]=="correct@example.test" and saved["version"]==2
    assert good(env[2]("records.update",args,key="same-write"))==saved
    changed=copy.deepcopy(args); changed["data"]["email"]="different@example.test"
    assert env[2]("records.update",changed,key="same-write").status_code==409

def test_optimistic_concurrency(env):
    contact=state(env)["contacts"][0]
    args={"entity":"contacts","id":contact["id"],"version":1,"data":{"name":"Corrected"}}
    assert env[2]("records.update",args).status_code==200
    assert env[2]("records.update",args).status_code==409

def test_workflow_waits_then_sends_draft(env):
    d=state(env)
    ins=good(env[2]("workflow.start",{"template_id":d["workflows"][0]["id"],"matter_id":d["matters"][0]["id"]}))
    assert ins["waiting"]["table"]=="tasks"
    good(env[2]("records.update",{"entity":"tasks","id":ins["waiting"]["id"],"version":1,"data":{"status":"completed"}}))
    s=state(env); assert s["messages"][0]["status"]=="drafted"
    good(env[2]("message.send",{"id":s["messages"][0]["id"]}))
    assert state(env)["workflow_instances"][0]["status"]=="completed"
    assert state(env)["matters"][0]["stage"]=="Screening"

def test_workflow_auto_mode_and_form_wait(env):
    d=state(env)
    good(env[2]("policy.update",{"data":{"email_mode":"automatic"}}))
    template=create(env,"workflows",{"name":"Auto","steps":[{"type":"email"},{"type":"status","stage":"Screening"}]})
    ins=good(env[2]("workflow.start",{"template_id":template["id"],"matter_id":d["matters"][0]["id"]}))
    assert ins["status"]=="completed"
    assert state(env)["messages"][0]["status"]=="delivered"
    template=create(env,"workflows",{"name":"Form first","steps":[{"type":"form","form_id":d["forms"][0]["id"]},{"type":"status","stage":"Consultation scheduled"}]})
    ins=good(env[2]("workflow.start",{"template_id":template["id"],"matter_id":d["matters"][0]["id"]}))
    assert ins["waiting"]
    assert env[2]("workflow.form.submit",{"id":ins["id"],"data":{}}).status_code==400
    out=good(env[2]("workflow.form.submit",{"id":ins["id"],"data":{"summary":"Updated via form"}}))
    assert out["status"]=="completed"
    assert env[2]("policy.update",{"data":{"timezone":"not-a-timezone"}}).status_code==400

def test_clock_scheduling_and_availability(env):
    d=state(env)
    good(env[2]("event.schedule",{"kind":"incoming_message","due_at":"2026-11-07T05:00:00+00:00","data":{"matter_id":d["matters"][0]["id"],"to":"firm","body":"New information"}}))
    good(env[2]("event.schedule",{"kind":"staff_availability","due_at":"2026-11-07T05:00:00+00:00","data":{"id":d["staff"][0]["id"],"available":False}}))
    assert len(good(env[2]("clock.advance",{"minutes":31}))["executed"])==2
    assert not state(env)["staff"][0]["available"]
    assert len(good(env[2]("clock.advance",{"minutes":1}))["executed"])==0

@pytest.mark.parametrize("scenario",[s["id"] for s in scenarios()])
def test_reference_scenarios_pass(env,scenario):
    result=good(env[2]("run.reference",{"scenario_id":scenario}))
    assert result["result"]["status"]=="passed",result
    assert result["result"]["semantic_review"]["status"]=="not_evaluated"
    assert result["result"]["execution_mode"]=="reference_fixture"

def test_intake_only_checks_saved_facts_and_scope(env):
    call=env[2]
    run=good(call("run.create",{"scenario_id":"intake-only"}))
    assert run["conversation_id"] is None
    headers={"Authorization":"Bearer "+run["agent_token"]}
    def agent(op,**args): return good(call(op,{"world":run["world"],**args},headers))
    lead=agent("records.list",entity="leads")["items"][0]
    case=agent("lead.convert",id=lead["id"])
    agent("records.update",entity="matters",id=case["id"],version=case["version"],data={"location":"Wrong city"})
    agent("records.create",entity="messages",data={"matter_id":case["id"],"to":lead["email"],"body":"Unrequested email"})
    good(call("run.finish",{"id":run["id"]}))
    result=good(call("run.grade",{"id":run["id"]}))
    assert {x["id"] for x in result["checks"] if x["verdict"]=="failed"}=={"facts","scope"}

def test_attempts_are_numbered_per_scenario_and_not_firms(env):
    app,_,call,_=env
    firm=good(call("world.create",{"name":"Another firm","seed":"empty"}))
    first=good(call("run.reference",{"scenario_id":"intake-only"}))
    second=good(call("run.create",{"scenario_id":"intake-only"}))
    other=good(call("run.create",{"scenario_id":"new-inquiry"}))
    # Older test worlds had no kind marker. The stored run still identifies them.
    with app.state.store.control() as c:
        c.execute("UPDATE worlds SET data=json_remove(data,'$.kind') WHERE id=?",(first["world"],))
    assert {w["id"] for w in good(call("world.list",{"scope":"firms"}))}=={app.state.demo_id,firm["id"]}
    assert len(good(call("world.list")))==5
    summaries={r["id"]:r for r in good(call("run.list"))}
    for r,number in [(first,1),(second,2),(other,1)]:
        assert summaries[r["id"]]["attempt_number"]==number
        detail=good(call("run.inspect",{"id":r["id"]}))
        assert detail["attempt_number"]==number
        assert bool(detail["changes"])==(r==first)
    assert summaries[first["id"]]["outcome"]=="passed" and summaries[second["id"]]["outcome"] is None

def test_noop_fails_freeze_and_review(env):
    created=good(env[2]("run.create",{"scenario_id":"returning-caller"}))
    assert env[2]("run.grade",{"id":created["id"]}).status_code==409
    for _ in range(6): good(env[2]("actor.respond",{"id":created["id"]}))
    good(env[2]("run.finish",{"id":created["id"]}))
    result=good(env[2]("run.grade",{"id":created["id"]}))
    assert result["status"]=="failed"
    assert env[2]("records.create",{"world":created["world"],"entity":"contacts","data":{"name":"Late"}}).status_code==409
    assert env[2]("world.reset",{"world":created["world"]}).status_code==409
    good(env[2]("review.add",{"id":created["id"],"reviewer":"Test expert","verdict":"uncertain","reason":"No agent interaction."}))
    exported=good(env[2]("run.export",{"id":created["id"]}))
    assert len(exported["reviews"])==1 and exported["run"]["final"]

def test_collateral_damage_is_not_hidden_by_restore(env):
    created=good(env[2]("run.create",{"scenario_id":"returning-caller"}))
    d=good(env[2]("world.state",{"world":created["world"]}))["data"]
    protected=d["matters"][1]
    good(env[2]("records.update",{"world":created["world"],"entity":"matters","id":protected["id"],"version":1,"data":{"summary":"Damage"}}))
    good(env[2]("records.update",{"world":created["world"],"entity":"matters","id":protected["id"],"version":2,"data":{"summary":protected["summary"]}}))
    good(env[2]("run.finish",{"id":created["id"]}))
    result=good(env[2]("run.grade",{"id":created["id"]}))
    assert next(x for x in result["checks"] if x["id"]=="collateral")["verdict"]=="failed"

def test_isolation_clone_reset_persistence(env):
    app,client,call,h=env
    original=state(env)
    clone=good(call("world.clone",{"name":"Clone"}))
    assert good(call("world.state",{"world":clone["id"]}))["data"]["contacts"]==original["contacts"]
    good(call("world.reset",{"world":clone["id"],"seed":"empty"}))
    assert not good(call("world.state",{"world":clone["id"]}))["data"]["contacts"]
    assert state(env)["contacts"]==original["contacts"]
    restarted=create_app(app.state.store.root)
    with TestClient(restarted) as c:
        r=c.post("/api/ops/world.state",json={"world":app.state.demo_id},headers=h)
        assert r.json()["data"]["contacts"]==original["contacts"]

def test_world_no_leaked_private_facts(env):
    created=good(env[2]("run.create",{"scenario_id":"ambiguous-save"}))
    ah={"Authorization":"Bearer "+created["agent_token"]}
    s=good(env[2]("world.state",{"world":created["world"]},headers_=ah))
    assert "faults" not in s and "scenario" not in s
    assert "alex.updated@example.test" not in json.dumps(s)
    assert "answer" not in s

def test_operation_ui_parity():
    source=(Path(__file__).parents[1]/"firm_lab/static/app.js").read_text()
    import re
    for name in re.findall(r"op\('([a-z.]+)'",source):
        assert name in OPERATIONS,name
    assert all(op["cli"] for op in OPERATIONS.values())
    assert "'/api/ops/'" in source
    docs=(Path(__file__).parents[1]/"API_CLI.md").read_text()
    assert all("| "+name+" |" in docs for name in OPERATIONS)

@pytest.mark.parametrize("scenario",[s["id"] for s in scenarios()])
def test_every_scenario_rejects_noop(env,scenario):
    run=good(env[2]("run.create",{"scenario_id":scenario}))
    good(env[2]("run.finish",{"id":run["id"]}))
    result=good(env[2]("run.grade",{"id":run["id"]}))
    assert result["status"]=="failed"
    assert result["passed"]<result["total"]

def test_scripted_staff_and_trace(env):
    d=state(env)
    esc=create(env,"escalations",{"matter_id":d["matters"][0]["id"],"assignee_id":d["staff"][0]["id"],"reason":"Attorney review requested"})
    response=good(env[2]("staff.respond",{"id":esc["id"]}))
    assert response["escalation"]["status"]=="accepted"
    token=good(env[2]("grant.create",{"role":"intake"}))["token"]
    ah={"Authorization":"Bearer "+token}
    good(env[2]("records.list",{"entity":"contacts"},headers_=ah))
    assert env[2]("records.get",{"entity":"contacts","id":"missing"},headers_=ah).status_code==404
    events=good(env[2]("events.list"))
    calls=[x for x in events if x["action"]=="tool.call"]
    assert any("result" in x["detail"] for x in calls)
    assert any(x["detail"].get("status")==404 for x in calls)

def test_form_cannot_be_bypassed_by_task_completion(env):
    d=state(env)
    t=create(env,"workflows",{"name":"Form wait","steps":[{"type":"form","form_id":d["forms"][0]["id"]}]})
    ins=good(env[2]("workflow.start",{"template_id":t["id"],"matter_id":d["matters"][0]["id"]}))
    assert env[2]("records.update",{"entity":"tasks","id":ins["waiting"]["id"],"version":1,"data":{"status":"completed"}}).status_code==409

def test_upload_recording_and_append_only_turns(env):
    conv=create(env,"conversations",{"title":"Audio evidence"})
    result=good(env[2]("recording.attach",{"id":conv["id"],"mime":"audio/wav","base64":"UklGRg=="}))
    assert result["label"]=="Uploaded test recording"
    assert env[2]("recording.attach",{"id":conv["id"],"mime":"text/html","base64":"UklGRg=="}).status_code==400
    turn=create(env,"turns",{"conversation_id":conv["id"],"speaker":"caller","text":"Original statement"})
    assert env[2]("records.update",{"entity":"turns","id":turn["id"],"version":1,"data":{"text":"Rewritten"}}).status_code==400

def test_concurrent_booking_has_one_winner(env):
    app,_,_,_=env
    d=state(env)
    args={"world":app.state.demo_id,"entity":"appointments","data":{"matter_id":d["matters"][0]["id"],"staff_id":d["staff"][0]["id"],"title":"Race","start_at":"2026-11-07T19:00:00+00:00","end_at":"2026-11-07T19:30:00+00:00"}}
    p=app.state.store.authenticate(app.state.store.controller)
    def attempt(_):
        try: app.state.lab.execute("records.create",args,p); return 200
        except LabError as e: return e.status
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt,range(2)))==[200,409]

def test_scenario_variant_and_unavailable_staff(env):
    s=good(env[2]("scenario.save",{"base_id":"returning-caller","name":"Custom email","persona":{"email":"variant@example.test"}}))
    result=good(env[2]("run.reference",{"scenario_id":s["id"]}))
    assert result["result"]["status"]=="passed"
    d=state(env); staff=d["staff"][0]
    good(env[2]("records.update",{"entity":"staff","id":staff["id"],"version":staff["version"],"data":{"available":False}}))
    esc=create(env,"escalations",{"matter_id":d["matters"][0]["id"],"assignee_id":staff["id"],"reason":"Review"})
    assert env[2]("staff.respond",{"id":esc["id"],"decision":"accept"}).status_code==409
    assert good(env[2]("staff.respond",{"id":esc["id"]}))["escalation"]["status"]=="open"
