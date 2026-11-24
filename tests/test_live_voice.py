import json
import os
import socket
import subprocess
import sys
import time
import wave

import httpx
import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright, expect
from starlette.websockets import WebSocketDisconnect

from firm_lab.app import create_app
from firm_lab.db import LabError
from firm_lab.live_voice import VoiceBridge


def test_live_tools_attempt_boundary_and_retry(tmp_path,monkeypatch):
    monkeypatch.setenv("TRIALRUN_GEMINI_API_KEY","fake")
    app=create_app(tmp_path)
    with TestClient(app) as client:
        auth={"Authorization":"Bearer "+app.state.store.controller}
        def op(name,**kw):
            return client.post("/api/ops/"+name,headers=auth,json=kw)
        def start():return op("call.start",mode="live").json()["id"]
        a,b=start(),start();bridge=VoiceBridge(app.state.lab)
        assert op("call.turn",id=a,text="bypass",sequence=0).status_code==409
        assert op("agent.list").json()["live_voice"]
        for headers in ({},{"origin":"https://elsewhere.test",**auth}):
            with pytest.raises(WebSocketDisconnect),client.websocket_connect("/api/voice/"+a,headers=headers):pass
        bridge.record(a,[("caller","I'm Sam Lane. I fell on Main. My number is 555-0123.")])
        def tool(name,args,i):return bridge.tool(a,{"name":name,"args":args,"id":i})
        assert not tool("schedule_callback",{"delay_minutes":15},"missing")["ok"]
        payload={"name":"Sam Lane","phone":"555-0123","summary":"I fell on Main."}
        assert not tool("save_inquiry",{**payload,"world":b},"outside")["ok"]
        assert not tool("save_inquiry",{**payload,"name":"Ben"},"invented")["ok"]
        assert not tool("save_inquiry",{**payload,"phone":"555-0100"},"wrong-number")["ok"]
        saved=tool("save_inquiry",payload,"save")
        assert saved["ok"] and tool("save_inquiry",payload,"save")==saved
        callback=tool("schedule_callback",{"delay_minutes":15},"callback")
        assert callback["ok"] and callback["task"]==tool("schedule_callback",{"delay_minutes":30},"change")["task"]
        bridge.record(a,[("agent","The simulated callback is scheduled.")])
        assert not op("run.inspect",id=b).json()["state"]["leads"]
        monkeypatch.setenv("TRIALRUN_VOICE_DAILY_SESSIONS","1")
        assert bridge.reserve(a)["callback_exists"]
        with pytest.raises(LabError,match="Daily voice"):bridge.reserve(b)
        op("call.end",id=a).raise_for_status();assert op("run.grade",id=a).json()["passed"]==3
        with pytest.raises(LabError):tool("save_inquiry",payload,"late")


@pytest.mark.skipif(os.getenv("TRIALRUN_TEST_GEMINI")!="1",reason="requires opt-in, Gemini and ffmpeg with flite")
def test_microphone_to_gemini_to_crm(tmp_path):
    wav=tmp_path/"caller.wav"
    with wave.open(str(wav),"wb") as w:
        w.setparams((1,2,16000,0,"NONE",""))
        for before,text in [(11,"Hello. My name is Robin Park. I was hit by a van on Pine Street. My callback number is zero one six three two, nine six zero, two four seven. Please create an inquiry and schedule a callback in thirty minutes."),
                            (7,"Sure. My full name is Robin Park. A van hit my bike on Pine Street. My phone number is zero one six three two, nine six zero, two four seven. Those details are correct. I would like that callback in thirty minutes."),
                            (7,"My name is Robin Park. The number is zero one six three two, nine six zero, two four seven. Yes, I confirm the details. Please save my inquiry and schedule that thirty minute callback. Thank you.")]:
            w.writeframes(b"\0"*32000*before)
            w.writeframes(subprocess.check_output(["ffmpeg","-loglevel","error","-f","lavfi","-i","flite=text='"+text+"':voice=slt","-ar","16000","-ac","1","-f","s16le","-"]))
        w.writeframes(b"\0"*32000*20)
    with socket.socket() as s:s.bind(("127.0.0.1",0));port=s.getsockname()[1]
    base=f"http://127.0.0.1:{port}";data=tmp_path/"worlds"
    server=subprocess.Popen([sys.executable,"-m","firm_lab.cli","serve","--port",str(port),"--data",str(data)],stdout=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                if httpx.get(base+"/health").is_success:break
            except httpx.HTTPError:pass
            time.sleep(.1)
        with sync_playwright() as pw:
            browser=pw.chromium.launch(args=["--no-sandbox","--disable-webgl","--use-fake-device-for-media-stream","--use-fake-ui-for-media-stream","--use-file-for-fake-audio-capture="+str(wav)])
            p=browser.new_page()
            p.add_init_script("""window.playedSamples=0;const start=AudioBufferSourceNode.prototype.start;
                 AudioBufferSourceNode.prototype.start=function(...args){if(this.buffer?.sampleRate===24000)window.playedSamples+=this.buffer.length;return start.apply(this,args)}""")
            p.goto(base+"/lab")
            token=(data/"controller.token").read_text().strip();p.get_by_label("Lab access token").fill(token)
            p.get_by_role("button",name="Open lab").click();p.get_by_role("button",name="Start call scenario").click()
            expect(p.get_by_label("Who is calling?")).to_have_value("live")
            p.get_by_role("button",name="Ring the office").click()
            expect(p.locator(".phone-audio")).to_contain_text("Speak naturally",timeout=25000)
            id=p.url.split("/attempts/")[1].split("?")[0]
            for _ in range(100):
                r=httpx.post(base+"/api/ops/run.inspect",headers={"Authorization":"Bearer "+token},json={"id":id}).json()
                speakers=[t["speaker"] for t in r["state"]["turns"]]
                if r.get("call_task") and "caller" in speakers and "agent" in speakers[speakers.index("caller")+1:]:break
                p.wait_for_timeout(900)
            print("Synthetic transcript:",[(t["speaker"],t["text"]) for t in r["state"]["turns"]])
            assert r.get("call_lead") and r.get("call_task"),r["runner_trace"]
            assert r["call_facts"]["name"].casefold()=="robin park"
            assert "".join(c for c in r["call_facts"]["phone"] if c.isdigit())=="01632960247"
            assert r["state"]["tasks"][-1]["lead_id"]==r["call_lead"]
            assert p.evaluate("window.playedSamples")>24000
            p.get_by_role("button",name="Disconnect microphone").click()
            expect(p.locator(".phone-audio")).to_contain_text("Microphone disconnected")
            p.get_by_role("button",name="End call").click();expect(p.locator(".grade")).to_contain_text("3 of 3")
            browser.close()
    finally:
        server.terminate();server.wait(timeout=15)
