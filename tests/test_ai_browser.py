"""Opt-in real model acceptance test. No demo data or provider tokens in evidence."""
import os
import socket
import subprocess
import sys
import time
import httpx
import pytest
from playwright.sync_api import sync_playwright, expect


@pytest.mark.skipif(os.getenv("TRIALRUN_LIVE_TEST")!="1",reason="requires opt-in real inference endpoint")
def test_real_model_from_lab(tmp_path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0)); port=sock.getsockname()[1]
    url=f"http://127.0.0.1:{port}"
    process=subprocess.Popen([sys.executable,"-m","firm_lab.cli","serve","--port",str(port),"--data",str(tmp_path)],
                             env={**os.environ,"TRIALRUN_LAB_URL":url},stdout=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                if httpx.get(url+"/health").is_success: break
            except httpx.HTTPError: pass
            time.sleep(.1)
        with sync_playwright() as pw:
            browser=pw.chromium.launch(args=["--no-sandbox"])
            page=browser.new_page()
            page.goto(url+"/lab")
            page.get_by_label("Lab access token").fill((tmp_path/"controller.token").read_text().strip())
            page.get_by_role("button",name="Open lab").click()
            page.get_by_role("button",name="Edit profile").click()
            page.get_by_label("Name",exact=True).fill("Live acceptance clerk")
            page.get_by_role("button",name="Save profile").click()
            page.get_by_role("button",name="Run with AI").click()
            expect(page.locator("#content")).to_contain_text("Waiting for website inquiry")
            with page.expect_popup() as tab:
                page.get_by_role("link",name="View attempt workspace").click()
            workspace=tab.value
            expect(workspace.locator("#content")).to_contain_text("No leads")
            page.get_by_role("button",name="Submit Jamie’s website form").click()
            expect(workspace.locator("#content")).to_contain_text("Jamie Rivera")
            page.get_by_role("button",name="Finish and evaluate").click(timeout=320000)
            expect(page.get_by_text("Evidence frozen",exact=False).first).to_be_visible()
            # A real evaluation need not pass. Verify that the outcome is actually grounded.
            evidence=page.evaluate("""async ()=> (await fetch('/api/ops/run.inspect',{method:'POST',
              headers:{'Content-Type':'application/json'},body:JSON.stringify({id:location.pathname.split('/').pop()})})).json()""")
            score=evidence["results"][-1]
            print("Real model:",evidence["agent_metadata"]["model"],"stop:",evidence["stop_reason"],
                  "tools:",[e["tool"] for e in evidence["runner_trace"] if e["event"]=="Requested tool"],
                  "score:",score["passed"],"/",score["total"])
            assert score["total"]==5 and evidence["execution_mode"]=="model_agent"
            assert any(e["action"]=="tool.call" and e["actor"]=="evaluated-agent" for e in evidence["state"]["events"])
            if score["passed"]==5:
                expect(workspace.locator("#content")).to_contain_text("converted",ignore_case=True)
                assert any(e.get("tool_call_id") for e in evidence["changes"] if e["actor"]=="evaluated-agent")
            expect(workspace.locator("#mode")).to_contain_text("Frozen result")
            browser.close()
    finally:
        process.terminate(); process.wait(timeout=20)
