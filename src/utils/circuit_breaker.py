"""Circuit breaker instances for external service calls."""
from pybreaker import CircuitBreaker
import httpx

# Video generation service breaker
video_breaker = CircuitBreaker(
    fail_max=5,
    reset_timeout=60,
    expected_exception=(httpx.HTTPError, Exception),
)

# GitHub API breaker
github_breaker = CircuitBreaker(
    fail_max=5,
    reset_timeout=60,
    expected_exception=(httpx.HTTPError, Exception),
)