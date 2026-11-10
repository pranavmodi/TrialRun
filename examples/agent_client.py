"""Minimal provider-independent client for an evaluated agent.

No controller secret, database access, reference solution, or private facts.
Import this client into your agent's own harness. It does not implement reasoning.
"""
import os
import uuid
import httpx

class FirmClient:
    def __init__(self, url=None, token=None):
        self.http=httpx.Client(
            base_url=url or os.environ.get("FIRM_LAB_URL","http://127.0.0.1:8810"),
            headers={"Authorization":"Bearer "+(token or os.environ["FIRM_LAB_TOKEN"])},
            timeout=30)

    def call(self, operation, arguments=None, request_key=None):
        headers={"Idempotency-Key":request_key} if request_key else {}
        response=self.http.post("/api/ops/"+operation,json=arguments or {},headers=headers)
        if response.is_error:
            return {"ok":False,"status":response.status_code,**response.json()}
        return {"ok":True,"result":response.json()}

    def operations(self):
        return self.http.get("/api/operations").json()

    def schema(self):
        return self.http.get("/api/schema").json()

    def close(self):
        self.http.close()

if __name__=="__main__":
    import json
    client=FirmClient()
    try:
        print(json.dumps({"tools":client.operations(),"schema":client.schema(),"world":client.call("world.state")},indent=2))
    finally:
        client.close()
