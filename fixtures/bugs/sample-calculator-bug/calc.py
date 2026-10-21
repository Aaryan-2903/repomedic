"""
Basic calculator module containing an intentional bug for Repomedic benchmark testing.
"""

def add(a: float, b: float) -> float:
    return a + b

def subtract(a: float, b: float) -> float:
    return a - b

def multiply(a: float, b: float) -> float:
    return a * b

def divide(a: float, b: float) -> float:
    """
    Divides a by b.
    Known Bug: Uses integer floor division '//' instead of floating division '/',
    causing negative quotient truncation and incorrect float outputs.
    Also fails to validate division by zero gracefully.
    """
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a // b  # BUG: should be a / b
