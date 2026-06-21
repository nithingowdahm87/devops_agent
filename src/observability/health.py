import time
import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.config.settings import settings

async def check_db(db: Session) -> dict:
    start = time.time()
    try:
        db.execute(text("SELECT 1"))
        latency = round((time.time() - start) * 1000, 1)
        return {"status": "healthy", "latency_ms": latency}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

async def check_redis() -> dict:
    try:
        # Try async redis if available, otherwise return info
        import asyncio
        try:
            import redis.asyncio as aioredis
            r = aioredis.from_url(settings.REDIS_URL or "redis://localhost:6379")
            await r.ping()
            return {"status": "healthy"}
        except ImportError:
            return {"status": "skipped", "reason": "redis not installed"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

async def check_external_apis() -> dict:
    results = {}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(2.0)) as client:
            r = await client.head("https://api.github.com")
            results["github"] = {"status": "healthy" if r.status_code < 500 else "degraded"}
    except Exception as e:
        results["github"] = {"status": "unhealthy", "error": str(e)}
    return results