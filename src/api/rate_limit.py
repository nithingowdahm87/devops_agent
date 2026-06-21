from limits import RateLimitItemPerMinute
from limits.strategies import MovingWindowRateLimiter
from limits.storage import MemoryStorage
from src.config.settings import settings

storage = MemoryStorage()
limiter = MovingWindowRateLimiter(storage)

def check_limit(key: str, limit: str = None) -> bool:
    """Check if key is within rate limit. Returns True if allowed."""
    limit_str = limit or settings.RATE_LIMIT_DEFAULT
    item = RateLimitItemPerMinute(int(limit_str.split("/")[0]))
    return limiter.hit(item, key)