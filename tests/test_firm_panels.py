"""Persistent office pickup and the shared dialog surfaces, using a temporary firm."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import httpx
from playwright.sync_api import expect,sync_playwright


def test_office_continuity_and_dialogs(tmp_path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0));port=sock.getsockname()[1]
    base=f"http://127.0.0.1:{port}"
    proc=subprocess.Popen([sys.executable,"-m","firm_lab.cli","serve","--port",str(port),"--data",str(tmp_path)],
        env={**os.environ,"TRIALRUN_GEMINI_API_KEY":"test-only"},stdout=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                if httpx.get(base+"/health").is_success:break
            except httpx.HTTPError:pass
            time.sleep(.1)
        token=(tmp_path/"controller.token").read_text().strip()
        def op(name,**kw):
            r=httpx.post(base+"/api/ops/"+name,headers={"Authorization":"Bearer "+token},json=kw);r.raise_for_status();return r.json()
        with sync_playwright() as pw:
            b=pw.chromium.launch(args=["--no-sandbox","--disable-webgl","--use-fake-device-for-media-stream","--use-fake-ui-for-media-stream"])
            ctx=b.new_context(viewport={"width":1280,"height":800})
            ctx.request.post(base+"/api/login",data={"token":token})
            p=ctx.new_page();connections=[]
            def accept(ws):
                connections.append(ws);ws.send('{"type":"ready"}')
            p.route_web_socket("**/api/voice/*",accept)
            p.on("dialog",lambda d:(_ for _ in ()).throw(AssertionError("Unexpected native dialog: "+d.type)))
            def shot(name):
                if dest:=os.getenv("TRIALRUN_PANEL_PREVIEWS"):
                    folder=Path(dest);folder.mkdir(parents=True,exist_ok=True);p.screenshot(path=folder/(name+".png"))
            p.goto(base+"/lab");p.get_by_role("button",name="Start call scenario").click()
            setup=p.get_by_role("dialog",name="Start an incoming call");expect(setup).to_be_visible()
            shot("call-setup")
            p.set_viewport_size({"width":390,"height":844})
            expect(setup.get_by_role("button",name="Ring the office")).to_be_in_viewport()
            setup.get_by_role("button",name="Ring the office").click()
            expect(p.locator(".phone-state")).to_contain_text("Ring 1")
            p.locator(".flat-photo").wait_for()
            geom="""()=>[...['.phone-console','.flat-photo'].flatMap(s=>{const r=document.querySelector(s).getBoundingClientRect();return [r.x,r.y,r.width,r.height]}),performance.timeOrigin]"""
            before=p.evaluate(geom)
            p.evaluate("window.originalRoom=document.querySelector('#office-desk');window.originalPanel=document.querySelector('.phone-console')")
            expect(p.locator(".phone-audio")).to_contain_text("Speak naturally",timeout=25000)
            assert before==p.evaluate(geom)
            assert len(connections)==1
            shot("connected-office")
            id=p.url.split("/attempts/")[1].split("?")[0];run=op("run.inspect",id=id)
            def turn(text):
                op("records.create",world=run["world"],entity="turns",data={"conversation_id":run["conversation_id"],"speaker":"agent","text":text})
            turn("Hello from the intake desk.")
            expect(p.locator(".phone-lines")).to_contain_text("Hello from the intake desk.")
            p.evaluate("window.firstLine=document.querySelector('.phone-lines li')")
            turn("What happened?")
            expect(p.locator(".phone-lines")).to_contain_text("What happened?")
            assert p.evaluate("firstLine===document.querySelector('.phone-lines li') && originalPanel===document.querySelector('.phone-console')")
            p.get_by_role("button",name="Start call scenario").click()
            p.keyboard.press("Escape");expect(setup).to_be_hidden();assert len(connections)==1
            p.get_by_role("button",name="Start call scenario").click()
            setup.get_by_role("button",name="Ring the office").click()
            expect(p.locator(".phone-state")).to_contain_text("Ring 1")
            assert p.evaluate("originalRoom===document.querySelector('#office-desk') && !originalPanel.isConnected")
            p.get_by_role("button",name="End call").click();expect(p.locator(".grade")).to_be_visible()
            assert before[-1]==p.evaluate("performance.timeOrigin")
            p.get_by_role("button",name="Add expert review").click()
            review=p.get_by_role("dialog",name="Expert review");review.get_by_label("Reviewer name").fill("Test specialist")
            review.get_by_label("Verdict").select_option("uncertain");review.get_by_label("Reason").fill("No conversation to assess.")
            review.get_by_role("button",name="Save review").click();expect(review).to_be_hidden()
            expect(p.locator("#content")).to_contain_text("Test specialist")
            other=op("run.create",scenario_id="returning-caller")["id"]
            p.goto(base+"/lab/attempts/"+other);p.get_by_role("button",name="Human role-play").click()
            rp=p.get_by_role("dialog",name="Human role-play");rp.get_by_label("Caller message").fill("I missed your call yesterday.")
            rp.get_by_role("button",name="Add caller message").click();expect(rp).to_be_hidden()
            assert any(t["text"]=="I missed your call yesterday." for t in op("run.inspect",id=other)["state"]["turns"])
            p.goto(base+"/workspace");p.get_by_role("button",name="Reset demo").click()
            confirm=p.get_by_role("dialog",name="Start fresh with an empty demo?")
            expect(confirm.get_by_role("button",name="Clear demo and start fresh")).to_be_in_viewport()
            expect(confirm).to_have_attribute("data-intent","destructive")
            confirm.get_by_role("button",name="Cancel").click();expect(confirm).to_be_hidden()
            b.close()
    finally:
        proc.terminate();proc.wait(timeout=20)
