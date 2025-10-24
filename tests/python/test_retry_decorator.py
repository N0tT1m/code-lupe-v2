"""
Comprehensive tests for retry decorator and circuit breaker
Uses extensive mocking to test edge cases
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock, call
from src.python.utils.retry_decorator import (
    retry_with_backoff,
    async_retry_with_backoff,
    CircuitBreaker
)


class TestRetryDecorator:
    """Tests for retry_with_backoff decorator"""

    def test_successful_execution_no_retry(self):
        """Test that successful function doesn't retry"""
        mock_func = Mock(return_value="success")
        decorated = retry_with_backoff(max_retries=3)(mock_func)

        result = decorated()

        assert result == "success"
        assert mock_func.call_count == 1

    def test_retry_on_exception(self):
        """Test that function retries on exception"""
        mock_func = Mock(side_effect=[
            ConnectionError("fail 1"),
            ConnectionError("fail 2"),
            "success"
        ])
        decorated = retry_with_backoff(
            max_retries=3,
            base_delay=0.01,  # Fast for testing
            exceptions=(ConnectionError,)
        )(mock_func)

        result = decorated()

        assert result == "success"
        assert mock_func.call_count == 3

    def test_max_retries_exceeded(self):
        """Test that exception is raised after max retries"""
        mock_func = Mock(side_effect=ConnectionError("always fails"))
        decorated = retry_with_backoff(
            max_retries=3,
            base_delay=0.01,
            exceptions=(ConnectionError,)
        )(mock_func)

        with pytest.raises(ConnectionError, match="always fails"):
            decorated()

        assert mock_func.call_count == 3

    def test_exponential_backoff(self):
        """Test exponential backoff calculation"""
        mock_func = Mock(side_effect=[
            ConnectionError("fail"),
            ConnectionError("fail"),
            "success"
        ])

        with patch('time.sleep') as mock_sleep:
            decorated = retry_with_backoff(
                max_retries=3,
                base_delay=1.0,
                exponential_base=2.0
            )(mock_func)

            decorated()

            # Check sleep was called with exponentially increasing delays
            sleep_calls = [call.args[0] for call in mock_sleep.call_args_list]
            assert len(sleep_calls) == 2
            assert sleep_calls[0] == 1.0  # 1.0 * (2 ** 0)
            assert sleep_calls[1] == 2.0  # 1.0 * (2 ** 1)

    def test_max_delay_cap(self):
        """Test that delay is capped at max_delay"""
        mock_func = Mock(side_effect=[
            ConnectionError("fail"),
            ConnectionError("fail"),
            "success"
        ])

        with patch('time.sleep') as mock_sleep:
            decorated = retry_with_backoff(
                max_retries=3,
                base_delay=10.0,
                max_delay=5.0,
                exponential_base=2.0
            )(mock_func)

            decorated()

            # Both delays should be capped at 5.0
            sleep_calls = [call.args[0] for call in mock_sleep.call_args_list]
            assert all(delay <= 5.0 for delay in sleep_calls)

    def test_specific_exceptions_only(self):
        """Test that only specified exceptions trigger retry"""
        mock_func = Mock(side_effect=ValueError("wrong exception"))
        decorated = retry_with_backoff(
            max_retries=3,
            base_delay=0.01,
            exceptions=(ConnectionError, TimeoutError)
        )(mock_func)

        with pytest.raises(ValueError, match="wrong exception"):
            decorated()

        # Should not retry for ValueError
        assert mock_func.call_count == 1

    def test_on_retry_callback(self):
        """Test that retry callback is called"""
        mock_callback = Mock()
        mock_func = Mock(side_effect=[
            ConnectionError("fail"),
            "success"
        ])

        decorated = retry_with_backoff(
            max_retries=3,
            base_delay=0.01,
            on_retry=mock_callback
        )(mock_func)

        decorated()

        # Callback should be called once with attempt number and exception
        assert mock_callback.call_count == 1
        call_args = mock_callback.call_args[0]
        assert call_args[0] == 0  # First retry (attempt 0)
        assert isinstance(call_args[1], ConnectionError)

    def test_on_retry_callback_exception(self):
        """Test that callback exceptions don't break retry logic"""
        mock_callback = Mock(side_effect=RuntimeError("callback failed"))
        mock_func = Mock(side_effect=[
            ConnectionError("fail"),
            "success"
        ])

        with patch('utils.retry_decorator.logger') as mock_logger:
            decorated = retry_with_backoff(
                max_retries=3,
                base_delay=0.01,
                on_retry=mock_callback
            )(mock_func)

            result = decorated()

            assert result == "success"
            # Should log callback error
            assert any("callback failed" in str(call) for call in mock_logger.error.call_args_list)

    def test_function_with_args_and_kwargs(self):
        """Test that decorated function preserves args and kwargs"""
        mock_func = Mock(return_value="success")
        decorated = retry_with_backoff(max_retries=3)(mock_func)

        result = decorated(1, 2, key="value")

        assert result == "success"
        mock_func.assert_called_once_with(1, 2, key="value")

    def test_functools_wraps_preserves_metadata(self):
        """Test that functools.wraps preserves function metadata"""
        def original_function():
            """Original docstring"""
            return "success"

        decorated = retry_with_backoff(max_retries=3)(original_function)

        assert decorated.__name__ == "original_function"
        assert decorated.__doc__ == "Original docstring"


@pytest.mark.asyncio
class TestAsyncRetryDecorator:
    """Tests for async_retry_with_backoff decorator"""

    async def test_async_successful_execution(self):
        """Test successful async function execution"""
        async def success_func():
            return "async success"

        decorated = async_retry_with_backoff(max_retries=3)(success_func)
        result = await decorated()

        assert result == "async success"

    async def test_async_retry_on_exception(self):
        """Test async retry on exception"""
        call_count = 0

        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError(f"fail {call_count}")
            return "async success"

        decorated = async_retry_with_backoff(
            max_retries=3,
            base_delay=0.01,
            exceptions=(ConnectionError,)
        )(flaky_func)

        result = await decorated()

        assert result == "async success"
        assert call_count == 3

    async def test_async_max_retries_exceeded(self):
        """Test async function raises after max retries"""
        async def always_fails():
            raise TimeoutError("async timeout")

        decorated = async_retry_with_backoff(
            max_retries=3,
            base_delay=0.01,
            exceptions=(TimeoutError,)
        )(always_fails)

        with pytest.raises(TimeoutError, match="async timeout"):
            await decorated()


class TestCircuitBreaker:
    """Tests for CircuitBreaker pattern"""

    def test_circuit_breaker_closed_state(self):
        """Test circuit breaker allows calls in closed state"""
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=5.0)
        mock_func = Mock(return_value="success")

        decorated = breaker(mock_func)
        result = decorated()

        assert result == "success"
        assert breaker.state == "closed"
        assert breaker.failure_count == 0

    def test_circuit_breaker_opens_after_threshold(self):
        """Test circuit breaker opens after failure threshold"""
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=5.0)
        mock_func = Mock(side_effect=ConnectionError("fail"))

        decorated = breaker(mock_func)

        # First 3 failures should raise exception and open circuit
        for i in range(3):
            with pytest.raises(ConnectionError):
                decorated()

        assert breaker.state == "open"
        assert breaker.failure_count == 3

    def test_circuit_breaker_rejects_calls_when_open(self):
        """Test circuit breaker rejects calls in open state"""
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=5.0)
        mock_func = Mock(side_effect=ConnectionError("fail"))

        decorated = breaker(mock_func)

        # Trigger circuit breaker to open
        for _ in range(2):
            with pytest.raises(ConnectionError):
                decorated()

        # Now circuit is open, should reject immediately
        with pytest.raises(Exception, match="Circuit breaker is OPEN"):
            decorated()

        # Original function should not be called when circuit is open
        assert mock_func.call_count == 2  # Only initial failures

    def test_circuit_breaker_half_open_state(self):
        """Test circuit breaker enters half-open state after timeout"""
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        call_count = 0

        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ConnectionError("fail")
            return "success"

        decorated = breaker(flaky_func)

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ConnectionError):
                decorated()

        assert breaker.state == "open"

        # Wait for recovery timeout
        time.sleep(0.15)

        # Next call should enter half-open and succeed
        result = decorated()

        assert result == "success"
        assert breaker.state == "closed"
        assert breaker.failure_count == 0

    def test_circuit_breaker_reopens_on_half_open_failure(self):
        """Test circuit reopens if call fails in half-open state"""
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        mock_func = Mock(side_effect=ConnectionError("fail"))

        decorated = breaker(mock_func)

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ConnectionError):
                decorated()

        # Wait for recovery timeout
        time.sleep(0.15)

        # Failure in half-open state should reopen circuit
        with pytest.raises(ConnectionError):
            decorated()

        assert breaker.state == "open"

    def test_circuit_breaker_specific_exception_type(self):
        """Test circuit breaker only counts specific exception types"""
        breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=5.0,
            expected_exception=ConnectionError
        )

        def mixed_failures(failure_type):
            if failure_type == "connection":
                raise ConnectionError("connection fail")
            else:
                raise ValueError("value fail")

        decorated = breaker(mixed_failures)

        # ValueError should not count towards failure threshold
        with pytest.raises(ValueError):
            decorated("value")

        assert breaker.failure_count == 0
        assert breaker.state == "closed"

        # ConnectionError should count
        with pytest.raises(ConnectionError):
            decorated("connection")

        assert breaker.failure_count == 1

    @patch('utils.retry_decorator.logger')
    def test_circuit_breaker_logging(self, mock_logger):
        """Test circuit breaker logs state changes"""
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        mock_func = Mock(side_effect=ConnectionError("fail"))

        decorated = breaker(mock_func)

        # Trigger circuit to open
        for _ in range(2):
            with pytest.raises(ConnectionError):
                decorated()

        # Check error logging when circuit opens
        assert any("is now OPEN" in str(call) for call in mock_logger.error.call_args_list)

        # Wait for recovery
        time.sleep(0.15)

        # Next call should log half-open state
        with pytest.raises(ConnectionError):
            decorated()

        assert any("half-open state" in str(call) for call in mock_logger.info.call_args_list)


class TestRetryIntegration:
    """Integration tests combining retry and circuit breaker"""

    def test_retry_with_circuit_breaker(self):
        """Test retry decorator combined with circuit breaker"""
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=5.0)
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        @breaker
        def unstable_service():
            nonlocal call_count
            call_count += 1
            if call_count < 5:
                raise ConnectionError(f"fail {call_count}")
            return "success"

        # Should eventually succeed with retries
        with pytest.raises(ConnectionError):
            unstable_service()

        # Circuit should be open after failures
        assert breaker.state == "open"


def test_real_world_database_connection():
    """Real-world example: database connection with retries"""
    connection_attempts = []

    @retry_with_backoff(
        max_retries=5,
        base_delay=1.0,
        exponential_base=2.0,
        exceptions=(ConnectionError, TimeoutError)
    )
    def connect_to_database(host, port):
        connection_attempts.append((host, port))
        if len(connection_attempts) < 3:
            raise ConnectionError(f"Connection refused (attempt {len(connection_attempts)})")
        return f"Connected to {host}:{port}"

    with patch('time.sleep'):  # Speed up test
        result = connect_to_database("localhost", 5432)

    assert result == "Connected to localhost:5432"
    assert len(connection_attempts) == 3


def test_real_world_api_call_with_circuit_breaker():
    """Real-world example: API calls with circuit breaker"""
    breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)
    api_calls = []

    @breaker
    def call_external_api(endpoint):
        api_calls.append(endpoint)
        # Simulate API failure
        raise ConnectionError("API unavailable")

    # Make calls until circuit opens
    for i in range(5):
        with pytest.raises(ConnectionError):
            call_external_api(f"/api/v1/data/{i}")

    assert breaker.state == "open"

    # Next call should fail immediately without hitting API
    with pytest.raises(Exception, match="Circuit breaker is OPEN"):
        call_external_api("/api/v1/data/6")

    # Should have only made 5 actual API calls
    assert len(api_calls) == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
