import os

from slowapi import Limiter
from slowapi.util import get_remote_address


if os.getenv("IS_TESTING"):
    class _NoOpLimiter:
        def limit(self, _rule: str):
            def decorator(func):
                return func

            return decorator


    limiter = _NoOpLimiter()
else:
    limiter = Limiter(key_func=get_remote_address)
