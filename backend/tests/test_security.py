import time

from app.core.security import RateLimiter


def test_rate_limiter_allows_up_to_limit():
    limiter = RateLimiter(limit=3, window=60.0)
    for _ in range(3):
        ok, _ = limiter.check("user-a")
        assert ok is True
    ok, retry_after = limiter.check("user-a")
    assert ok is False
    assert retry_after > 0


def test_rate_limiter_keys_are_independent():
    limiter = RateLimiter(limit=1, window=60.0)
    ok_a, _ = limiter.check("a")
    ok_b, _ = limiter.check("b")
    assert ok_a is True
    assert ok_b is True


def test_rate_limiter_window_expiry():
    limiter = RateLimiter(limit=1, window=0.05)
    ok1, _ = limiter.check("x")
    assert ok1 is True
    ok2, _ = limiter.check("x")
    assert ok2 is False
    time.sleep(0.07)
    ok3, _ = limiter.check("x")
    assert ok3 is True
