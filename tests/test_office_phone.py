import os
import socket
import subprocess
import sys
import time
from threading import Event
import httpx
import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright, expect
from firm_lab import phone
from firm_lab.app import create_app


def test_grounded_fields_never_copy_agent_or_unsaid_values(monkeypatch):
    monkeypatch.setenv("TRIALRUN_MODEL_URL","http://model.test/v1")
    client=httpx.Client
    def response(req):
        assert req.url.host=="model.test"
        raw='{"reply":"Where did it happen?","facts":{"name":"Robin Park","location":"Seattle","email":"made-up@example.test"}}'
        return httpx.Response(200,json={"choices":[{"finish_reason":"stop","message":{"content":raw}}]})
    monkeypatch.setattr(phone.httpx,"Client",lambda **kw:client(transport=httpx.MockTransport(response),**kw))
    reply,facts=phone.decide({"model":"local","timeout_seconds":10},[
        {"speaker":"agent","text":"Are you in Seattle?"},{"speaker":"caller","text":"No. My name is Robin Park."}],{})
    assert facts=={"name":"Robin Park"} and reply=="Where did it happen?"


def test_phone_failure_retry_isolation_and_freeze(tmp_path,monkeypatch):
    monkeypatch.setenv("TRIALRUN_MODELS","test");monkeypatch.setenv("TRIALRUN_MODEL_URL","http://invalid.test")
    app=create_app(tmp_path);entered=Event();release=Event()
    def fail(*args):
        entered.set();release.wait(3);raise ValueError("bad provider")
    monkeypatch.setattr(phone,"decide",fail)
    with TestClient(app) as c:
        h={"Authorization":"Bearer "+app.state.store.controller}
        def call(op,**args):return c.post("/api/ops/"+op,json=args,headers=h)
        def inspect(i):return call("run.inspect",id=i).json()
        def until(i,expected):
            for _ in range(100):
                r=inspect(i)
                if r["ai_state"]==expected:return r
                time.sleep(.025)
            pytest.fail(r["ai_state"])
        a=call("call.start").json()["id"];b=call("call.start",mode="demo").json()["id"]
        msg="My name is Sam Lake, my number is 555-0199. A van hit my bike."
        assert call("call.turn",id=a,sequence=0,text=msg).is_success and entered.wait(2)
        assert call("call.turn",id=a,sequence=0,text=msg).status_code==409
        release.set();r=until(a,"failed");assert [t["speaker"] for t in r["state"]["turns"]]==["agent","caller"]
        assert len(inspect(b)["state"]["turns"])==1
        monkeypatch.setattr(phone,"decide",lambda p,ts,f:("How are you feeling after the bike incident?",
            {"name":"Sam Lake","phone":"555-0199","summary":"A van hit my bike."}))
        assert call("call.retry",id=a).is_success
        r=until(a,"listening");assert len(r["state"]["leads"])==1 and r["state"]["turns"][-1]["speaker"]=="agent"
        assert call("call.end",id=a).is_success and call("call.turn",id=a,sequence=1,text="hello").status_code==409
        assert call("run.grade",id=a).json()["passed"]==3
        assert not inspect(b)["state"]["leads"]
        assert call("actor.respond",id=b,text="Injected").status_code==409
        def demo_reply(profile,turns,facts):
            assert turns[-1]["text"]==phone.JAMIE[0] and not facts
            return "Were you injured when you were hit?",{}
        monkeypatch.setattr(phone,"decide",demo_reply)
        assert call("call.turn",id=b,sequence=0,text="Not part of the demo").is_success
        demo=until(b,"listening")
        assert [t["text"] for t in demo["state"]["turns"]]==[phone.GREETING,phone.JAMIE[0],"Were you injured when you were hit?"]
        assert not demo["state"]["leads"]
        g=call("grant.create",world=r["world"],role="intake",actor="test").json()
        assert c.post("/api/ops/call.turn",json={"id":b,"sequence":0},headers={"Authorization":"Bearer "+g["token"]}).status_code==403


@pytest.mark.skipif(os.getenv("TRIALRUN_PHONE_LIVE")!="1",reason="requires configured live model")
def test_human_caller_real_browser_and_provider(tmp_path):
    with socket.socket() as s:s.bind(("127.0.0.1",0));port=s.getsockname()[1]
    url=f"http://127.0.0.1:{port}"
    proc=subprocess.Popen([sys.executable,"-m","firm_lab.cli","serve","--port",str(port),"--data",str(tmp_path)],stdout=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                if httpx.get(url+"/health").is_success:break
            except httpx.HTTPError:pass
            time.sleep(.1)
        with sync_playwright() as pw:
            browser=pw.chromium.launch(args=["--no-sandbox","--disable-webgl"])
            p=browser.new_page()
            # Exercise the browser recognition-result and review path without requiring
            # physical microphone hardware (inference below is NOT mocked).
            p.add_init_script("""window.SpeechRecognition=class {start(){this.onresult({results:[[{transcript:'My callback number is 415-555-0181. My wrist is sore.'}]]});this.onend()}abort(){}stop(){}}""")
            p.goto(url+"/lab");p.get_by_label("Lab access token").fill((tmp_path/"controller.token").read_text().strip())
            p.get_by_role("button",name="Open lab").click()
            p.get_by_role("button",name="Start call scenario").click()
            if os.getenv("TRIALRUN_PHONE_PROFILE"):p.get_by_label("Clerk model").select_option(os.environ["TRIALRUN_PHONE_PROFILE"])
            p.get_by_role("button",name="Ring the office").click()
            panel=p.get_by_label("Office call",exact=True);expect(panel).to_be_visible()
            for idx,msg in enumerate(["A delivery van hit my bicycle on Pine Street. My name is Robin Park. Can you help?",
                                      "My callback number is 415-555-0181. My wrist is sore."]):
                if idx==0:panel.get_by_label("Your words").fill(msg)
                else:
                    panel.get_by_role("button",name="Use microphone").click()
                    expect(panel.get_by_label("Your words")).to_have_value(msg)
                panel.get_by_role("button",name="Send turn").click()
                expect(panel.locator(".phone-lines li")).to_have_count(3+idx*2,timeout=190000)
                print("Caller:",msg,"Agent:",panel.locator(".phone-lines li").last.inner_text(),flush=True)
            panel.get_by_role("button",name="Minimize").click()
            p.get_by_role("button",name="Intake monitor",exact=True).click()
            crm=p.frame_locator('iframe[title="Attempt CRM"]')
            print("CRM:",crm.locator("#content").inner_text(),flush=True)
            expect(crm.locator('#content')).to_contain_text('Robin Park')
            p.get_by_role("button",name="Back to office").click()
            p.get_by_role("button",name="Desk phone",exact=True).click()
            panel.get_by_role("button",name="End call").click()
            expect(p.locator(".grade")).to_contain_text("checks passed")
            browser.close()
    finally:
        proc.terminate();proc.wait(timeout=30)
