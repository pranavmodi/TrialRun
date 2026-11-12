"""Real browser acceptance test. Uses its own temporary server and database."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import httpx
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]

def test_browser_workflow(tmp_path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0)); port=sock.getsockname()[1]
    url=f"http://127.0.0.1:{port}"
    log=(tmp_path/"server.log").open("w")
    process=subprocess.Popen([sys.executable,"-m","firm_lab.cli","serve","--port",str(port),"--data",str(tmp_path/"data")],cwd=ROOT,stdout=log,stderr=log)
    try:
        for _ in range(100):
            try:
                if httpx.get(url+"/health").status_code==200: break
            except httpx.HTTPError: pass
            time.sleep(.1)
        else: raise AssertionError("Browser test server failed to start")
        token=(tmp_path/"data/controller.token").read_text().strip()
        with sync_playwright() as pw:
            browser=pw.chromium.launch(args=["--no-sandbox"])
            page=browser.new_page(viewport={"width":1440,"height":1000})
            errors=[]; page.on("pageerror",lambda e:errors.append(str(e)))
            page.goto(url+"/website")
            page.get_by_role("button",name="Load a fictional test example").click()
            page.get_by_role("button",name="Submit test inquiry").click()
            expect(page.locator("#result")).to_contain_text("Reference:")
            page.goto(url)
            page.locator("#token").fill(token)
            page.get_by_role("button",name="Open workspace").click()
            expect(page.locator("#page-title")).to_have_text("Your firm at a glance")
            page.locator('#nav [data-page="leads"]').click()
            expect(page.locator("table")).to_contain_text("Jamie Rivera")
            page.get_by_role("button",name="Convert",exact=True).click()
            page.get_by_role("button",name="Convert to matter",exact=True).click()
            expect(page.locator("#page-title")).to_contain_text("Jamie Rivera")
            page.get_by_role("button",name="Add task",exact=True).click()
            page.locator('#modal-fields [name="title"]').fill("Browser acceptance callback")
            page.get_by_role("button",name="Save changes",exact=True).click()
            expect(page.locator("#content")).to_contain_text("Browser acceptance callback")
            page.get_by_role("button",name="Draft message",exact=True).click()
            page.get_by_role("button",name="Save changes",exact=True).click()
            expect(page.locator("#content")).to_contain_text("drafted")
            page.get_by_role("button",name="Send locally",exact=True).click()
            expect(page.locator("#content")).to_contain_text("delivered")
            page.locator('#nav [data-page="appointments"]').click()
            page.get_by_role("button",name="Add appointment",exact=True).click()
            matter_options=page.locator('[name="matter_id"] option').all_text_contents()
            page.locator('[name="matter_id"]').select_option(label=next(x for x in matter_options if "Jamie Rivera" in x))
            page.locator('[name="staff_id"]').select_option(label="Avery Chen")
            page.locator('[name="title"]').fill("Browser consultation")
            page.locator('[name="start_at"]').fill("2026-11-07T18:00:00+00:00")
            page.locator('[name="end_at"]').fill("2026-11-07T18:30:00+00:00")
            page.get_by_role("button",name="Save changes",exact=True).click()
            expect(page.locator("table")).to_contain_text("Browser consultation")
            page.locator('#nav [data-page="lab"]').click()
            expect(page.get_by_role("heading",name="Convert one website inquiry")).to_be_visible()
            expect(page.locator('[data-action="reference"][data-id="ambiguous-save"]')).to_be_hidden()
            page.get_by_role("button",name="Try scripted example").click()
            expect(page.locator("#world-label")).to_have_text("Viewing test · Attempt 1")
            expect(page.locator("#content")).to_contain_text("No records in this inbox yet")
            expect(page.get_by_role("button",name="Reset demo")).to_be_hidden()
            page.get_by_role("button",name="Submit Jamie’s website form").click()
            expect(page.locator("#content")).to_contain_text("Website visitor · Submitted website form")
            page.reload()
            expect(page.locator("#world-label")).to_have_text("Viewing test · Attempt 1")
            page.get_by_role("button",name="Run scripted conversion").click()
            expect(page.locator("#content")).to_contain_text("Script · Inquiry → converted")
            page.get_by_role("button",name="Contacts",exact=True).click()
            expect(page.locator("#content summary").filter(has_text="Jamie Rivera record")).to_be_visible()
            page.get_by_role("button",name="Finish and evaluate").click()
            expect(page.locator("#content")).to_contain_text("5 of 5 checks passed",timeout=30000)
            expect(page.locator("#section-kicker")).to_contain_text("NOT AN AI EVALUATION")
            expect(page.get_by_role("button",name="Caller speaks")).to_have_count(0)
            page.get_by_role("button",name="Back to evaluation lab").click()
            page.get_by_role("button",name="Set up agent run").click()
            expect(page.locator("#modal")).to_contain_text("No agent has started")
            conn=json.loads(page.locator('#modal pre').text_content())
            page.get_by_role("button",name="Close dialog").click()
            page.get_by_role("button",name="Submit Jamie’s website form").click()
            expect(page.locator("#content")).to_contain_text("Website visitor · Submitted website form")
            # An external worker writes via HTTP; the unchanged browser tab must see it via live polling.
            resp=httpx.post(url+'/api/ops/records.create',headers={'Authorization':'Bearer '+conn['agent_token']},
                json={'entity':'contacts','data':{'name':'Out of scope test contact'}})
            assert resp.is_success
            expect(page.locator("#content")).to_contain_text("Agent · create · contacts · Out of scope test contact")
            page.get_by_role("button",name="Finish and evaluate").click()
            expect(page.locator("#content")).to_contain_text("0 of 5 checks passed")
            expect(page.locator("#world-label")).to_contain_text("Attempt 2")
            page.get_by_role("button",name="Back to evaluation lab").click()
            expect(page.get_by_role("row").filter(has_text="Attempt 2")).to_contain_text("failed")
            expect(page.get_by_role("row").filter(has_text="Attempt 1")).to_contain_text("passed")
            page.get_by_text("More scenarios and other runs",exact=True).click()
            page.locator('[data-action="reference"][data-id="ambiguous-save"]').click()
            expect(page.locator("#content")).to_contain_text("7/7 checks",timeout=30000)
            expect(page.locator("#content")).to_contain_text("Requires independent PI expert review")
            screenshot_dir=ROOT/"artifacts"; screenshot_dir.mkdir(exist_ok=True)
            page.screenshot(path=str(screenshot_dir/"evaluation-desktop.png"),full_page=True)
            page.locator('#nav [data-page="overview"]').click()
            expect(page.locator("#page-title")).to_have_text("Your firm at a glance")
            page.screenshot(path=str(screenshot_dir/"workspace-desktop.png"),full_page=True)
            page.set_viewport_size({"width":390,"height":844})
            page.screenshot(path=str(screenshot_dir/"workspace-mobile.png"),full_page=True)
            page.goto(url+"/website")
            page.screenshot(path=str(screenshot_dir/"website-mobile.png"),full_page=True)
            # Uploaded audio is a playable artifact, not a claim of live capture.
            import base64, io, wave
            audio=io.BytesIO()
            with wave.open(audio,"wb") as wav:
                wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(8000); wav.writeframes(bytes(16000))
            auth={"Authorization":"Bearer "+token}
            world=httpx.get(url+"/api/session",headers=auth).json()["demo_world"]
            conversation=httpx.post(url+"/api/ops/records.create",headers=auth,json={"world":world,"entity":"conversations","data":{"title":"Uploaded audio test"}}).json()
            response=httpx.post(url+"/api/ops/recording.attach",headers=auth,json={"world":world,"id":conversation["id"],"mime":"audio/wav","base64":base64.b64encode(audio.getvalue()).decode()})
            assert response.status_code==200
            page.goto(url)
            expect(page.locator("#page-title")).to_have_text("Your firm at a glance")
            page.locator('#nav [data-page="conversations"]').click()
            expect(page.locator('audio')).to_be_visible()
            page.wait_for_function("Number.isFinite(document.querySelector('audio')?.duration)")
            assert page.locator('audio').evaluate('(a)=>a.duration')>0
            # Prominent empty reset: cancel is safe, confirmation clears only the demo.
            expect(page.get_by_role('button',name='Reset demo',exact=True)).to_be_visible()
            page.get_by_role('button',name='Reset demo',exact=True).click()
            expect(page.locator('#modal')).to_contain_text('No sample cases are added')
            page.get_by_role('button',name='Cancel',exact=True).click()
            expect(page.locator('audio')).to_be_visible()
            worlds=httpx.post(url+'/api/ops/world.list',headers=auth,json={}).json()
            other=next(w['id'] for w in worlds if w['id']!=world)
            before=httpx.post(url+'/api/ops/world.state',headers=auth,json={'world':other}).json()
            page.get_by_role('button',name='Reset demo',exact=True).click()
            page.get_by_role('button',name='Clear demo and start fresh',exact=True).click()
            expect(page.locator('#page-title')).to_have_text('Your firm at a glance')
            fresh=httpx.post(url+'/api/ops/world.state',headers=auth,json={'world':world}).json()
            for entity,records in fresh['data'].items():
                if entity not in {'staff','forms','workflows'}: assert not records,entity
            assert fresh['data']['forms'] and fresh['data']['staff']
            after=httpx.post(url+'/api/ops/world.state',headers=auth,json={'world':other}).json()
            assert before['data']==after['data']
            expect(page.locator('#world-select')).to_be_hidden()
            expect(page.locator('#world-label')).to_have_text('Harbor & Stone')
            assert httpx.post(url+'/api/ops/world.create',headers=auth,json={'name':'Second firm','seed':'empty'}).is_success
            page.reload()
            selector=page.get_by_role('combobox',name='Selected firm')
            expect(selector).to_be_visible()
            expect(selector.locator('option')).to_have_text(['Harbor & Stone','Second firm'])
            selector.select_option(label='Second firm')
            expect(page.get_by_role('button',name='Reset demo')).to_be_hidden()
            assert not errors,errors
            browser.close()
        # CLI operates over HTTP, not the database.
        env={**os.environ,"FIRM_LAB_URL":url,"FIRM_LAB_TOKEN_FILE":str(tmp_path/"data/controller.token")}
        result=subprocess.run([sys.executable,"-m","firm_lab.cli","operations"],cwd=ROOT,env=env,capture_output=True,text=True)
        assert result.returncode==0,result.stderr
        assert any(x["name"]=="world.reset" for x in json.loads(result.stdout))
        result=subprocess.run([sys.executable,"-m","firm_lab.cli","call","world.list"],cwd=ROOT,env=env,capture_output=True,text=True)
        assert result.returncode==0,result.stderr
        assert len(json.loads(result.stdout))>=2
    finally:
        process.terminate()
        process.wait(timeout=10)
        log.close()
