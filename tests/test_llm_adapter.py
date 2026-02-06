"""Tests for LLM adapter abstract interface and implementations."""

import asyncio

import pytest

from backend.llm import LLMAdapter, LLMError, StubLLMAdapter, FailingLLMAdapter


class TestStubLLMAdapter:
    """Test the stub LLM adapter for testing."""

    @pytest.mark.asyncio
    async def test_basic_response(self):
        """Test basic canned response functionality."""
        stub = StubLLMAdapter({
            "greet": "Hello, world!",
            "compute": "42",
        })

        response = await stub.complete("Check greet")
        assert response == "Hello, world!"

        response = await stub.complete("Check compute")
        assert response == "42"

    @pytest.mark.asyncio
    async def test_default_response(self):
        """Test default response when no keyword matches."""
        stub = StubLLMAdapter(
            {"greet": "Hello"},
            default_response="UNCLEAR"
        )

        response = await stub.complete("unknown prompt")
        assert response == "UNCLEAR"

    @pytest.mark.asyncio
    async def test_call_count(self):
        """Test that call count is tracked."""
        stub = StubLLMAdapter({"test": "response"})

        assert stub.call_count == 0

        await stub.complete("test")
        assert stub.call_count == 1

        await stub.complete("test")
        await stub.complete("test")
        assert stub.call_count == 3

    @pytest.mark.asyncio
    async def test_call_history(self):
        """Test that call history is tracked."""
        stub = StubLLMAdapter({"test": "response"})

        await stub.complete("prompt1", max_tokens=100)
        await stub.complete("prompt2", temperature=0.5)

        assert len(stub.call_history) == 2
        assert stub.call_history[0]["prompt"] == "prompt1"
        assert stub.call_history[0]["kwargs"]["max_tokens"] == 100
        assert stub.call_history[1]["prompt"] == "prompt2"
        assert stub.call_history[1]["kwargs"]["temperature"] == 0.5

    @pytest.mark.asyncio
    async def test_get_last_call(self):
        """Test get_last_call method."""
        stub = StubLLMAdapter({"test": "response"})

        assert stub.get_last_call() is None

        await stub.complete("first")
        last = stub.get_last_call()
        assert last is not None
        assert last["prompt"] == "first"

        await stub.complete("second")
        last = stub.get_last_call()
        assert last["prompt"] == "second"

    @pytest.mark.asyncio
    async def test_was_called_with(self):
        """Test was_called_with method."""
        stub = StubLLMAdapter({"test": "response"})

        assert not stub.was_called_with("null_safety")

        await stub.complete("Check null_safety for function")
        assert stub.was_called_with("null_safety")

        await stub.complete("Another prompt about complexity")
        assert stub.was_called_with("complexity")

    @pytest.mark.asyncio
    async def test_reset(self):
        """Test reset method."""
        stub = StubLLMAdapter({"test": "response"})

        await stub.complete("test1")
        await stub.complete("test2")

        assert stub.call_count == 2
        assert len(stub.call_history) == 2

        stub.reset()

        assert stub.call_count == 0
        assert len(stub.call_history) == 0

    @pytest.mark.asyncio
    async def test_simulated_latency(self):
        """Test simulated network latency."""
        stub = StubLLMAdapter(
            {"test": "response"},
            latency_seconds=0.1
        )

        import time
        start = time.time()
        await stub.complete("test")
        elapsed = time.time() - start

        assert elapsed >= 0.1
        assert elapsed < 0.2  # Should be close to 0.1

    @pytest.mark.asyncio
    async def test_kwargs_ignored(self):
        """Test that extra kwargs are accepted but ignored."""
        stub = StubLLMAdapter({"test": "response"})

        # Should not raise an error
        response = await stub.complete(
            "test",
            max_tokens=1000,
            temperature=0.5,
            unknown_param="value"
        )
        assert response == "response"


class TestFailingLLMAdapter:
    """Test the failing LLM adapter."""

    @pytest.mark.asyncio
    async def test_always_raises(self):
        """Test that adapter always raises an exception."""
        failing = FailingLLMAdapter()

        with pytest.raises(LLMError) as exc_info:
            await failing.complete("any prompt")

        assert "Simulated LLM failure" in str(exc_info.value)
        assert exc_info.value.provider == "failing_stub"

    @pytest.mark.asyncio
    async def test_custom_error_message(self):
        """Test custom error message."""
        failing = FailingLLMAdapter(error_message="Custom error!")

        with pytest.raises(LLMError) as exc_info:
            await failing.complete("test")

        assert "Custom error!" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_call_count_tracked(self):
        """Test that call count is tracked even when failing."""
        failing = FailingLLMAdapter()

        assert failing.call_count == 0

        try:
            await failing.complete("test")
        except LLMError:
            pass

        assert failing.call_count == 1

    @pytest.mark.asyncio
    async def test_custom_error_type(self):
        """Test custom error type."""
        class CustomError(Exception):
            pass

        failing = FailingLLMAdapter(error_type=CustomError)

        with pytest.raises(CustomError):
            await failing.complete("test")


class TestLLMAdapterInterface:
    """Test the LLM adapter interface requirements."""

    def test_stub_is_adapter(self):
        """Test that StubLLMAdapter is an LLMAdapter."""
        stub = StubLLMAdapter({})
        assert isinstance(stub, LLMAdapter)

    def test_failing_is_adapter(self):
        """Test that FailingLLMAdapter is an LLMAdapter."""
        failing = FailingLLMAdapter()
        assert isinstance(failing, LLMAdapter)

    @pytest.mark.asyncio
    async def test_adapter_has_complete_method(self):
        """Test that all adapters have the complete method."""
        stub = StubLLMAdapter({})
        assert hasattr(stub, "complete")
        assert callable(stub.complete)

        # Verify it's async
        import inspect
        assert inspect.iscoroutinefunction(stub.complete)


class TestNullSafetyStubResponses:
    """Test stub responses for null safety checks."""

    @pytest.mark.asyncio
    async def test_unsafe_response(self):
        """Test stub returning UNSAFE response."""
        stub = StubLLMAdapter({
            "null_safety": "UNSAFE: name (calls .upper() without None check)"
        })

        response = await stub.complete("Check null_safety")
        assert "UNSAFE" in response
        assert "name" in response

    @pytest.mark.asyncio
    async def test_safe_response(self):
        """Test stub returning SAFE response."""
        stub = StubLLMAdapter({
            "null_safety": "SAFE: all parameters handled"
        })

        response = await stub.complete("Check null_safety")
        assert response == "SAFE: all parameters handled"

    @pytest.mark.asyncio
    async def test_unclear_response(self):
        """Test stub returning UNCLEAR response."""
        stub = StubLLMAdapter({})  # No canned responses

        response = await stub.complete("Check null_safety")
        assert response == "UNCLEAR"  # Default response


class TestStubAdapterIntegration:
    """Integration tests using stub adapter."""

    @pytest.mark.asyncio
    async def test_multiple_checks_in_sequence(self):
        """Test running multiple checks sequentially."""
        stub = StubLLMAdapter({
            "null_safety": "UNSAFE: data",
            "complexity": "HIGH",
            "security": "SAFE",
        })

        results = []
        for prompt in ["Check null_safety", "Check complexity", "Check security"]:
            results.append(await stub.complete(prompt))

        assert results == [
            "UNSAFE: data",
            "HIGH",
            "SAFE",
        ]

        assert stub.call_count == 3

    @pytest.mark.asyncio
    async def test_concurrent_calls(self):
        """Test handling concurrent calls."""
        stub = StubLLMAdapter({
            "test": "response"
        })

        # Make concurrent calls
        tasks = [stub.complete(f"test{i}") for i in range(10)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        assert stub.call_count == 10
