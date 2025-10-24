#!/usr/bin/env python3
"""
Retry Decorator with Exponential Backoff
Provides resilient retry logic for transient failures
"""

import time
import logging
from functools import wraps
from typing import Callable, Type, Tuple, Optional

logger = logging.getLogger(__name__)


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable] = None
):
    """
    Decorator that retries a function with exponential backoff

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries (seconds)
        max_delay: Maximum delay between retries (seconds)
        exponential_base: Base for exponential backoff calculation
        exceptions: Tuple of exception types to catch and retry
        on_retry: Optional callback function called on each retry

    Returns:
        Decorated function with retry logic

    Example:
        @retry_with_backoff(max_retries=5, exceptions=(ConnectionError,))
        def fetch_data():
            return requests.get('https://api.example.com/data')
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    # Last attempt - raise the exception
                    if attempt == max_retries - 1:
                        logger.error(
                            f"{func.__name__} failed after {max_retries} attempts: {e}"
                        )
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)

                    logger.warning(
                        f"{func.__name__} attempt {attempt + 1}/{max_retries} failed: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )

                    # Call retry callback if provided
                    if on_retry:
                        try:
                            on_retry(attempt, e)
                        except Exception as callback_error:
                            logger.error(f"Retry callback failed: {callback_error}")

                    time.sleep(delay)

            # Should never reach here, but just in case
            raise RuntimeError(f"{func.__name__} exhausted all retries")

        return wrapper
    return decorator


def async_retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    Async version of retry decorator

    Example:
        @async_retry_with_backoff(max_retries=5)
        async def fetch_data_async():
            async with aiohttp.ClientSession() as session:
                async with session.get('https://api.example.com/data') as resp:
                    return await resp.json()
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            import asyncio

            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries - 1:
                        logger.error(
                            f"{func.__name__} failed after {max_retries} attempts: {e}"
                        )
                        raise

                    delay = min(base_delay * (exponential_base ** attempt), max_delay)

                    logger.warning(
                        f"{func.__name__} attempt {attempt + 1}/{max_retries} failed: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )

                    await asyncio.sleep(delay)

            raise RuntimeError(f"{func.__name__} exhausted all retries")

        return wrapper
    return decorator


class CircuitBreaker:
    """
    Circuit breaker pattern implementation
    Prevents cascading failures by failing fast when error rate is high
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception
    ):
        """
        Initialize circuit breaker

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Time to wait before attempting recovery (seconds)
            expected_exception: Exception type to count as failure
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'closed'  # closed, open, half-open

    def __call__(self, func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            if self.state == 'open':
                # Check if recovery timeout has passed
                if time.time() - self.last_failure_time < self.recovery_timeout:
                    raise Exception(f"Circuit breaker is OPEN for {func.__name__}")
                else:
                    self.state = 'half-open'
                    logger.info(f"Circuit breaker for {func.__name__} entering half-open state")

            try:
                result = func(*args, **kwargs)

                # Success - reset failure count in half-open state
                if self.state == 'half-open':
                    self.state = 'closed'
                    self.failure_count = 0
                    logger.info(f"Circuit breaker for {func.__name__} closed (recovered)")

                return result

            except self.expected_exception as e:
                self.failure_count += 1
                self.last_failure_time = time.time()

                if self.failure_count >= self.failure_threshold:
                    self.state = 'open'
                    logger.error(
                        f"Circuit breaker for {func.__name__} is now OPEN "
                        f"(failures: {self.failure_count})"
                    )

                raise

        return wrapper


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Example 1: Basic retry
    @retry_with_backoff(max_retries=3, base_delay=1)
    def unstable_function():
        import random
        if random.random() < 0.7:  # 70% failure rate
            raise ConnectionError("Connection failed")
        return "Success!"

    # Example 2: Database connection with retry
    @retry_with_backoff(
        max_retries=5,
        base_delay=2,
        exceptions=(ConnectionError, TimeoutError)
    )
    def connect_to_database():
        # Simulated database connection
        import random
        if random.random() < 0.5:
            raise ConnectionError("Database unavailable")
        return "Connected to database"

    # Example 3: Circuit breaker
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=10)

    @breaker
    def call_external_api():
        import random
        if random.random() < 0.8:  # 80% failure rate
            raise ConnectionError("API unavailable")
        return "API response"

    # Test retry decorator
    print("\n=== Testing Retry Decorator ===")
    try:
        result = unstable_function()
        print(f"Result: {result}")
    except Exception as e:
        print(f"Failed: {e}")

    # Test database connection
    print("\n=== Testing Database Connection ===")
    try:
        result = connect_to_database()
        print(f"Result: {result}")
    except Exception as e:
        print(f"Failed: {e}")

    # Test circuit breaker
    print("\n=== Testing Circuit Breaker ===")
    for i in range(10):
        try:
            result = call_external_api()
            print(f"Attempt {i + 1}: {result}")
        except Exception as e:
            print(f"Attempt {i + 1}: {e}")
        time.sleep(1)
