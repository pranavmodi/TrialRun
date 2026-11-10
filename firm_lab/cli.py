import argparse
import json
import os
import sys
from pathlib import Path
import httpx

def main():
    parser=argparse.ArgumentParser(description="PI Firm Lab — all product operations use the HTTP API")
    parser.add_argument("--url",default=os.environ.get("FIRM_LAB_URL","http://127.0.0.1:8810"))
    parser.add_argument("--token-file",default=os.environ.get("FIRM_LAB_TOKEN_FILE",".local/controller.token"))
    sub=parser.add_subparsers(dest="command",required=True)
    serve=sub.add_parser("serve"); serve.add_argument("--host",default="127.0.0.1"); serve.add_argument("--port",type=int,default=8810); serve.add_argument("--data",default=".local")
    sub.add_parser("token",help="Print the local controller token for browser sign-in; do not share with agents")
    sub.add_parser("operations",help="List all role-permitted API/CLI operations")
    sub.add_parser("schema",help="Show field schema")
    call=sub.add_parser("call"); call.add_argument("operation"); call.add_argument("--json",default="{}"); call.add_argument("--file"); call.add_argument("--key",help="Idempotency key")
    public=sub.add_parser("submit"); public.add_argument("--json",required=True); public.add_argument("--key")
    args=parser.parse_args()
    if args.command=="serve":
        os.environ["FIRM_LAB_DATA"]=str(Path(args.data).resolve())
        import uvicorn
        uvicorn.run("firm_lab.app:create_app",factory=True,host=args.host,port=args.port)
        return
    if args.command=="token":
        print(Path(args.token_file).read_text().strip()); return
    try:
        headers={}
        if args.command!="submit":
            token=os.environ.get("FIRM_LAB_TOKEN") or Path(args.token_file).read_text().strip()
            headers["Authorization"]="Bearer "+token
        if getattr(args,"key",None): headers["Idempotency-Key"]=args.key
        with httpx.Client(base_url=args.url,headers=headers,timeout=120) as client:
            if args.command=="operations": response=client.get("/api/operations")
            elif args.command=="schema": response=client.get("/api/schema")
            elif args.command=="submit": response=client.post("/api/public/intakes",json=json.loads(args.json))
            else:
                data=json.loads(Path(args.file).read_text()) if args.file else json.loads(args.json)
                response=client.post("/api/ops/"+args.operation,json=data)
        print(json.dumps(response.json(),indent=2))
        if response.is_error: sys.exit(1)
    except (OSError,ValueError,httpx.HTTPError) as e:
        print(str(e),file=sys.stderr); sys.exit(1)

if __name__=="__main__": main()
