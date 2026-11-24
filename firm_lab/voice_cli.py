"""Audio transport for shell clients; status to stderr, never mixed with PCM."""
import asyncio
import json
import sys
from urllib.parse import urlsplit, urlunsplit, quote
from websockets.asyncio.client import connect

async def stream(url,attempt,headers):
    p=urlsplit(url)
    uri=urlunsplit(("wss" if p.scheme=="https" else "ws",p.netloc,"/api/voice/"+quote(attempt,safe=""),"",""))
    async with connect(uri,additional_headers=headers,proxy=None) as ws:
        first=await ws.recv()
        if json.loads(first).get("type")!="ready":raise ValueError("Voice session unavailable")
        async def upload():
            while chunk:=await asyncio.to_thread(sys.stdin.buffer.read,1280):
                await ws.send(chunk);await asyncio.sleep(len(chunk)/32000)
            await ws.send("stop")
        task=asyncio.create_task(upload())
        try:
            async for msg in ws:
                if isinstance(msg,bytes):sys.stdout.buffer.write(msg);sys.stdout.buffer.flush()
                else:print(msg,file=sys.stderr)
        finally:
            task.cancel();await asyncio.gather(task,return_exceptions=True)
