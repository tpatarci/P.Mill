"""Tests for null safety check prompts and response parsing."""

import pytest

from backend.llm.prompts import build_null_safety_prompt
from backend.llm.response_parser import (
    is_safe_response,
    is_unclear_response,
    is_unsafe_response,
    parse_null_safety_response,
)
from backend.models import FunctionFacts, ParameterInfo


class TestPromptBuilder:
    """Test the null safety prompt builder."""

    def test_build_prompt_basic(self):
        """Test building a basic prompt."""
        facts = FunctionFacts(
            function_name="greet",
            qualified_name="greet",
            line_start=1,
            line_end=2,
            parameters=[
                ParameterInfo(name="name", type_hint=None, has_default=False)
            ],
            has_none_checks=[],
            calls=["str.upper"],
            source_code='def greet(name): return f"Hello, {name.upper()}"',
        )

        prompt = build_null_safety_prompt(facts)

        assert "greet" in prompt
        assert "name" in prompt
        assert "str.upper" in prompt
        assert "No None checks detected" in prompt

    def test_build_prompt_with_multiple_params(self):
        """Test prompt with multiple parameters."""
        facts = FunctionFacts(
            function_name="process",
            qualified_name="process",
            line_start=1,
            line_end=3,
            parameters=[
                ParameterInfo(name="data", type_hint="list", has_default=False),
                ParameterInfo(name="items", type_hint="list", has_default=True),
            ],
            has_none_checks=["data"],
            calls=["list.add"],
            source_code="def process(data, items=None): ...",
        )

        prompt = build_null_safety_prompt(facts)

        assert "data" in prompt
        assert "items" in prompt
        assert "Has None check for: data" in prompt or "Has None checks for: data" in prompt

    def test_build_prompt_with_no_params(self):
        """Test prompt with no parameters."""
        facts = FunctionFacts(
            function_name="no_params",
            qualified_name="no_params",
            line_start=1,
            line_end=2,
            parameters=[],
            has_none_checks=[],
            calls=[],
            source_code="def no_params(): return 42",
        )

        prompt = build_null_safety_prompt(facts)

        assert "none" in prompt.lower()

    def test_build_prompt_truncates_long_call_list(self):
        """Test that long call lists are truncated."""
        # Create a function with many calls
        calls = [f"func{i}" for i in range(15)]
        facts = FunctionFacts(
            function_name="many_calls",
            qualified_name="many_calls",
            line_start=1,
            line_end=2,
            parameters=[
                ParameterInfo(name="x", type_hint=None, has_default=False)
            ],
            has_none_checks=[],
            calls=calls,
            source_code="def many_calls(x): ...",
        )

        prompt = build_null_safety_prompt(facts)

        # Should mention truncation
        assert "more" in prompt.lower()


class TestResponseParser:
    """Test the null safety response parser."""

    def test_parse_safe_response(self):
        """Test parsing SAFE response."""
        response = "SAFE: all parameters handled"
        answer_type, params = parse_null_safety_response(response)

        assert answer_type == "SAFE"
        assert params == []

    def test_parse_unsafe_single_param(self):
        """Test parsing UNSAFE response with single parameter."""
        response = "UNSAFE: name (calls .upper() without None check)"
        answer_type, params = parse_null_safety_response(response)

        assert answer_type == "UNSAFE"
        assert "name" in params

    def test_parse_unsafe_multiple_params(self):
        """Test parsing UNSAFE response with multiple parameters."""
        response = "UNSAFE: data, items, result (all used without None checks)"
        answer_type, params = parse_null_safety_response(response)

        assert answer_type == "UNSAFE"
        assert len(params) > 0
        # Should find some of the parameter names
        found = any(p in params for p in ["data", "items", "result"])
        assert found

    def test_parse_unclear_response(self):
        """Test parsing UNCLEAR response."""
        response = "I'm not sure about this function"
        answer_type, params = parse_null_safety_response(response)

        assert answer_type == "UNCLEAR"
        assert params == []

    def test_parse_garbled_response(self):
        """Test parsing garbled/unexpected response."""
        response = "The quick brown fox jumps over the lazy dog"
        answer_type, params = parse_null_safety_response(response)

        # Should default to UNCLEAR
        assert answer_type == "UNCLEAR"

    def test_parse_case_insensitive(self):
        """Test case-insensitive parsing."""
        response1 = "safe: all good"
        response2 = "Unsafe: param1"
        response3 = "UNCLEAR"

        assert is_safe_response(response1)
        assert is_unsafe_response(response2)
        assert is_unclear_response(response3)

    def test_parse_with_extra_text(self):
        """Test parsing responses with extra explanatory text."""
        response = """
        After analyzing the function, I conclude that it is
        UNSAFE: data because it calls methods on it without checking
        """

        answer_type, params = parse_null_safety_response(response)
        assert answer_type == "UNSAFE"
        assert len(params) > 0


class TestHelperFunctions:
    """Test helper functions for response classification."""

    def test_is_safe_response(self):
        """Test is_safe_response helper."""
        assert is_safe_response("SAFE: all parameters")
        assert is_safe_response("The function is SAFE")
        assert not is_safe_response("UNSAFE: name")
        assert not is_safe_response("I don't know")

    def test_is_unsafe_response(self):
        """Test is_unsafe_response helper."""
        assert is_unsafe_response("UNSAFE: name")
        assert is_unsafe_response("The code is UNSAFE: param")
        assert not is_unsafe_response("SAFE: all good")
        assert not is_unsafe_response("Maybe...")

    def test_is_unclear_response(self):
        """Test is_unclear_response helper."""
        assert is_unclear_response("UNCLEAR")
        assert is_unclear_response("I'm not sure")
        assert is_unclear_response("Can't determine")
        assert not is_unclear_response("SAFE: all good")
        assert not is_unclear_response("UNSAFE: param")


class TestEndToEndNullSafetyCheck:
    """End-to-end tests for null safety check with stub adapter."""

    @pytest.mark.asyncio
    async def test_safe_function_with_stub(self):
        """Test checking a safe function with stub adapter."""
        from backend.llm import StubLLMAdapter

        stub = StubLLMAdapter({
            "null safety": "SAFE: all parameters handled"
        })

        facts = FunctionFacts(
            function_name="safe_greet",
            qualified_name="safe_greet",
            line_start=1,
            line_end=4,
            parameters=[
                ParameterInfo(name="name", type_hint=None, has_default=False)
            ],
            has_none_checks=["name"],
            calls=["str.upper"],
            source_code='def safe_greet(name):\n    if name is None: return "Hello"\n    return name.upper()',
        )

        prompt = build_null_safety_prompt(facts)
        response = await stub.complete(prompt)

        answer_type, params = parse_null_safety_response(response)
        assert answer_type == "SAFE"
        assert params == []

    @pytest.mark.asyncio
    async def test_unsafe_function_with_stub(self):
        """Test checking an unsafe function with stub adapter."""
        from backend.llm import StubLLMAdapter

        stub = StubLLMAdapter({
            "null safety": "UNSAFE: name (calls .upper() without None check)"
        })

        facts = FunctionFacts(
            function_name="unsafe_greet",
            qualified_name="unsafe_greet",
            line_start=1,
            line_end=2,
            parameters=[
                ParameterInfo(name="name", type_hint=None, has_default=False)
            ],
            has_none_checks=[],
            calls=["str.upper"],
            source_code='def unsafe_greet(name): return name.upper()',
        )

        prompt = build_null_safety_prompt(facts)
        response = await stub.complete(prompt)

        answer_type, params = parse_null_safety_response(response)
        assert answer_type == "UNSAFE"
        assert "name" in params

    @pytest.mark.asyncio
    async def test_unclear_response_with_stub(self):
        """Test unclear response from stub adapter."""
        from backend.llm import StubLLMAdapter

        # Use default UNCLEAR response
        stub = StubLLMAdapter({})

        facts = FunctionFacts(
            function_name="complex_func",
            qualified_name="complex_func",
            line_start=1,
            line_end=5,
            parameters=[
                ParameterInfo(name="data", type_hint=None, has_default=False)
            ],
            has_none_checks=[],
            calls=[],
            source_code="def complex_func(data): ...",
        )

        prompt = build_null_safety_prompt(facts)
        response = await stub.complete(prompt)

        answer_type, params = parse_null_safety_response(response)
        assert answer_type == "UNCLEAR"


class TestResponseParserEdgeCases:
    """Test edge cases in response parsing."""

    def test_empty_response(self):
        """Test parsing empty response."""
        answer_type, params = parse_null_safety_response("")
        assert answer_type == "UNCLEAR"

    def test_response_with_only_punctuation(self):
        """Test parsing response with only punctuation."""
        answer_type, params = parse_null_safety_response("... --- !!!")
        assert answer_type == "UNCLEAR"

    def test_unsafe_with_colon_variations(self):
        """Test various UNSAFE formats."""
        formats = [
            "UNSAFE: param",
            "unsafe: param",
            "UNSAFE param",
            "It's UNSAFE: param, param2",
        ]

        for fmt in formats:
            answer_type, params = parse_null_safety_response(fmt)
            assert answer_type == "UNSAFE", f"Failed for: {fmt}"

    def test_parameter_name_filtering(self):
        """Test that common words are filtered from parameter extraction."""
        # This should not extract "the", "and", "or", etc. as parameters
        response = "UNSAFE: the data and the items are used without checks"
        answer_type, params = parse_null_safety_response(response)

        assert answer_type == "UNSAFE"
        # Should find "data" and "items" but not "the", "and"
        assert "the" not in params
        assert "and" not in params
