import json
import html
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from .db import Store, LabError, get, put, rows, meta
from .schema import SCHEMAS
from .lab import LabService
from .service import OPERATIONS

STATIC=Path(__file__).parent / "static"

def create_app(data_root=None):
    store=Store(data_root)
    lab=LabService(store); lab.install_scenarios()
    controller=store.authenticate(store.controller)
    demo_file=store.root / "demo.id"
    if not demo_file.exists():
        demo=lab.execute("world.create",{"name":"Harbor & Stone — demo","seed":"realistic"},controller)
        demo_file.write_text(demo["id"])
    demo_id=demo_file.read_text().strip()
    app=FastAPI(title="PI Firm Lab",version="0.1.0",docs_url=None,redoc_url=None,description="Independent simulated workplace. No external delivery. Operation registry: /api/operations.")
    app.state.store=store; app.state.lab=lab; app.state.demo_id=demo_id
    def auth(request):
        value=request.headers.get("authorization","")
        token=value[7:] if value.lower().startswith("bearer ") else request.cookies.get("firm_lab_token","")
        return store.authenticate(token)

    @app.middleware("http")
    async def boundaries(request,call_next):
        if request.method not in ("GET","HEAD","OPTIONS"):
            length=request.headers.get("content-length")
            if length and int(length)>8*1024*1024: return JSONResponse({"error":"Request too large"},413)
            origin=request.headers.get("origin")
            if origin and origin.rstrip("/")!=str(request.base_url).rstrip("/"):
                return JSONResponse({"error":"Cross-origin writes are not permitted"},403)
        response=await call_next(request)
        response.headers["X-Content-Type-Options"]="nosniff"
        response.headers["Referrer-Policy"]="no-referrer"
        response.headers["Content-Security-Policy"]="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self' data:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
        response.headers["Cache-Control"]="no-store"
        return response

    @app.exception_handler(LabError)
    async def domain_error(request,e):
        return JSONResponse({"error":str(e)},e.status)

    @app.exception_handler(KeyError)
    async def missing_key(request,e):
        return JSONResponse({"error":"Missing required field: "+str(e)},400)

    @app.exception_handler(ValueError)
    async def invalid_value(request,e):
        return JSONResponse({"error":"Invalid request value"},400)

    @app.get("/health")
    def health():
        return {"status":"ok","mode":"simulation","version":"0.1.0"}

    @app.get("/docs",response_class=HTMLResponse)
    def documentation():
        catalog="".join("<tr><td><code>"+html.escape(op["name"])+"</code></td><td>"+html.escape(op["label"])+"</td><td>"+html.escape(", ".join(op["roles"]))+"</td><td><code>"+html.escape(op["cli"])+"</code></td></tr>" for op in OPERATIONS.values())
        return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>PI Firm Lab · API reference</title><link rel="stylesheet" href="/static/style.css"></head><body><header class="public-nav"><div class="public-brand">PI Firm Lab</div><a href="/">Open workspace</a></header><main><p class="eyebrow">LOCAL API REFERENCE</p><h1>One contract. Every interface.</h1><div class="callout">POST /api/ops/{operation} with JSON arguments and an Authorization: Bearer TOKEN header. Business operations require a world unless the token is world-scoped. Use records.update with the current record version; retry ambiguous writes with an Idempotency-Key.</div><p><a href="/openapi.json">HTTP OpenAPI document</a> · <a href="/api/operations">Authenticated operation registry</a> · <a href="/api/schema">Authenticated field schema</a></p><p>Full examples and argument descriptions are in API_CLI.md in the project directory. GET /health is public. Website submissions use POST /api/public/intakes. MCP tools use POST /mcp.</p><div class="table-wrap"><table><thead><tr><th>Operation</th><th>Purpose</th><th>Roles</th><th>CLI</th></tr></thead><tbody>'+catalog+'</tbody></table></div></main></body></html>'

    @app.post("/api/login")
    async def login(request:Request):
        data=await request.json(); principal=store.authenticate(data.get("token",""))
        response=JSONResponse({"role":principal["role"],"world":principal.get("world")})
        response.set_cookie("firm_lab_token",data["token"],httponly=True,samesite="strict",max_age=43200)
        return response

    @app.post("/api/logout")
    def logout():
        response=JSONResponse({"ok":True}); response.delete_cookie("firm_lab_token"); return response

    @app.get("/api/session")
    def session(request:Request):
        return {**auth(request),"demo_world":demo_id}

    @app.get("/api/operations")
    def operations(request:Request):
        p=auth(request)
        return [{k:v for k,v in op.items() if k!="handler"} for op in OPERATIONS.values() if p["role"] in op["roles"]]

    @app.get("/api/schema")
    def schema(request:Request):
        auth(request); return SCHEMAS

    @app.post("/api/ops/{operation}")
    async def call(operation:str,request:Request):
        data=await request.json()
        if not isinstance(data,dict): raise LabError("Operation arguments must be an object")
        return lab.execute(operation,data,auth(request),request.headers.get("idempotency-key"))

    @app.get("/api/public")
    def public_config():
        with store.world(demo_id) as c:
            return {"firm_name":meta(c)["policy"]["firm_name"],"form":rows(c,"forms")[0],"mode":"simulation"}

    @app.post("/api/public/intakes")
    async def public_intake(request:Request):
        data=await request.json()
        record=lab.website_submission(demo_id,data,request.headers.get("idempotency-key"))
        return {"reference":record["id"],"message":"Your test inquiry was saved in the simulated firm's leads inbox. No real firm has been contacted."}

    @app.post("/mcp")
    async def mcp(request:Request):
        p=auth(request); body=await request.json()
        method=body.get("method"); request_id=body.get("id")
        if method=="notifications/initialized": return JSONResponse({},202)
        if method=="initialize": result={"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"serverInfo":{"name":"pi-firm-lab","version":"0.1.0"}}
        elif method=="tools/list":
            result={"tools":[{"name":name.replace(".","__"),"description":op["label"]+". Arguments follow the operation registry and API_CLI.md.",
                      "inputSchema":{"type":"object","properties":{"world":{"type":"string"},"entity":{"type":"string","enum":list(SCHEMAS)},"id":{"type":"string"},"data":{"type":"object"},"version":{"type":"integer"},"query":{"type":"string"},"contact_id":{"type":"string"},"matter_id":{"type":"string"},"template_id":{"type":"string"}},"additionalProperties":True}}
                    for name,op in OPERATIONS.items() if p["role"] in op["roles"] and not op["control"]]}
        elif method=="tools/call":
            params=body.get("params",{})
            try:
                name=params["name"].replace("__",".")
                if name not in OPERATIONS or OPERATIONS[name]["control"]: raise LabError("Controller tools are not exposed over MCP",403)
                output=lab.execute(name,params.get("arguments",{}),p,request.headers.get("idempotency-key"))
                result={"content":[{"type":"text","text":json.dumps(output)}],"isError":False}
            except LabError as e:
                result={"content":[{"type":"text","text":json.dumps({"error":str(e),"status":e.status})}],"isError":True}
        else: return {"jsonrpc":"2.0","id":request_id,"error":{"code":-32601,"message":"Method not found"}}
        return {"jsonrpc":"2.0","id":request_id,"result":result}

    @app.get("/")
    def home(): return FileResponse(STATIC/"index.html")
    @app.get("/website")
    def website(): return FileResponse(STATIC/"website.html")
    app.mount("/static",StaticFiles(directory=STATIC),name="static")
    return app
