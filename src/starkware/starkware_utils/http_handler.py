import asyncio
import logging
import os
import ssl
from http import HTTPStatus
from typing import Any, Callable, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)


class BadHttpRequest(Exception):
    def __init__(self, status_code: HTTPStatus, text: str, url: str):
        self.status_code = status_code
        self.text = text
        self.url = url

    def __repr__(self):
        return (
            f"HTTP error ocurred. Status: {str(self.status_code)}."
            + f" Text: {self.text} \n URL: {self.url}"
        )


class TooManyAttempts(Exception):
    def __init__(self, attempts: int, url: str, ex: Exception):
        self.attempts = attempts
        self.url = url
        self.ex = ex

    def __repr__(self):
        return (
            f"Failed to contact {self.url} after too many attempts ({self.attempts})."
            + f"\nLast exception was {self.ex}"
        )


class HttpRetryPolicy:
    """
    A utility to do send requests with retry attempts.

    Once a request is sent via send_http_request, if it fails with an error code in
    retry_error_codes, it will try to resend the request. This will be done at most
    retry_count times, and the waiting times between the attempts will be determined by
    the timeout_gen function.
    """

    def __init__(
        self,
        success_code: HTTPStatus,
        retry_error_codes: List[HTTPStatus],
        http_request_timeout: int = 300,
        retry_count: int = 0,
        timeout_gen: Callable[[int], float] = None,
        certificates_path: Optional[str] = None,
    ):
        # Note that total number of attempts = 1 + number of retries.
        # Attempts are started at 0, and when failing at attempt n moving to n+1, the timeout in
        # between will be timeout_get(n). Default timeout between retries is 1 second.
        self.retry_count = retry_count
        if timeout_gen is None:
            self.timeout_gen: Callable[[int], float] = lambda _: 1
        else:
            self.timeout_gen = timeout_gen
        self.success_code = success_code
        self.retry_error_codes = retry_error_codes
        self.request_kwargs: Dict[str, Any] = {"timeout": http_request_timeout}
        self.ssl_context = None
        if certificates_path is not None:
            self.ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
            self.ssl_context.verify_mode = ssl.CERT_REQUIRED
            self.ssl_context.check_hostname = True

            self.ssl_context.load_cert_chain(
                os.path.join(certificates_path, "user.crt"),
                os.path.join(certificates_path, "user.key"),
            )
            # Enforce usage of server certificate authentication.
            self.ssl_context.load_verify_locations(os.path.join(certificates_path, "server.crt"))

    def retry_exception(self, ex: Exception) -> bool:
        if isinstance(ex, BadHttpRequest):
            return ex.status_code in self.retry_error_codes
        if isinstance(ex, asyncio.TimeoutError):
            return True
        return False

    async def _send_single_http_request(
        self, session: aiohttp.ClientSession, send_method: str, url: str, data=None
    ) -> str:
        async with session.request(send_method, url, data=data, **self.request_kwargs) as resp:
            text = await resp.text()
            status_code = HTTPStatus(resp.status)
            if status_code != self.success_code:
                raise BadHttpRequest(status_code=status_code, text=text, url=url)
            return text

    async def send_http_request(self, send_method: str, url: str, data=None) -> str:
        """
        Sends a request using the retry policy.
        """
        async with aiohttp.TCPConnector(ssl=self.ssl_context) as conn:
            async with aiohttp.ClientSession(connector=conn) as session:
                for attempt in range(self.retry_count):
                    # Try to send the request.
                    try:
                        return await self._send_single_http_request(
                            session=session, send_method=send_method, url=url, data=data
                        )
                    except Exception as ex:
                        if self.retry_exception(ex):
                            msg = (
                                f"Sending request attempt #{attempt} failed with "
                                + f"exception:\n{repr(ex)}"
                            )
                            logger.warning(msg)
                        else:
                            raise ex
                    timeout = self.timeout_gen(attempt)
                    await asyncio.sleep(timeout)
                try:
                    return await self._send_single_http_request(
                        session=session, send_method=send_method, url=url, data=data
                    )
                except Exception as ex:
                    raise TooManyAttempts(self.retry_count, url, ex)
