from typing import Union
import math


def is_prime(n: Union[int, float]) -> bool:
    """
    Check if a number is prime.

    A prime number is a natural number greater than 1 that has no positive
    divisors other than 1 and itself.

    Args:
        n: The number to check. Must be a positive integer.

    Returns:
        True if n is prime, False otherwise.

    Examples:
        >>> is_prime(2)
        True
        >>> is_prime(17)
        True
        >>> is_prime(4)
        False
        >>> is_prime(1)
        False
    """
    # Handle non-integers, negatives, and numbers < 2
    if not isinstance(n, int) or n < 2:
        return False

    # 2 is the only even prime
    if n == 2:
        return True

    # All other even numbers are not prime
    if n % 2 == 0:
        return False

    # Check odd divisors up to sqrt(n)
    # We start at 3 and step by 2 to skip even numbers
    for i in range(3, int(math.isqrt(n)) + 1, 2):
        if n % i == 0:
            return False

    return True


# Example test cases
if __name__ == "__main__":
    # Test case 1: Small primes
    assert is_prime(2) is True, "2 is prime"
    assert is_prime(3) is True, "3 is prime"
    assert is_prime(5) is True, "5 is prime"
    assert is_prime(7) is True, "7 is prime"

    # Test case 2: Larger prime
    assert is_prime(97) is True, "97 is prime"
    assert is_prime(541) is True, "541 is prime"

    # Test case 3: Non-primes (composites)
    assert is_prime(4) is False, "4 is not prime (2*2)"
    assert is_prime(9) is False, "9 is not prime (3*3)"
    assert is_prime(15) is False, "15 is not prime (3*5)"
    assert is_prime(100) is False, "100 is not prime"

    # Test case 4: Edge cases
    assert is_prime(1) is False, "1 is not prime"
    assert is_prime(0) is False, "0 is not prime"
    assert is_prime(-5) is False, "negative numbers are not prime"
    assert is_prime(2.5) is False, "non-integers are not prime"

    print("All tests passed!")
