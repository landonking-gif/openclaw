"""
Timer Decorator - Function Execution Time Logger

A production-ready Python decorator for measuring and logging function
execution time. Supports both @timer and @timer() syntax.
"""

import time
import functools
from typing import Callable, Optional, Any, overload, Union
from datetime import timedelta


def timer(
    func: Optional[Callable] = None,
    *,
    log_prefix: str = "[TIMER]",
    precision: int = 4,
    enabled: bool = True
) -> Callable:
    """
    A decorator that logs function execution time.

    Can be used in two ways:
        @timer          # Simple usage
        def my_func(): ...

        @timer(log_prefix="[CUSTOM]")  # With arguments
        def my_func(): ...

    Args:
        func: The function to decorate (when used as @timer without parentheses).
        log_prefix: Prefix string for log messages. Default: "[TIMER]".
        precision: Number of decimal places for time display. Default: 4.
        enabled: If False, timing is disabled (useful for debugging). Default: True.

    Returns:
        The decorated function with timing instrumentation.
    """
    def decorator(wrapped_func: Callable) -> Callable:
        """The actual decorator that wraps the function."""
        @functools.wraps(wrapped_func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not enabled:
                return wrapped_func(*args, **kwargs)

            # Record start time
            start_time = time.perf_counter()

            try:
                # Execute the wrapped function
                result = wrapped_func(*args, **kwargs)
                return result
            finally:
                # Calculate and log execution time
                end_time = time.perf_counter()
                elapsed = end_time - start_time

                # Format the message
                func_name = wrapped_func.__qualname__
                time_str = f"{elapsed:.{precision}f}"

                print(
                    f"{log_prefix} {func_name} executed in {time_str} seconds "
                    f"({timedelta(seconds=elapsed)})"
                )

        # Attach metadata for inspection
        wrapper._timer_config = {  # type: ignore
            "log_prefix": log_prefix,
            "precision": precision,
            "enabled": enabled
        }

        return wrapper

    # Handle both @timer and @timer() usage
    if func is None:
        # Called with parentheses: @timer() or @timer(log_prefix="...")
        return decorator
    else:
        # Called without parentheses: @timer
        return decorator(func)


class TimerContextManager:
    """
    A context manager for timing blocks of code.

    Alternative to the decorator for timing arbitrary code blocks.

    Example:
        with TimerContextManager("block_name"):
            # Code to time
            pass
    """

    def __init__(self, name: str = "code_block", log_prefix: str = "[TIMER]"):
        self.name = name
        self.log_prefix = log_prefix
        self.start_time: Optional[float] = None
        self.elapsed: Optional[float] = None

    def __enter__(self) -> 'TimerContextManager':
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args: Any) -> None:
        self.elapsed = time.perf_counter() - self.start_time  # type: ignore
        print(
            f"{self.log_prefix} {self.name} executed in "
            f"{self.elapsed:.4f} seconds"
        )

    def __float__(self) -> float:
        """Allow casting to float to get elapsed time."""
        return self.elapsed if self.elapsed is not None else 0.0


def get_timer_stats(func: Callable) -> Optional[dict]:
    """
    Retrieve timer configuration from a decorated function.

    Args:
        func: A function decorated with @timer.

    Returns:
        Dictionary with timer configuration, or None if not decorated.
    """
    return getattr(func, '_timer_config', None)


# ============================================================================
# Example Usage and Testing
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("Timer Decorator - Example Usage")
    print("=" * 70)

    # Example 1: Simple usage without parentheses
    @timer
    def slow_add(a: int, b: int) -> int:
        """Add two numbers with a small delay."""
        time.sleep(0.1)
        return a + b

    # Example 2: With configuration
    @timer(log_prefix="[PROFILE]", precision=6)
    def process_data(items: list) -> list:
        """Process a list of items with delay."""
        time.sleep(0.05)
        return [x * 2 for x in items]

    # Example 3: Disabled timer (for debugging)
    @timer(enabled=False)
    def quick_function() -> str:
        """This won't log timing."""
        return "done"

    # Example 4: Class method
    class DataProcessor:
        @timer(log_prefix="[METHOD]")
        def compute(self, n: int) -> int:
            """Compute something expensive."""
            time.sleep(0.02)
            return n ** 2

    # Run examples
    print("\n1. Simple usage (@timer):")
    result = slow_add(5, 3)
    print(f"   Result: {result}")

    print("\n2. With custom configuration (@timer(log_prefix=...)):")
    result = process_data([1, 2, 3, 4, 5])
    print(f"   Result: {result}")

    print("\n3. Disabled timer (no output expected):")
    result = quick_function()
    print(f"   Result: {result}")

    print("\n4. Class method:")
    processor = DataProcessor()
    result = processor.compute(10)
    print(f"   Result: {result}")

    # Example 5: Context manager
    print("\n5. Context manager for code blocks:")
    with TimerContextManager("data_processing"):
        time.sleep(0.1)
        print("   Processing inside timed block...")

    # Example 6: Inspect timer configuration
    print("\n6. Inspecting decorated function metadata:")
    print(f"   Function name: {slow_add.__name__}")
    print(f"   Docstring: {slow_add.__doc__}")
    print(f"   Timer config: {get_timer_stats(slow_add)}")

    # Example 7: Multiple calls to show timing variance
    print("\n7. Multiple calls (showing timing variance):")
    @timer(precision=6)
    def variable_delay():
        """Function with random-ish delay."""
        import random
        time.sleep(random.uniform(0.01, 0.05))

    for i in range(3):
        variable_delay()

    print("\n" + "=" * 70)
    print("All examples completed!")
    print("=" * 70)
