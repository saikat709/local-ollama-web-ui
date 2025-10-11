from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware

import os, json, httpx, asyncio
from typing import Dict, Any
import asyncio, logging

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

import csv, os
from datetime import datetime

from server import OLLAMA_BASE

stream_gate = asyncio.Semaphore(1)
log = logging.getLogger(__name__)

# Lock to protect servers list and a round-robin pointer for tie-breaking
servers_lock = asyncio.Lock()
rr_index = 0

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

# how many times to retry a request to a different backend on transient network errors
MAX_RETRIES = 2

# shared HTTP client to benefit from connection pooling
shared_client: httpx.AsyncClient | None = None


system_prompt = """
You are the official assistant for the "BDAIO Qualifier Round" ML competition.

Your name: *BDAIO Qualifier Round Bot*  
Your purpose: Help participants with code, documentation, and dataset-related queries for the competition.  

### Behavior Rules:
1. *Primary Function*: Provide only code and documentation support relevant to the competition.  
   - Examples: dataset loading, metric implementation, submission formatting, evaluation scripts, data preprocessing, feature extraction, or model training (from scratch).  
   - Do *not* generate essays, opinions, personal reflections, jokes, or roleplay.  

2. *Response Style*:
   - Be concise and professional.
   - Never exceed *400 words*.
   - If code is requested, respond with *code only* (no explanations) unless explicitly asked for an explanation.
   - Format all code in proper Markdown blocks using ```language syntax highlighting.

3. *Content Restrictions*:
   - No hate speech, harassment, political content, or personal commentary.
   - No external pretrained model usage suggestions unless explicitly allowed (e.g., BERT, GPT, or HF models are not permitted).
   - No references to unapproved datasets or APIs.

4. *Contest-Specific Boundaries*:
   - Do not leak solution data or reveal private test labels.
   - Do not generate or share direct answers to competition test data.
   - Always remind users to follow the competition rules if their request risks violating them.

5. *Help Scope*:
   - Assist with: Python (Pandas, NumPy, scikit-learn, PyTorch, TensorFlow), metric design, CSV formatting, data validation, and error debugging.
   - You may help with small algorithmic pseudocode or formula derivations relevant to ML tasks.
   - Reject requests unrelated to the competition scope.

6. *Tone*:
   - Strictly professional, factual, and focused on problem-solving.
   - No unnecessary greetings or conversational fluff.

7. *Failure Protocol*:
   - If a request violates competition rules, respond with:
     “This request is not permitted under BDAIO Qualifier Round rules.”

8. *Response Format*:
   - Code snippets should be provided in Markdown format with appropriate syntax highlighting.
   - Do not include comments in the code to explain key steps or decisions, if not needed.
   - If applicable, provide a brief overview of the code's purpose and functionality.
   - Answers should be clear, concise, and directly address the user's query.

You are optimized for helping contestants efficiently within these limits.
"""


servers = [
    {
        'name': 'Sakib Vai PC',
        'ip': '10.47.0.140',
        'port': '8000',
        'current_load': 0,
        'is_active': True,
        'max_concurrency': 6,
    },
    {
        'name': 'Darun Nayeem Laptop',
        'ip': '10.100.200.236',
        'port': '8000',
        'current_load': 0,
        'is_active': True,
        'max_concurrency': 6,
    },
     {
        'name': 'Tausif Vai PC',
        'ip': '10.100.201.127',
        'port': '8000',
        'current_load': 0,
        'is_active': True,
        'max_concurrency': 6,
    },
    {
        'name': 'Server Pc 1',
        'ip': '10.42.0.155',
        'port': '8000',
        'current_load': 0,
        'is_active': True,
        'max_concurrency': 6,
    },
    {
        'name': 'Arif Vai PC',
        'ip': '10.47.0.136',
        'port': '8000',
        'current_load': 0,
        'is_active': True,
        'max_concurrency': 6,
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
    {
        'name': 'Akkhar PC',
        'ip': '10.100.202.160',
        'port': '8000',
        'current_load': 0,
        'is_active': True,
    }, 
    {
        'name': 'Ratul PC',
        'ip': '10.100.202.164',
        'port': '8000',
        'current_load': 0,
        'is_active': True,
    },
    {
        'name' : 'Nafis PC',
        'ip' : '10.100.202.173',
        'port' : '8000',
        'current_load' : 0,
        'is_active' : True
    }
]


def log_request(client_ip: str, prompt: str, handling_server: str):
    ip_filename = f"logs/{client_ip}.csv"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = [client_ip, handling_server, now, prompt]
    header = ["client_ip", "handling_server", "date_time", "prompt"]

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
    # Run an initial health check and then start a background loop to keep server health updated.
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

    # start background health loop
    async def background_health_loop(interval: float = 10.0):
        while True:
            try:
                tasks = [_check_server_health(s, timeout=3.0) for s in servers]
                results = await asyncio.gather(*tasks)
                # print brief summary
                active = sum(1 for r in results if r['ok'])
                inactive = len(results) - active
                print(f"[health-loop] Active: {active}, Inactive: {inactive}")
            except Exception as e:
                print("Health loop error:", e)
            await asyncio.sleep(interval)

    asyncio.create_task(background_health_loop(10.0))

    # initialize shared httpx client
    global shared_client
    if shared_client is None:
        shared_client = httpx.AsyncClient(timeout=300.0)


@app.on_event("shutdown")
async def on_shutdown():
    global shared_client
    if shared_client is not None:
        await shared_client.aclose()
        shared_client = None


async def acquire_server():
    """Select a server (least loaded with round-robin tie-break), increment its load and return it.

    Raises HTTPException(503) when no active servers are available.
    """
    global rr_index
    async with servers_lock:
        active_servers = [s for s in servers if s.get('is_active')]
        if not active_servers:
            raise HTTPException(status_code=503, detail="No active backend servers")

        # prefer servers that are below their max_concurrency
        available = [s for s in active_servers if s.get('current_load', 0) < s.get('max_concurrency', 9999)]
        pool = available if available else active_servers

        # find minimal load among the pool
        min_load = min(s['current_load'] for s in pool)
        candidates = [s for s in pool if s['current_load'] == min_load]

        # round-robin among candidates to avoid always picking the first
        chosen = candidates[rr_index % len(candidates)]
        rr_index = (rr_index + 1) % max(1, len(candidates))

        chosen['current_load'] += 1
        return chosen


async def release_server(server: dict):
    """Decrement server current_load under lock. Never go below zero."""
    async with servers_lock:
        try:
            server['current_load'] = max(0, server.get('current_load', 0) - 1)
        except Exception:
            server['current_load'] = 0


async def get_least_loaded_server():
    """Return the current least loaded active server without modifying state.
    (kept for compatibility in places where we don't need to acquire a server).
    """
    async with servers_lock:
        active_servers = [s for s in servers if s.get('is_active')]
        if not active_servers:
            raise HTTPException(status_code=503, detail="No active backend servers")
        least_loaded_server = min(active_servers, key=lambda x: x['current_load'])
        return least_loaded_server


@app.get("/servers")
async def servers_status():
    """Return list of servers with load and health info."""
    async with servers_lock:
        out = [
            {
                'name': s['name'],
                'ip': s['ip'],
                'port': s['port'],
                'current_load': s.get('current_load', 0),
                'is_active': bool(s.get('is_active', False)),
            }
            for s in servers
        ]
    return JSONResponse({'servers': out})


@app.post("/servers/{name}/activate")
async def activate_server(name: str):
    async with servers_lock:
        for s in servers:
            if s['name'] == name:
                s['is_active'] = True
                return JSONResponse({'ok': True, 'server': s['name']})
    raise HTTPException(status_code=404, detail="server not found")


@app.post("/servers/{name}/deactivate")
async def deactivate_server(name: str):
    async with servers_lock:
        for s in servers:
            if s['name'] == name:
                s['is_active'] = False
                return JSONResponse({'ok': True, 'server': s['name']})
    raise HTTPException(status_code=404, detail="server not found")



@app.post("/generate")
@limiter.limit("1/minute")
async def generate(request: Request):
    client_host = request.client.host if request.client else "unknown"
    payload = await request.json()
    payload["stream"] = False
    payload["prompt"] = system_prompt + "\n\n User query is: " + payload.get("prompt", "")

    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        server = await acquire_server()
        OLLAMA_BASE = f"http://{server['ip']}:{server['port']}"

        log_request(client_host, payload.get("prompt", "").strip(), server['name'])
        print(f"Routing to server: {server['name']} at {server['ip']}:{server['port']} (attempt {attempt}) load={server['current_load']}")

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                r = await client.post(f"{OLLAMA_BASE}/generate", json=payload)
                if r.status_code != 200:
                    body = r.text if r.text is not None else ""
                    raise HTTPException(r.status_code, body)
                data = r.json()
                return JSONResponse({"response": data.get("response", "")})
        except (httpx.RemoteProtocolError, httpx.ReadError, httpx.ConnectError, httpx.RequestError) as e:
            log.warning("Upstream failed (attempt %d): %r", attempt, e)
            last_exc = e
            async with servers_lock:
                server['is_active'] = False
        finally:
            await release_server(server)
    raise HTTPException(status_code=503, detail=f"All backend attempts failed: {last_exc}")


@app.post("/stream")
@limiter.limit("1/minute")
async def stream(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    payload = await request.json()
    payload.setdefault("stream", True)

    log_request(client_ip, payload.get("prompt", "").strip(), "-")
    payload["prompt"] = system_prompt + "\n\n User query is: " + payload.get("prompt", "")

    # print(payload["prompt"])

    async def ndjson():
        for attempt in range(1, MAX_RETRIES + 1):
            server = await acquire_server()
            OLLAMA_BASE = f"http://{server['ip']}:{server['port']}"
            yielded_any = False
            released = False
            print(f"Routing to server: {server['name']} at {server['ip']}:{server['port']} (attempt {attempt}) load={server['current_load']}")
            try:
                async with httpx.AsyncClient(timeout=None) as client:
                    async with client.stream("POST", f"{OLLAMA_BASE}/stream", json=payload) as r:
                        if r.status_code != 200:
                            body = await r.aread()
                            raise HTTPException(r.status_code, body.decode("utf-8", "ignore"))
                        async for line in r.aiter_lines():
                            if not line:
                                continue
                            yielded_any = True
                            yield line + "\n"
                        return

            except (httpx.RemoteProtocolError, httpx.ReadError, httpx.ConnectError, httpx.RequestError) as e:
                log.warning("Upstream aborted early (attempt %d): %r", attempt, e)
                async with servers_lock:
                    server['is_active'] = False
                await release_server(server)
                released = True
                if yielded_any:
                    return
                else:
                    continue
            finally:
                if not released:
                    await release_server(server)
        return

    return StreamingResponse(ndjson(), media_type="application/x-ndjson")


@app.get("/healthz")
@limiter.limit("122/minute")
async def health(request: Request):
    server = await get_least_loaded_server()
    OLLAMA_BASE = f"http://{server['ip']}:{server['port']}"

    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(f"{OLLAMA_BASE}/api/tags")
            r.raise_for_status()
        return PlainTextResponse("ok")
    except Exception as e:
        raise HTTPException(503, str(e))
