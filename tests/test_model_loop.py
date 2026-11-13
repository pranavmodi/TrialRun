import json
import httpx
from firm_lab import runner


def test_model_loop_search_failure_and_recovery(monkeypatch):
    monkeypatch.setenv("TRIALRUN_MODEL_URL","https://provider.test/v1/")
    monkeypatch.setenv("TRIALRUN_MODEL_KEY","provider-secret")
    monkeypatch.delenv("TRIALRUN_MODEL_KEY_FILE",raising=False)
    monkeypatch.setenv("TRIALRUN_LAB_URL","https://lab.test")
    actions=iter([("records__list",{"entity":"leads"}),("lead__convert",{"id":"wrong"}),
                  ("lead__convert",{"id":"found"}),None])
    def serve(request):
        body=json.loads(request.content)
        if request.url.host=="provider.test":
            assert request.headers["authorization"]=="Bearer provider-secret"
            assert "lab-secret" not in str(body)
            action=next(actions)
            if action:
                assert action[0] in {tool["function"]["name"] for tool in body["tools"]}
                msg={"content":None,"tool_calls":[{"type":"function","id":"x",
                    "function":{"name":action[0],"arguments":json.dumps(action[1])}}]}
            else: msg={"content":"Done."}
            return httpx.Response(200,json={"choices":[{"message":msg,"finish_reason":"tool_calls" if action else "stop"}]})
        assert request.url.host=="lab.test" and request.headers["authorization"]=="Bearer lab-secret"
        if body["method"]=="tools/list":
            result={"tools":[{"name":name,"description":name,"inputSchema":{"properties":{
                k:{"type":"string"} for k in ("entity","id","version","data","query","contact_id","matter_id")}}}
                for name in runner.FIELDS if name!="link_existing_lead"]}
        else:
            args=body["params"]["arguments"]
            result={"isError":args.get("id")=="wrong","content":[{"text":json.dumps(
                {"items":[{"id":"found"}]} if "entity" in args else {"ok":args["id"]=="found"})}]}
        return httpx.Response(200,json={"result":result})
    client=httpx.Client
    monkeypatch.setattr(runner.httpx,"Client",lambda **kwargs:client(transport=httpx.MockTransport(serve),**kwargs))
    trace=[]
    reason=runner.run_model(dict(instructions="Test",model="test",timeout_seconds=60,max_turns=4),
                            "Use the firm tools","lab-secret",trace.append)
    assert reason=="Model returned a final response"
    assert [x["event"] for x in trace if x["event"].startswith("Tool ")]==["Tool result","Tool error","Tool result"]
    assert "secret" not in str(trace)
