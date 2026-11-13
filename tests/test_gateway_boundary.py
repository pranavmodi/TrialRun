import json
import httpx
from fastapi.testclient import TestClient
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

spec=spec_from_file_location("openclaw_bridge",Path(__file__).resolve().parents[1]/"deploy/openclaw_bridge.py")
bridge=module_from_spec(spec)
spec.loader.exec_module(bridge)

def test_private_adapter_rejects_routing_overrides_and_never_forwards_headers(tmp_path,monkeypatch):
    monkeypatch.setenv("CREDENTIALS_DIRECTORY",str(tmp_path))
    (tmp_path/"gateway").write_text("dummy-private")
    client=httpx.AsyncClient
    def reply(request):
        assert str(request.url)=="http://127.0.0.1:18789/v1/chat/completions"
        assert request.headers["Authorization"]=="Bearer dummy-private"
        assert "x-openclaw-agent-id" not in request.headers
        body=json.loads(request.content)
        assert body["model"]=="openclaw/trialrun-clerk"
        assert [x["function"]["name"] for x in body["tools"]]==["trialrun_decide"]
        return httpx.Response(200,json={"choices":[{"message":{"tool_calls":[
            {"function":{"name":"trialrun_decide","arguments":json.dumps({"final":"Done"})}}]}}]})
    monkeypatch.setattr(bridge.httpx,"AsyncClient",lambda **kw:client(transport=httpx.MockTransport(reply),**kw))
    with TestClient(bridge.app) as web:
        payload={"tools":[],"history":[]}
        assert web.post("/decision",json={**payload,"model":"openclaw/main"}).status_code==400
        r=web.post("/decision",json=payload,headers={"x-openclaw-agent-id":"main","Authorization":"Bearer wrong"})
        assert json.loads(r.json()["decision"])=={"final":"Done"}
