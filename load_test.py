import asyncio
import httpx

URL = "http://127.0.0.1:8000/stream"
payload = {"prompt": "hello", "model": "any", "stream": False}

async def make_one(i):
    async with httpx.AsyncClient() as c:
        r = await c.post(URL, json=payload, timeout=30.0)
        return r.status_code

async def run(n=50):
    tasks = [make_one(i) for i in range(n)]
    res = await asyncio.gather(*tasks, return_exceptions=True)
    print(res.count(200) if isinstance(res, list) else res)

if __name__ == "__main__":
    asyncio.run(run(40))