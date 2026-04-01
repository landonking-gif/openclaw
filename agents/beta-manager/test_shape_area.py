"""
Comprehensive pytest tests for shape_area.calculate_area function
"""

import math
import pytest
from shape_area import calculate_area


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def valid_dimensions():
    """Reusable test data for valid shape dimensions."""
    return {
        'circle': {'radius': 5, 'expected': 25 * math.pi},
        'rectangle': {'width': 4, 'height': 6, 'expected': 24},
        'triangle': {'base': 10, 'height': 5, 'expected': 25},
        'square': {'side': 7, 'expected': 49},
    }


@pytest.fixture
def floating_point_cases():
    """Test cases requiring floating point precision handling."""
    return {
        'circle_pi': {'shape': 'circle', 'args': (1,), 'expected': math.pi},
        'circle_precision': {'shape': 'circle', 'args': (2.5,), 'expected': 19.63495408},
        'triangle_half': {'shape': 'triangle', 'args': (2, 3), 'expected': 3.0},
        'rectangle_float': {'shape': 'rectangle', 'args': (2.5, 4.2), 'expected': 10.5},
    }


@pytest.fixture
def zero_cases():
    """Test cases with zero dimensions."""
    return {
        'circle_zero': {'shape': 'circle', 'args': (0,), 'expected': 0},
        'rectangle_zero_width': {'shape': 'rectangle', 'args': (0, 5), 'expected': 0},
        'rectangle_zero_height': {'shape': 'rectangle', 'args': (4, 0), 'expected': 0},
        'rectangle_zero_both': {'shape': 'rectangle', 'args': (0, 0), 'expected': 0},
        'triangle_zero_base': {'shape': 'triangle', 'args': (0, 5), 'expected': 0},
        'triangle_zero_height': {'shape': 'triangle', 'args': (4, 0), 'expected': 0},
        'square_zero': {'shape': 'square', 'args': (0,), 'expected': 0},
    }


# =============================================================================
# Parametrized Tests for Valid Calculations
# =============================================================================

@pytest.mark.parametrize(
    "shape, args, expected",
    [
        # Circle
        ('circle', (1,), math.pi),
        ('circle', (2,), 4 * math.pi),
        ('circle', (5,), 25 * math.pi),
        ('circle', (10,), 100 * math.pi),

        # Rectangle
        ('rectangle', (1, 1), 1),
        ('rectangle', (2, 3), 6),
        ('rectangle', (4, 5), 20),
        ('rectangle', (10, 10), 100),

        # Triangle
        ('triangle', (2, 2), 2),
        ('triangle', (4, 3), 6),
        ('triangle', (10, 5), 25),
        ('triangle', (6, 8), 24),

        # Square
        ('square', (1,), 1),
        ('square', (2,), 4),
        ('square', (5,), 25),
        ('square', (10,), 100),
    ],
)
def test_valid_calculations(shape, args, expected):
    """Test valid area calculations with known expected values."""
    result = calculate_area(shape, *args)
    assert result == expected


@pytest.mark.parametrize(
    "shape, args, expected",
    [
        ('circle', (2.5,), 19.634954084936208),
        ('circle', (1.41421356,), 6.283185305858225),
        ('rectangle', (2.5, 4.2), 10.5),
        ('rectangle', (3.14159, 2.0), 6.28318),
        ('triangle', (3.3, 6.6), 10.89),
        ('triangle', (1.5, 4.0), 3.0),
        ('square', (2.5,), 6.25),
        ('square', (3.14159,), 9.8695877281),
    ],
)
def test_floating_point_precision(shape, args, expected):
    """Test floating point precision using pytest.approx."""
    result = calculate_area(shape, *args)
    assert result == pytest.approx(expected)


def test_fixture_valid_dimensions(valid_dimensions):
    """Test using the valid_dimensions fixture."""
    data = valid_dimensions
    assert calculate_area('circle', data['circle']['radius']) == pytest.approx(data['circle']['expected'])
    assert calculate_area('rectangle', data['rectangle']['width'], data['rectangle']['height']) == data['rectangle']['expected']
    assert calculate_area('triangle', data['triangle']['base'], data['triangle']['height']) == data['triangle']['expected']
    assert calculate_area('square', data['square']['side']) == data['square']['expected']


# =============================================================================
# Edge Cases: Zero Values
# =============================================================================

@pytest.mark.parametrize(
    "shape, args",
    [
        ('circle', (0,)),
        ('rectangle', (0, 5)),
        ('rectangle', (4, 0)),
        ('rectangle', (0, 0)),
        ('triangle', (0, 5)),
        ('triangle', (4, 0)),
        ('triangle', (0, 0)),
        ('square', (0,)),
    ],
)
def test_zero_values_return_zero(shape, args):
    """Test that zero dimensions return area of zero."""
    assert calculate_area(shape, *args) == 0


def test_zero_values_using_fixture(zero_cases):
    """Test zero values using the zero_cases fixture."""
    for case_name, case_data in zero_cases.items():
        result = calculate_area(case_data['shape'], *case_data['args'])
        assert result == case_data['expected'], f"Failed for case: {case_name}"


# =============================================================================
# Edge Cases: Negative Inputs
# =============================================================================

@pytest.mark.parametrize(
    "shape, args",
    [
        ('circle', (-1,)),
        ('circle', (-5.5,)),
        ('rectangle', (-1, 5)),
        ('rectangle', (4, -1)),
        ('rectangle', (-2, -3)),
        ('triangle', (-1, 5)),
        ('triangle', (4, -1)),
        ('triangle', (-2, -3)),
        ('square', (-1,)),
        ('square', (-2.5,)),
    ],
)
def test_negative_inputs_raise_valueerror(shape, args):
    """Test that negative dimensions raise ValueError."""
    with pytest.raises(ValueError):
        calculate_area(shape, *args)


# =============================================================================
# Invalid Shape Types (should raise ValueError or TypeError)
# =============================================================================

@pytest.mark.parametrize(
    "invalid_shape",
    [
        'oval',
        'pentagon',
        'hexagon',
        'dodecahedron',
        'cube',
        'cone',
        '  ',
        '',
    ],
)
def test_invalid_shape_raises_valueerror(invalid_shape):
    """Test that invalid shape names raise ValueError."""
    with pytest.raises(ValueError) as exc_info:
        calculate_area(invalid_shape, 1)
    assert "Invalid shape" in str(exc_info.value)


@pytest.mark.parametrize(
    "non_string_shape",
    [
        123,
        45.67,
        ['circle'],
        {'shape': 'circle'},
        None,
        object(),
    ],
)
def test_non_string_shape_raises_typeerror(non_string_shape):
    """Test that non-string shape values raise TypeError."""
    with pytest.raises(TypeError) as exc_info:
        calculate_area(non_string_shape, 1)
    assert "must be a string" in str(exc_info.value)


# =============================================================================
# Wrong Number of Arguments
# =============================================================================

@pytest.mark.parametrize(
    "shape, args, expected_count",
    [
        # Circles require 1 arg
        ('circle', (), 1),
        ('circle', (1, 2), 1),
        ('circle', (1, 2, 3), 1),

        # Rectangles require 2 args
        ('rectangle', (), 2),
        ('rectangle', (5,), 2),
        ('rectangle', (1, 2, 3), 2),
        ('rectangle', (1, 2, 3, 4), 2),

        # Triangles require 2 args
        ('triangle', (), 2),
        ('triangle', (5,), 2),
        ('triangle', (1, 2, 3), 2),
        ('triangle', (1, 2, 3, 4), 2),

        # Squares require 1 arg