#!/usr/bin/env python3
"""
Add Numbers - Simple addition utility with type hints.
"""

from typing import Union

Number = Union[int, float]


def add_numbers(a: Number, b: Number) -> Number:
    """
    Add two numbers together.

    Args:
        a: First number (int or float)
        b: Second number (int or float)

    Returns:
        The sum of a and b

    Examples:
        >>> add_numbers(2, 3)
        5
        >>> add_numbers(1.5, 2.5)
        4.0
    """
    return a + b


# Test cases
if __name__ == "__main__":
    # Test 1: Integers
    assert add_numbers(2, 3) == 5
    print(f"✓ add_numbers(2, 3) = {add_numbers(2, 3)}")

    # Test 2: Floats
    assert add_numbers(1.5, 2.5) == 4.0
    print(f"✓ add_numbers(1.5, 2.5) = {add_numbers(1.5, 2.5)}")

    # Test 3: Mixed
    assert add_numbers(5, 3.5) == 8.5
    print(f"✓ add_numbers(5, 3.5) = {add_numbers(5, 3.5)}")

    # Test 4: Negative numbers
    assert add_numbers(-10, 5) == -5
    print(f"✓ add_numbers(-10, 5) = {add_numbers(-10, 5)}")

    # Test 5: Zero
    assert add_numbers(0, 0) == 0
    print(f"✓ add_numbers(0, 0) = {add_numbers(0, 0)}")

    print("\nAll tests passed!")
