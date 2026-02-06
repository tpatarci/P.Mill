"""Pytest configuration and fixtures for Program Mill tests."""

import pytest


@pytest.fixture
def sample_python_code() -> str:
    """Sample Python code for testing."""
    return """
def add(a: int, b: int) -> int:
    '''Add two numbers.'''
    return a + b

def divide(a: int, b: int) -> float:
    '''Divide two numbers.'''
    return a / b  # Potential division by zero

class Calculator:
    def __init__(self):
        self.result = 0

    def multiply(self, a: int, b: int) -> int:
        self.result = a * b
        return self.result
"""


@pytest.fixture
def vulnerable_code() -> str:
    """Sample code with security vulnerabilities."""
    return """
import os

def execute_command(user_input: str):
    # SQL injection vulnerability
    query = f"SELECT * FROM users WHERE name = '{user_input}'"

    # Command injection vulnerability
    os.system(f"echo {user_input}")

    return query
"""


@pytest.fixture
def complex_code() -> str:
    """Sample code with high complexity."""
    return """
def complex_function(x, y, z):
    if x > 0:
        if y > 0:
            if z > 0:
                return x + y + z
            elif z < 0:
                return x + y - z
            else:
                return x + y
        elif y < 0:
            if z > 0:
                return x - y + z
            else:
                return x - y - z
    elif x < 0:
        if y > 0:
            return -x + y
        else:
            return -x - y
    return 0
"""
