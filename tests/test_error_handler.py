"""Tests for lib/error_handler.py"""

import time
import pytest

from lib.error_handler import LLMRetryPolicy, RetryExhaustedError, with_retry


class TestLLMRetryPolicy:
    def test_success_on_first_try(self):
        policy = LLMRetryPolicy(max_attempts=3)
        result = policy.call_with_retry(lambda: 42)
        assert result == 42
        assert policy.total_calls == 1
        assert policy.total_retries == 0

    def test_success_on_second_try(self):
        call_count = [0]
        def flaky():
            call_count[0] += 1
            if call_count[0] < 2:
                raise ConnectionError("Temporary failure")
            return "success"

        policy = LLMRetryPolicy(max_attempts=3, base_delay=0.01)
        result = policy.call_with_retry(flaky)
        assert result == "success"
        assert call_count[0] == 2
        assert policy.total_retries == 1

    def test_all_attempts_fail(self):
        def always_fail():
            raise ConnectionError("Always fails")

        policy = LLMRetryPolicy(max_attempts=3, base_delay=0.01)
        with pytest.raises(RetryExhaustedError) as exc_info:
            policy.call_with_retry(always_fail)

        assert exc_info.value.attempts == 3
        assert isinstance(exc_info.value.last_error, ConnectionError)
        assert policy.total_failures == 1

    def test_exponential_backoff_delays(self):
        policy = LLMRetryPolicy(
            max_attempts=4,
            base_delay=1.0,
            multiplier=2.0,
        )
        assert policy._calculate_delay(1) == 1.0
        assert policy._calculate_delay(2) == 2.0
        assert policy._calculate_delay(3) == 4.0
        assert policy._calculate_delay(4) == 8.0

    def test_delay_capped_at_max(self):
        policy = LLMRetryPolicy(
            base_delay=10.0,
            max_delay=15.0,
            multiplier=2.0,
        )
        assert policy._calculate_delay(3) == 15.0  # 10 * 4 = 40 > 15

    def test_retryable_exceptions_filter(self):
        """Only retry specific exception types"""
        call_count = [0]
        def raises_value_error():
            call_count[0] += 1
            raise ValueError("Not retryable")

        policy = LLMRetryPolicy(
            max_attempts=3,
            base_delay=0.01,
            retryable_exceptions=(ConnectionError,),
        )

        # ValueError should NOT be retried
        with pytest.raises(ValueError):
            policy.call_with_retry(raises_value_error)

        assert call_count[0] == 1  # Only one attempt

    def test_get_stats(self):
        policy = LLMRetryPolicy(max_attempts=2, base_delay=0.01)

        # Success
        policy.call_with_retry(lambda: 1)

        # Failure
        try:
            policy.call_with_retry(lambda: (_ for _ in ()).throw(Exception("fail")))
        except RetryExhaustedError:
            pass

        stats = policy.get_stats()
        assert stats['total_calls'] == 2
        assert stats['success_rate'] > 0


class TestWithRetryDecorator:
    def test_decorator_success(self):
        @with_retry(max_attempts=2, base_delay=0.01)
        def success():
            return "ok"

        assert success() == "ok"

    def test_decorator_retries(self):
        counter = [0]

        @with_retry(max_attempts=3, base_delay=0.01)
        def flaky():
            counter[0] += 1
            if counter[0] < 3:
                raise ConnectionError("retry me")
            return "done"

        result = flaky()
        assert result == "done"
        assert counter[0] == 3
