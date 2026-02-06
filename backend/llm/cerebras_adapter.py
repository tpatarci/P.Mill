"""Cerebras LLM adapter implementation."""

from typing import Any, Optional

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from backend.config import settings
from backend.llm.adapter import LLMAdapter, LLMError


logger = structlog.get_logger()


# Cerebras API endpoint
CEREBRAS_API_URL = "https://api.cerebras.ai/v1/chat/completions"


class CerebrasAdapter(LLMAdapter):
    """
    Cerebras LLM adapter with retry logic and graceful error handling.

    Uses httpx for async HTTP requests and tenacity for retry logic.
    Designed for fast inference with Cerebras's GPU-optimized models.
    """

    def __init__(
        self,
        config: Optional[settings.__class__] = None,
        client: Optional[httpx.AsyncClient] = None
    ):
        """
        Initialize the Cerebras adapter.

        Args:
            config: Configuration object (uses global settings if None)
            client: httpx async client (creates new one if None)
        """
        self.config = config or settings
        self.api_key = self.config.cerebras_api_key
        self.model = self.config.cerebras_model
        self.max_retries = self.config.llm_max_retries
        self.timeout = self.config.llm_timeout_seconds
        self._client = client

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the httpx client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
            )
        return self._client

    async def close(self) -> None:
        """Close the httpx client if we created it."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
        reraise=True,
    )
    async def complete(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs: Any
    ) -> str:
        """
        Get a completion from Cerebras API.

        Args:
            prompt: The prompt to send
            max_tokens: Maximum tokens in response (uses config default if None)
            temperature: Sampling temperature (uses config default if None)
            **kwargs: Additional parameters (ignored for now)

        Returns:
            The LLM's response text

        Raises:
            LLMError: If the request fails after retries
        """
        if not self.api_key:
            raise LLMError(
                "Cerebras API key not configured. Set CEREBRAS_API_KEY environment variable.",
                provider="cerebras"
            )

        max_tokens = max_tokens or self.config.llm_max_tokens
        temperature = temperature if temperature is not None else self.config.llm_temperature

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        logger.debug(
            "cerebras_request",
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            prompt_length=len(prompt),
        )

        client = await self._get_client()

        try:
            response = await client.post(CEREBRAS_API_URL, json=payload, headers=headers)

            # Handle HTTP errors
            if response.status_code >= 400:
                error_detail = response.text
                try:
                    error_json = response.json()
                    error_detail = error_json.get("error", error_detail)
                except Exception:
                    pass

                logger.error(
                    "cerebras_api_error",
                    status_code=response.status_code,
                    error=error_detail,
                )

                raise httpx.HTTPStatusError(
                    f"Cerebras API error: {error_detail}",
                    request=response.request,
                    response=response
                )

            response_json = response.json()

            # Extract the response text
            try:
                content = response_json["choices"][0]["message"]["content"]
            except (KeyError, IndexError) as e:
                raise LLMError(
                    f"Unexpected response format from Cerebras API: {e}",
                    provider="cerebras"
                )

            logger.debug(
                "cerebras_response",
                response_length=len(content),
                tokens_used=response_json.get("usage", {}).get("total_tokens"),
            )

            return content

        except httpx.TimeoutException as e:
            logger.error("cerebras_timeout", error=str(e))
            raise LLMError(
                f"Request timed out after {self.timeout}s",
                provider="cerebras"
            ) from e

        except httpx.HTTPStatusError as e:
            # Re-raise for retry logic
            raise

        except httpx.HTTPError as e:
            logger.error("cerebras_http_error", error=str(e))
            raise LLMError(
                f"HTTP error: {e}",
                provider="cerebras"
            ) from e

        except Exception as e:
            logger.error("cerebras_unexpected_error", error=str(e), type=type(e).__name__)
            raise LLMError(
                f"Unexpected error: {e}",
                provider="cerebras"
            ) from e

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
