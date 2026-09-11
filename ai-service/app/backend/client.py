"""Asynchronous HTTP client for transmitting validated detections to FastAPI Backend."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
from typing import Any

import httpx

from app.backend.schemas import BackendDetectionPayload
from app.core.config import settings

logger = logging.getLogger(__name__)


class BackendClient:
    """
    Asynchronous HTTP client responsible only for communicating with the FastAPI backend.

    Guarantees:
      - POSTs to /api/v1/detections using httpx.AsyncClient
      - Configurable timeout
      - Bounded retries with exponential backoff delay for 5xx and network errors
      - Distinguishes non-retryable 4xx errors from retryable 5xx/network errors
      - Never raises exceptions or crashes the stream processing pipeline
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_prefix: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        retry_delay_seconds: float | None = None,
        retry_backoff_base: float | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        raw_base = base_url or settings.BACKEND_BASE_URL
        self.base_url = str(raw_base).rstrip("/")
        raw_prefix = api_prefix or settings.BACKEND_API_PREFIX
        self.api_prefix = str(raw_prefix).rstrip("/")
        self.timeout_seconds = float(
            timeout_seconds
            if timeout_seconds is not None
            else settings.BACKEND_REQUEST_TIMEOUT_SECONDS
        )
        self.max_retries = int(
            max_retries
            if max_retries is not None
            else settings.BACKEND_MAX_RETRIES
        )
        self.retry_delay_seconds = float(
            retry_delay_seconds
            if retry_delay_seconds is not None
            else settings.BACKEND_RETRY_DELAY_SECONDS
        )
        self.retry_backoff_base = float(
            retry_backoff_base
            if retry_backoff_base is not None
            else getattr(settings, "BACKEND_RETRY_BACKOFF_BASE", 0.5)
        )
        self._endpoint = f"{self.base_url}{self.api_prefix}/detections"
        self._client = http_client
        self._owns_client = http_client is None

        # Telemetry metrics
        self.backend_requests: int = 0
        self.backend_successes: int = 0
        self.backend_failures: int = 0
        self.retry_count: int = 0
        self.last_backend_error: str | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout_seconds)
        return self._client

    async def post_detection(
        self,
        payload: BackendDetectionPayload | dict[str, Any],
    ) -> tuple[bool, int, str | None]:
        """
        Transmit a validated detection payload to the FastAPI backend.

        Args:
            payload: BackendDetectionPayload dataclass or serialized dictionary.

        Returns:
            Tuple of (success: bool, status_code: int, response_or_error: str | None).
            Never raises exceptions to the caller.
        """
        data = payload.to_dict() if hasattr(payload, "to_dict") else dict(payload)
        client = await self._get_client()

        last_status = 0
        last_error: str | None = None

        # 1 initial attempt + up to max_retries retries
        total_attempts = max(1, self.max_retries + 1)

        for attempt in range(1, total_attempts + 1):
            self.backend_requests += 1
            try:
                response = await client.post(self._endpoint, json=data)
                last_status = response.status_code

                # Success: 200 OK or 201 Created (or idempotent deduplication return)
                if 200 <= last_status < 300:
                    self.backend_successes += 1
                    logger.info(
                        "Successfully ingested detection type=%s [status=%d] -> %s",
                        data.get("detection_type"),
                        last_status,
                        self._endpoint,
                    )
                    return True, last_status, response.text

                # 4xx Client Errors: Do NOT retry (bad schema, unknown bus/camera, validation error)
                if 400 <= last_status < 500:
                    self.backend_failures += 1
                    last_error = f"HTTP {last_status}: {response.text[:200]}"
                    self.last_backend_error = last_error
                    logger.warning(
                        "Backend rejected detection with HTTP %d (non-retryable client error): %s",
                        last_status,
                        response.text[:200],
                    )
                    return False, last_status, response.text

                # 5xx Server Errors: Retryable
                last_error = f"HTTP {last_status}: {response.text[:200]}"
                logger.warning(
                    "Backend server error (HTTP %d) on attempt %d/%d: %s",
                    last_status,
                    attempt,
                    total_attempts,
                    last_error,
                )

            except (httpx.RequestError, httpx.TimeoutException) as net_err:
                last_status = 0
                last_error = f"{net_err.__class__.__name__}: {str(net_err)}"
                logger.warning(
                    "Backend network failure on attempt %d/%d: %s",
                    attempt,
                    total_attempts,
                    last_error,
                )
            except Exception as unexp_err:
                last_status = 0
                last_error = f"UnexpectedException: {str(unexp_err)}"
                logger.error(
                    "Unexpected error during backend request on attempt %d/%d: %s",
                    attempt,
                    total_attempts,
                    unexp_err,
                )

            # Check if retries remain
            if attempt < total_attempts:
                self.retry_count += 1
                delay = self.retry_delay_seconds * (2 ** (attempt - 1))
                logger.debug("Waiting %.2f seconds before retry attempt %d...", delay, attempt + 1)
                await asyncio.sleep(delay)

        # All retries exhausted
        self.backend_failures += 1
        self.last_backend_error = last_error
        logger.error(
            "Failed to ingest detection after %d attempts to %s. Last error: %s",
            total_attempts,
            self._endpoint,
            last_error,
        )
        return False, last_status, last_error

    async def close(self) -> None:
        """Release underlying HTTP client resources."""
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    def get_metrics(self) -> dict[str, Any]:
        """Expose client telemetry statistics."""
        return {
            "backend_requests": self.backend_requests,
            "backend_successes": self.backend_successes,
            "backend_failures": self.backend_failures,
            "retry_count": self.retry_count,
            "last_backend_error": self.last_backend_error,
        }
