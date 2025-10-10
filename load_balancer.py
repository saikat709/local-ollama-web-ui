from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware

import os, json, httpx, asyncio
from typing import Dict, Any

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

import csv, os
from datetime import datetime

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

limiter = Limiter(key_func=get_remote_address, default_limits=["200/day", "50/hour"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


servers = [
    {
        'name': 'Sakib Vai PC',
        'ip': '10.47.0.140',
        'port': '8000',
        'current_load': 0,
        'is_active': True,
    },
    {
        'name': 'Darun Nayeem Laptop',
        'ip': '10.100.200.236',
        'port': '8000',
        'current_load': 0,
        'is_active': True,
    },
     {
        'name': 'Tausif Vai PC',
        'ip': '10.100.201.127',
        'port': '8000',
        'current_load': 0,
        'is_active': True,
    },
    {
        'name': 'Server Pc 1',
        'ip': '10.42.0.155',
        'port': '8000',
        'current_load': 0,
        'is_active': True,
    },
    {
        'name': 'Arif Vai PC',
        'ip': '10.47.0.136',
        'port': '8000',
        'current_load': 0,
        'is_active': True,
    },
    {
        'name': 'Proma Apu PC',
        'ip': '10.47.0.109',
        'port': '8000',
        'current_load': 0,
        'is_active': True,
    },
    {
        'name': 'Nahid Vai PC Left',
        'ip': '10.47.0.105',
        'port': '8000',
        'current_load': 0,
        'is_active': True,
    },
    {
        'name': 'Dipshika Apu PC',
        'ip': '10.47.0.130',
        'port': '8000',
        'current_load': 0,
        'is_active': True,
    },
]


def log_request(request: Request, prompt: str, handling_server: str):
    ip = "1.1.1.1" #request.headers.get("X-Forwarded-For", flask_request.remote_addr)
    ip_filename = f"logs/{ip}.csv"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = [ip, handling_server, now, prompt]
    header = ["ip", "handling_server", "date_time", "prompt"]

    # Write to both global log and per-IP log
    for filename in ["logs.csv", ip_filename]:
        file_exists = os.path.isfile(filename)
        with open(filename, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(header)
            writer.writerow(row)


async def _check_server_health(server: Dict[str, Any], timeout: float = 5.0) -> Dict[str, Any]:
    """Async check of a server's /healthz endpoint. Returns a small result dict."""
    url = f"http://{server['ip']}:{server['port']}/healthz"
    start = asyncio.get_event_loop().time()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(url)
            body = r.text.strip() if r.text is not None else ""
            ok = r.status_code == 200 and (body == "" or body.lower() in ("ok", "okay", "healthy"))
            elapsed = asyncio.get_event_loop().time() - start
            server['is_active'] = bool(ok)
            return {
                'server': server.get('name'),
                'url': url,
                'status_code': r.status_code,
                'body': body,
                'ok': ok,
                'elapsed': elapsed,
            }
    except Exception as e:
        elapsed = asyncio.get_event_loop().time() - start
        server['is_active'] = False
        return {
            'server': server.get('name'),
            'url': url,
            'status_code': None,
            'body': str(e),
            'ok': False,
            'elapsed': elapsed,
        }


@app.on_event("startup")
async def on_startup_health_check():
    tasks = [_check_server_health(s, timeout=5.0) for s in servers]
    results = await asyncio.gather(*tasks)

    ok_count = 0
    fail_count = 0
    for r in results:
        if r['ok']:
            ok_count += 1
            print(f"[OK]   {r['server']:20} {r['url']:30} ({r['elapsed']:.2f}s) -> {r['body']}")
        else:
            fail_count += 1
            code = r['status_code'] or 'ERR'
            print(f"[FAIL] {r['server']:20} {r['url']:30} ({r['elapsed']:.2f}s) -> {code} {r['body']}")

    print(f"Initial health check complete. Active: {ok_count}, Inactive: {fail_count}")


def get_least_loaded_server():
    active_servers = [s for s in servers if s['is_active']]
    if not active_servers:
        raise HTTPException(status_code=503, detail="No active backend servers")
    least_loaded_server = min(active_servers, key=lambda x: x['current_load'])
    return least_loaded_server



@app.post("/generate")
@limiter.limit("122/minute")
async def generate(request: Request):
    payload = await request.json()
    payload["stream"] = False
    server = get_least_loaded_server()
    OLLAMA_BASE = f"http://{server['ip']}:{server['port']}"
    server['current_load'] += 1

    log_request(request, payload.get("prompt", "").strip(), server['name'])

    print(f"Routing to server: {server['name']} at {server['ip']}:{server['port']} with current load {server['current_load']}")
    async with httpx.AsyncClient(timeout=300.0) as client:
        r = await client.post(f"{OLLAMA_BASE}/generate", json=payload)
        if r.status_code != 200:
            raise HTTPException(r.status_code, r.text)
        data = r.json()
        server['current_load'] -= 1
        return JSONResponse({"response": data.get("response", "")})


@app.post("/stream")
@limiter.limit("122/minute")
async def stream(request: Request):
    payload = await request.json()
    payload.setdefault("stream", True)

    server = get_least_loaded_server()
    OLLAMA_BASE = f"http://{server['ip']}:{server['port']}"
    server['current_load'] += 1 

    log_request(request, payload.get("prompt", "").strip(), server['name'])

    print(f"Routing to server: {server['name']} at {server['ip']}:{server['port']} with current load {server['current_load']}")
    async def ndjson():
        try: 
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", f"{OLLAMA_BASE}/stream", json=payload) as r:
                    print(r)
                    if r.status_code != 200:
                        body = await r.aread()
                        raise HTTPException(r.status_code, body.decode("utf-8", "ignore"))
                    async for line in r.aiter_lines():
                        if not line:
                            continue
                        yield line + "\n"
        finally:
            server['current_load'] -= 1

    return StreamingResponse(ndjson(), media_type="application/x-ndjson")


@app.get("/healthz")
@limiter.limit("122/minute")
async def health(request: Request):
    server = get_least_loaded_server()
    OLLAMA_BASE = f"http://{server['ip']}:{server['port']}"

    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(f"{OLLAMA_BASE}/api/tags")
            r.raise_for_status()
        return PlainTextResponse("ok")
    except Exception as e:
        raise HTTPException(503, str(e))
