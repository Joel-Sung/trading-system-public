from collections.abc import Callable
from time import sleep
from typing import TypeVar

from custom_types.market import (
    APIRateLimitExceededError,
)

T = TypeVar("T")


def retry_on_rate_limit(
    func: Callable[[], T],
    retries: int = 3,
    delay: float = 60,
) -> T:
    for attempt in range(retries):
        try:
            return func()
        except APIRateLimitExceededError:
            if attempt == retries - 1:
                raise
            sleep(delay)
