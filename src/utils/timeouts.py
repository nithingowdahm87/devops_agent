"""Request timeout decorator and utilities."""
import httpx
from functools import wraps
from typing import Callable, ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")


def with_timeout(seconds: float):
    """Decorator that injects an httpx.AsyncClient with the given timeout.

    Usage:
        @with_timeout(10.0)
        async def my_func(prompt: str, _http_client: httpx.AsyncClient):
            response = await _http_client.post("https://api.example.com", json={"prompt": prompt})
            return response.json()
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            async with httpx.AsyncClient(timeout=httpx.Timeout(seconds)) as client:
                kwargs["_http_client"] = client
                return await func(*args, **kwargs)

        return wrapper

    return decorator