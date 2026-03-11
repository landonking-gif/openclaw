"""
Shape Area Calculator
Supports: circle, rectangle, triangle, and square
"""

import math
from typing import Union

Number = Union[int, float]


def calculate_area(shape: str, *args: Number) -> float:
    """
    Calculate the area of a shape.

    Args:
        shape: Type of shape ('circle', 'rectangle', 'triangle', 'square')
        *args: Dimensions required for the shape

    Returns:
        float: The calculated area

    Raises:
        ValueError: If shape type is invalid or dimensions are negative
        TypeError: If shape is not a string or if dimension count/type is wrong

    Shape-specific args:
        - circle: radius (1 arg)
        - rectangle: width, height (2 args)
        - triangle: base, height (2 args)
        - square: side (1 arg)
    """
    # Validate shape type
    if not isinstance(shape, str):
        raise TypeError(f"Shape must be a string, got {type(shape).__name__}")

    shape = shape.lower().strip()
    valid_shapes = {'circle', 'rectangle', 'triangle', 'square'}

    if shape not in valid_shapes:
        raise ValueError(f"Invalid shape '{shape}'. Valid shapes: {', '.join(sorted(valid_shapes))}")

    # Validate all args are numeric
    for i, arg in enumerate(args):
        if not isinstance(arg, (int, float)):
            raise TypeError(f"Argument {i} must be numeric, got {type(arg).__name__}")

    # Calculate based on shape
    if shape == 'circle':
        if len(args) != 1:
            raise ValueError(f"Circle requires 1 argument (radius), got {len(args)}")
        radius = args[0]
        if radius < 0:
            raise ValueError(f"Radius cannot be negative, got {radius}")
        return math.pi * radius ** 2

    elif shape == 'rectangle':
        if len(args) != 2:
            raise ValueError(f"Rectangle requires 2 arguments (width, height), got {len(args)}")
        width, height = args
        if width < 0:
            raise ValueError(f"Width cannot be negative, got {width}")
        if height < 0:
            raise ValueError(f"Height cannot be negative, got {height}")
        return width * height

    elif shape == 'triangle':
        if len(args) != 2:
            raise ValueError(f"Triangle requires 2 arguments (base, height), got {len(args)}")
        base, height = args
        if base < 0:
            raise ValueError(f"Base cannot be negative, got {base}")
        if height < 0:
            raise ValueError(f"Height cannot be negative, got {height}")
        return 0.5 * base * height

    elif shape == 'square':
        if len(args) != 1:
            raise ValueError(f"Square requires 1 argument (side), got {len(args)}")
        side = args[0]
        if side < 0:
            raise ValueError(f"Side cannot be negative, got {side}")
        return side ** 2

    # This should never be reached due to earlier validation
    raise ValueError(f"Unexpected error for shape '{shape}'")
