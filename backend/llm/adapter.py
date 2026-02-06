"""LLM adapter abstract interface and stub implementation for testing."""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class LLMAdapter(ABC):
    """
    Abstract base class for LLM adapters.

    All LLM adapters must implement the async complete() method.
    This allows for easy testing with stub implementations and
    swapping between different LLM providers.
    """

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        **kwargs: Any
    ) -> str:
        """
        Get a completion from the LLM.

        Args:
            prompt: The prompt to send to the LLM
            **kwargs: Additional provider-specific parameters
                (max_tokens, temperature, etc.)

        Returns:
            The LLM's response as a string

        Raises:
            LLMError: If the request fails after retries
        """
        pass


class LLMError(Exception):
    """Exception raised when LLM request fails."""

    def __init__(self, message: str, provider: str, status_code: Optional[int] = None):
        self.message = message
        self.provider = provider
        self.status_code = status_code
        super().__init__(f"[{provider}] {message}")


class StubLLMAdapter(LLMAdapter):
    """
    Stub LLM adapter for testing.

    Returns canned responses based on prompt content. Never makes
    real API calls, ensuring tests are fast and deterministic.

    Example:
        stub = StubLLMAdapter({
            "null_safety": "UNSAFE: name (calls .upper() without None check)",
            "default": "SAFE: all parameters handled"
        })
        response = await stub.complete("Check null_safety")
        # Returns: "UNSAFE: name (calls .upper() without None check)"
    """

    def __init__(
        self,
        canned_responses: Dict[str, str],
        default_response: str = "UNCLEAR",
        latency_seconds: float = 0.0
    ):
        """
        Initialize the stub adapter.

        Args:
            canned_responses: Mapping from prompt keywords to responses.
                The first key found in the prompt determines the response.
            default_response: Response to return if no keyword matches
            latency_seconds: Simulated network latency (for testing timeouts)
        """
        self.responses = canned_responses
        self.default_response = default_response
        self.latency_seconds = latency_seconds
        self.call_count = 0
        self.call_history: list[Dict[str, Any]] = []

    async def complete(
        self,
        prompt: str,
        **kwargs: Any
    ) -> str:
        """
        Return a canned response based on prompt content.

        Args:
            prompt: The prompt to check for keywords
            **kwargs: Ignored (for interface compatibility)

        Returns:
            The canned response matching a keyword in the prompt,
            or the default response if no match
        """
        self.call_count += 1

        # Record call for test assertions
        self.call_history.append({
            "prompt": prompt,
            "kwargs": kwargs,
        })

        # Simulate latency if configured
        if self.latency_seconds > 0:
            await asyncio.sleep(self.latency_seconds)

        # Find matching response based on prompt content
        for keyword, response in self.responses.items():
            if keyword in prompt:
                return response

        return self.default_response

    def reset(self) -> None:
        """Reset call counters and history."""
        self.call_count = 0
        self.call_history.clear()

    def get_last_call(self) -> Optional[Dict[str, Any]]:
        """Get the most recent call to complete()."""
        if self.call_history:
            return self.call_history[-1]
        return None

    def was_called_with(self, keyword: str) -> bool:
        """Check if complete() was called with a prompt containing the keyword."""
        return any(keyword in call["prompt"] for call in self.call_history)


class FailingLLMAdapter(LLMAdapter):
    """
    LLM adapter that always fails.

    Useful for testing error handling and graceful degradation.
    """

    def __init__(
        self,
        error_message: str = "Simulated LLM failure",
        error_type: type[Exception] = LLMError
    ):
        """
        Initialize the failing adapter.

        Args:
            error_message: Message to include in the exception
            error_type: Type of exception to raise
        """
        self.error_message = error_message
        self.error_type = error_type
        self.call_count = 0

    async def complete(
        self,
        prompt: str,
        **kwargs: Any
    ) -> str:
        """Always raise an exception."""
        self.call_count += 1
        # Try to raise with provider kwarg, fall back to message only
        try:
            raise self.error_type(self.error_message, provider="failing_stub")
        except TypeError:
            # Custom exception types may not accept the provider kwarg
            raise self.error_type(self.error_message)
