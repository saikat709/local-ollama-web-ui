from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
import os, json, httpx, asyncio

from server import OLLAMA_BASE

# OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

app = FastAPI(title="Ollama Load Balancer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# http://10.42.0.155:11434/api/generate
# http://10.47.0.109:8000/stream
# http://10.42.0.155:8000/stream


servers = [
    {
        'name' : 'Server Pc 1',
        'ip' : '10.42.0.155',
        'port' : '8000',
        'current_load' : 0
    },
    {
        'name' : 'Masters 1',
        'ip' : '10.42.0.155',
        'port' : '8000',
        'current_load' : 0
    },
    {
        'name' : 'Masters 2',
        'ip' : '10.47.0.109',
        'port' : '8000',
        'current_load' : 0
    },
]


def get_least_loaded_server():
    least_loaded_server = min(servers, key=lambda x: x['current_load'])
    return least_loaded_server


@app.post("/generate")
async def generate(req: Request):
    payload = await req.json()
    payload["stream"] = False
    server = get_least_loaded_server()
    OLLAMA_BASE = f"http://{server['ip']}:{server['port']}"
    server['current_load'] += 1
    print(f"Routing to server: {server['name']} at {server['ip']}:{server['port']} with current load {server['current_load']}")
    async with httpx.AsyncClient(timeout=300.0) as client:
        r = await client.post(f"{OLLAMA_BASE}/generate", json=payload)
        if r.status_code != 200:
            raise HTTPException(r.status_code, r.text)
        data = r.json()
        server['current_load'] -= 1
        return JSONResponse({"response": data.get("response", "")})


@app.post("/stream")
async def stream(request: Request):
    payload = await request.json()
    payload.setdefault("stream", True)

    server = get_least_loaded_server()
    OLLAMA_BASE = f"http://{server['ip']}:{server['port']}"
    server['current_load'] += 1   
    print(f"Routing to server: {server['name']} at {server['ip']}:{server['port']} with current load {server['current_load']}")
    async def ndjson():
        try: 
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", f"{OLLAMA_BASE}/stream", json=payload) as r:
                    print(r)
                    if r.status_code != 200:
                        body = await r.aread()
                        print(body)
                        raise HTTPException(r.status_code, body.decode("utf-8", "ignore"))
                    async for line in r.aiter_lines():
                        if not line:
                            continue
                        yield line + "\n"
        finally:
            server['current_load'] -= 1

    return StreamingResponse(ndjson(), media_type="application/x-ndjson")


@app.get("/healthz")
async def health():
    server = get_least_loaded_server()
    OLLAMA_BASE = f"http://{server['ip']}:{server['port']}"

    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(f"{OLLAMA_BASE}/api/tags")
            r.raise_for_status()
        return PlainTextResponse("ok")
    except Exception as e:
        raise HTTPException(503, str(e))
