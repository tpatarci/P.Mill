"""Tests for automatic language detection."""

import pytest

from backend.analysis.language_detector import LanguageDetector, detect_language


class TestLanguageDetector:
    """Test suite for LanguageDetector."""

    def test_detect_python_code(self):
        """Test detection of Python code."""
        code = """
def hello_world():
    print("Hello, World!")
    return 42
"""
        result = LanguageDetector.detect(code)
        assert result == "python"

    def test_detect_python_by_filename(self):
        """Test Python detection by filename extension."""
        code = "print('test')"
        result = LanguageDetector.detect(code, filename="script.py")
        assert result == "python"

    def test_detect_javascript_code(self):
        """Test detection of JavaScript code."""
        code = """
function helloWorld() {
    console.log("Hello, World!");
    return 42;
}
"""
        result = LanguageDetector.detect(code)
        assert result == "javascript"

    def test_detect_go_code(self):
        """Test detection of Go code."""
        code = """
package main

import "fmt"

func main() {
    fmt.Println("Hello, World!")
}
"""
        result = LanguageDetector.detect(code)
        assert result == "go"

    def test_detect_rust_code(self):
        """Test detection of Rust code."""
        code = """
fn main() {
    println!("Hello, World!");
}
"""
        result = LanguageDetector.detect(code)
        assert result == "rust"

    def test_detect_typescript_code(self):
        """Test detection of TypeScript code."""
        code = """
function greet(name: string): string {
    return `Hello, ${name}!`;
}
"""
        result = LanguageDetector.detect(code)
        assert result == "typescript"

    def test_detect_cpp_code(self):
        """Test detection of C++ code."""
        code = """
#include <iostream>

int main() {
    std::cout << "Hello, World!" << std::endl;
    return 0;
}
"""
        result = LanguageDetector.detect(code)
        assert result == "cpp"

    def test_detect_shell_script(self):
        """Test detection of shell scripts."""
        code = """
#!/bin/bash
echo "Hello, World!"
"""
        result = LanguageDetector.detect(code)
        assert result == "shell"

    def test_detect_sql_code(self):
        """Test detection of SQL code."""
        code = """
SELECT users.name, orders.total
FROM users
INNER JOIN orders ON users.id = orders.user_id
WHERE orders.total > 100;
"""
        result = LanguageDetector.detect(code)
        assert result == "sql"

    def test_detect_empty_code(self):
        """Test handling of empty code."""
        result = LanguageDetector.detect("")
        assert result == "unknown"

    def test_detect_whitespace_only(self):
        """Test handling of whitespace-only code."""
        result = LanguageDetector.detect("   \n\t  ")
        assert result == "unknown"

    def test_is_supported_python(self):
        """Test that Python is marked as supported."""
        assert LanguageDetector.is_supported("python") is True

    def test_is_supported_javascript(self):
        """Test that JavaScript is not yet supported."""
        assert LanguageDetector.is_supported("javascript") is False

    def test_is_supported_unknown(self):
        """Test that unknown language is not supported."""
        assert LanguageDetector.is_supported("unknown") is False

    def test_get_supported_languages(self):
        """Test getting list of supported languages."""
        supported = LanguageDetector.get_supported_languages()
        assert "python" in supported
        assert isinstance(supported, set)

    def test_convenience_function(self):
        """Test the convenience function wrapper."""
        code = "def test(): pass"
        result = detect_language(code)
        assert result == "python"

    def test_filename_takes_precedence(self):
        """Test that filename detection takes precedence over content."""
        # Ambiguous code that could be multiple languages
        code = "print('test')"
        result = LanguageDetector.detect(code, filename="script.py")
        assert result == "python"

    def test_python3_normalized_to_python(self):
        """Test that Python3 lexer is normalized to 'python'."""
        code = """
async def fetch_data():
    async with aiohttp.ClientSession() as session:
        return await session.get('https://api.example.com')
"""
        result = LanguageDetector.detect(code)
        assert result == "python"

    def test_complex_python_with_type_hints(self):
        """Test detection of modern Python with type hints."""
        code = """
from typing import List, Dict, Optional

def process_data(
    items: List[str],
    config: Dict[str, int],
    timeout: Optional[float] = None
) -> bool:
    '''Process data with configuration.'''
    return all(item in config for item in items)
"""
        result = LanguageDetector.detect(code)
        assert result == "python"

    def test_python_with_decorators(self):
        """Test detection of Python with decorators."""
        code = """
@app.route('/api/data')
@require_auth
async def get_data(request):
    return JSONResponse({'status': 'ok'})
"""
        result = LanguageDetector.detect(code)
        assert result == "python"

    def test_malformed_code_returns_best_guess(self):
        """Test that malformed code still attempts detection."""
        code = "def broken( syntax error"
        result = LanguageDetector.detect(code)
        # Should still attempt to detect, likely returns "python" or "unknown"
        assert result in ["python", "unknown", "text"]
