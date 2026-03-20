#!/usr/bin/env python3
"""
Fibonacci with Memoization

Efficient Fibonacci calculation using functools.lru_cache for automatic memoization.
Also includes a manual memoization implementation for comparison.
"""

from functools import lru_cache
from typing import Dict


@lru_cache(maxsize=None)
def fibonacci(n: int) -> int:
    """
    Calculate the nth Fibonacci number using automatic memoization.
    
    Uses functools.lru_cache to cache results of previous calculations,
    avoiding redundant computations and improving performance significantly.
    
    Args:
        n: The position in the Fibonacci sequence (0-indexed).
           Must be a non-negative integer.
    
    Returns:
        The nth Fibonacci number.
    
    Raises:
        ValueError: If n is negative.
    
    Time Complexity:
        - Without memoization: O(2^n) exponential
        - With memoization: O(n) linear (each value computed once)
    
    Space Complexity:
        - O(n) for the cache (stores all computed values)
        - O(n) for recursion stack depth
    
    Examples:
        >>> fibonacci(0)
        0
        >>> fibonacci(1)
        1
        >>> fibonacci(10)
        55
        >>> fibonacci(50)
        12586269025
    
    Note:
        The LRU cache persists across multiple calls, so subsequent
        calls with the same n are O(1) lookups.
    """
    if n < 0:
        raise ValueError(f"n must be non-negative, got {n}")
    if n < 2:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)


def fibonacci_manual(n: int, _cache: Dict[int, int] = None) -> int:
    """
    Calculate the nth Fibonacci number using manual memoization.
    
    This implementation uses an explicit dictionary for caching,
    useful when you need more control over the cache or decorator
    usage isn't appropriate.
    
    Args:
        n: The position in the Fibonacci sequence (0-indexed).
        _cache: Internal cache dictionary (users should not provide this).
    
    Returns:
        The nth Fibonacci number.
    
    Raises:
        ValueError: If n is negative.
    
    Time Complexity: O(n) - each value computed once
    Space Complexity: O(n) - cache storage
    
    Examples:
        >>> fibonacci_manual(0)
        0
        >>> fibonacci_manual(10)
        55
    """
    if _cache is None:
        _cache = {0: 0, 1: 1}
    
    if n < 0:
        raise ValueError(f"n must be non-negative, got {n}")
    
    if n not in _cache:
        _cache[n] = fibonacci_manual(n - 1, _cache) + fibonacci_manual(n - 2, _cache)
    
    return _cache[n]


def clear_fibonacci_cache() -> None:
    """Clear the LRU cache for the fibonacci function."""
    fibonacci.cache_clear()


def get_cache_info() -> Dict:
    """Get cache statistics from the fibonacci function."""
    return {
        "cache_hits": fibonacci.cache_info().hits,
        "cache_misses": fibonacci.cache_info().misses,
        "max_size": fibonacci.cache_info().maxsize,
        "current_size": fibonacci.cache_info().currsize
    }


# ============================================================================
# Example Usage and Testing
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Fibonacci with Memoization - Examples")
    print("=" * 60)
    
    # Basic examples
    print("\n1. Basic Fibonacci calculations:")
    for i in range(11):
        print(f"   fibonacci({i}) = {fibonacci(i)}")
    
    # Demonstrate cache effectiveness
    print("\n2. Cache statistics after computing fibonacci(0) to fibonacci(10):")
    info = get_cache_info()
    print(f"   Cache hits: {info['cache_hits']}")
    print(f"   Cache misses: {info['cache_misses']}")
    print(f"   Current cache size: {info['current_size']}")
    
    # Large value demonstration
    print("\n3. Computing large Fibonacci numbers:")
    print(f"   fibonacci(50) = {fibonacci(50)}")
    print(f"   fibonacci(100) = {fibonacci(100)}")
    
    # Manual memoization
    print("\n4. Manual memoization version:")
    print(f"   fibonacci_manual(20) = {fibonacci_manual(20)}")
    
    # Error handling
    print("\n5. Error handling:")
    try:
        result = fibonacci(-1)
    except ValueError as e:
        print(f"   Caught expected error: {e}")
    
    # Cache clear demonstration
    print("\n6. Clear cache:")
    clear_fibonacci_cache()
    print(f"   Cache cleared. Current size: {get_cache_info()['current_size']}")
    
    print("\n" + "=" * 60)
    print("All examples completed successfully!")
    print("=" * 60)
