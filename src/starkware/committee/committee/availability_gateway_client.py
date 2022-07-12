import logging
from http import HTTPStatus
from typing import Optional, Type
from urllib.parse import urljoin

from starkware.starkware_utils.http_handler import HttpRetryPolicy
from starkware.starkware_utils.objects.availability import (
    BatchDataResponseBase,
    CommitteeSignature,
    StateUpdateBase,
)

logger = logging.getLogger(__name__)


class AvailabilityGatewayClient:
    def __init__(
        self,
        gateway_url: str,
        batch_data_response_class: Type[BatchDataResponseBase],
        http_request_timeout: int,
        certificates_path: Optional[str] = None,
    ):
        self.gateway_url = gateway_url
        self.retry_policy = HttpRetryPolicy(
            success_code=HTTPStatus.OK,
            retry_count=9,
            http_request_timeout=http_request_timeout,
            timeout_gen=(lambda i: i + 1),
            retry_error_codes=[
                HTTPStatus.BAD_GATEWAY,
                HTTPStatus.SERVICE_UNAVAILABLE,
                HTTPStatus.GATEWAY_TIMEOUT,
            ],
            certificates_path=certificates_path,
        )
        self.batch_data_response_class = batch_data_response_class

    async def _send_http_request(self, send_method: str, uri: str, data=None) -> str:
        url = urljoin(self.gateway_url, uri)
        return await self.retry_policy.send_http_request(
            send_method=send_method, url=url, data=data
        )

    async def order_tree_height(self) -> int:
        uri = "/availability_gateway/order_tree_height"
        answer = await self._send_http_request("GET", uri)
        return int(answer)

    async def _get_batch_created(self, batch_id: int) -> str:
        """
        Returns a BatchCreated dump string corresponding to a given ID.
        """
        uri = f"/availability_gateway/_get_batch_created?batch_id={batch_id}"
        return await self._send_http_request(send_method="GET", uri=uri, data=None)

    async def get_batch_data(
        self, batch_id: int, validate_rollup: Optional[bool]
    ) -> Optional[StateUpdateBase]:
        # For backwards compatability, only send validate_rollup as part of the query string if it's
        # True.
        uri = f"/availability_gateway/get_batch_data?batch_id={batch_id}"
        if validate_rollup is not None:
            uri += f"&validate_rollup={validate_rollup}"
        answer = await self._send_http_request("GET", uri)
        return self.batch_data_response_class.Schema().loads(answer).update

    async def send_signature(self, batch_id: int, sig: str, member_key: str, claim_hash: str):
        signature = CommitteeSignature(
            batch_id=batch_id, signature=sig, member_key=member_key, claim_hash=claim_hash
        )

        answer = await self._send_http_request(
            "POST", "/availability_gateway/approve_new_roots", data=signature.dumps()
        )

        if answer != "signature accepted":
            logger.error(f"unexpected response: {answer}")
            assert False, "Signature was not accepted"

        logger.debug(f"Signature for batch {batch_id} was sent successfully")

    async def is_alive(self):
        return await self._send_http_request("GET", f"/availability_gateway/is_alive")
