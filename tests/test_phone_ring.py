"""Check real UI timing without opening a microphone or calling an inference provider."""
import os
import socket
import subprocess
import sys
import time

import httpx
from playwright.sync_api import expect, sync_playwright


def test_two_rings_before_microphone_and_cancel(tmp_path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0));port=sock.getsockname()[1]
    base=f"http://127.0.0.1:{port}"
    proc=subprocess.Popen([sys.executable,"-m","firm_lab.cli","serve","--port",str(port),"--data",str(tmp_path)],
                          env={**os.environ,"TRIALRUN_GEMINI_API_KEY":"ui-test-only"},stdout=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                if httpx.get(base+"/health").is_success:break
            except httpx.HTTPError:pass
            time.sleep(.1)
        with sync_playwright() as pw:
            browser=pw.chromium.launch(args=["--no-sandbox","--disable-webgl"])
            p=browser.new_page();p.add_init_script("""window.notes=[];window.mics=[];
                const start=OscillatorNode.prototype.start;
                OscillatorNode.prototype.start=function(...args){notes.push([this.frequency.value,performance.now()]);return start.apply(this,args)};
                navigator.mediaDevices.getUserMedia=async()=>{mics.push(performance.now());throw new DOMException('No device','NotAllowedError')};""")
            p.goto(base+"/lab");p.get_by_label("Lab access token").fill((tmp_path/"controller.token").read_text().strip())
            p.get_by_role("button",name="Open lab").click()
            def launch():
                p.get_by_role("button",name="Start call scenario").click()
                p.get_by_role("button",name="Ring the office").click()
            launch()
            desk=p.locator("#office-desk")
            expect(p.locator(".phone-state")).to_have_text("Incoming call · Ring 1 of 2")
            expect(desk).to_have_attribute("data-phone-lit","true")
            expect(p.get_by_role("button",name="Connect microphone")).to_be_hidden()
            expect(desk).to_have_attribute("data-phone-lit","false")
            expect(p.locator(".phone-state")).to_have_text("Incoming call · Ring 2 of 2")
            expect(desk).to_have_attribute("data-phone-lit","true")
            expect(p.locator(".phone-audio")).to_contain_text("permission denied")
            expect(desk).to_have_attribute("data-ringing","false")
            notes,mics=p.evaluate("[notes,mics]")
            assert [freq for freq,_ in notes]==[440,480,440,480] and len(mics)==1
            assert notes[2][1]-notes[0][1]>=2500 and mics[0]-notes[2][1]>=1050
            launch()
            expect(p.locator(".phone-state")).to_contain_text("Ring 1 of 2")
            original=p.url;p.get_by_role("button",name="End call").click()
            expect(p.locator(".grade")).to_be_visible()
            # The old timers must not request a mic even if we return to the frozen office.
            p.goto(original);expect(p.locator(".phone-state")).to_contain_text("Ended")
            p.wait_for_timeout(4100)
            assert p.evaluate("[notes.length,mics.length]")==[0,0]
            browser.close()
    finally:
        proc.terminate();proc.wait(timeout=20)
