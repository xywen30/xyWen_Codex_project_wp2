from __future__ import annotations

import time
from collections.abc import Callable


def conservative_retry(call: Callable, attempts: int = 2, base_delay: float = 1.5):
    last = None
    for index in range(attempts):
        try:
            return call()
        except Exception as exc:
            last = exc
            if index + 1 < attempts:
                time.sleep(base_delay * (2**index))
    raise last
