"""
Error Handler for OC-Memory
LLM API retry policy with exponential backoff

Provides automatic retry logic for LLM API calls
with configurable backoff strategy.
"""

import logging
import time
from functools import wraps
from typing import Callable, Any, Optional, Type, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# Retry Policy
# =============================================================================

class RetryExhaustedError(Exception):
    """All retry attempts exhausted"""
    def __init__(self, last_error: Exception, attempts: int):
        self.last_error = last_error
        self.attempts = attempts
        super().__init__(f"All {attempts} retry attempts exhausted: {last_error}")


class LLMRetryPolicy:
    """
    Retry policy with exponential backoff for LLM API calls.

    Default: 3 attempts with delays of 2s, 4s, 8s
    """

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 2.0,
        max_delay: float = 30.0,
        multiplier: float = 2.0,
        retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    ):
        """
        Args:
            max_attempts: Maximum number of retry attempts
            base_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
            multiplier: Delay multiplier for exponential backoff
            retryable_exceptions: Exception types to retry (default: all)
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.multiplier = multiplier
        self.retryable_exceptions = retryable_exceptions or (Exception,)

        # Statistics
        self.total_calls = 0
        self.total_retries = 0
        self.total_failures = 0

    def call_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """
        Call a function with retry logic.

        Args:
            func: Function to call
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function return value

        Raises:
            RetryExhaustedError: If all attempts fail
        """
        self.total_calls += 1
        last_error = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                result = func(*args, **kwargs)
                if attempt > 1:
                    logger.info(f"Succeeded on attempt {attempt}")
                return result

            except self.retryable_exceptions as e:
                last_error = e
                if attempt < self.max_attempts:
                    delay = self._calculate_delay(attempt)
                    self.total_retries += 1
                    logger.warning(
                        f"Attempt {attempt}/{self.max_attempts} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                else:
                    self.total_failures += 1
                    logger.error(
                        f"All {self.max_attempts} attempts failed. "
                        f"Last error: {e}"
                    )

        raise RetryExhaustedError(last_error, self.max_attempts)

    async def call_with_retry_async(self, func: Callable, *args, **kwargs) -> Any:
        """Async version of call_with_retry"""
        import asyncio

        self.total_calls += 1
        last_error = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                result = await func(*args, **kwargs)
                if attempt > 1:
                    logger.info(f"Succeeded on attempt {attempt}")
                return result

            except self.retryable_exceptions as e:
                last_error = e
                if attempt < self.max_attempts:
                    delay = self._calculate_delay(attempt)
                    self.total_retries += 1
                    logger.warning(
                        f"Attempt {attempt}/{self.max_attempts} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    self.total_failures += 1
                    logger.error(
                        f"All {self.max_attempts} attempts failed. "
                        f"Last error: {e}"
                    )

        raise RetryExhaustedError(last_error, self.max_attempts)

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number"""
        delay = self.base_delay * (self.multiplier ** (attempt - 1))
        return min(delay, self.max_delay)

    def get_stats(self) -> dict:
        """Get retry statistics"""
        return {
            'total_calls': self.total_calls,
            'total_retries': self.total_retries,
            'total_failures': self.total_failures,
            'success_rate': (
                (self.total_calls - self.total_failures) / max(self.total_calls, 1)
            ),
        }


# =============================================================================
# Decorator
# =============================================================================

def with_retry(
    max_attempts: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 30.0,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
):
    """
    Decorator for adding retry logic to functions.

    Usage:
        @with_retry(max_attempts=3)
        def call_llm():
            ...
    """
    policy = LLMRetryPolicy(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        retryable_exceptions=retryable_exceptions,
    )

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            return policy.call_with_retry(func, *args, **kwargs)
        wrapper._retry_policy = policy
        return wrapper

    return decorator
