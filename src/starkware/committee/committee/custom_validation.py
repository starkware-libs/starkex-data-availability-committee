from committee.availability_gateway_client import AvailabilityGatewayClient
from starkware.starkware_utils.objects.availability import StateUpdateBase
from starkware.storage.storage import Storage


def batch_created_key(batch_id: int) -> bytes:
    return f"committee_backup_of_batch_{batch_id}".encode("ascii")


async def is_valid(
    state_update: StateUpdateBase,
    batch_id: int,
    storage: Storage,
    availability_gateway: AvailabilityGatewayClient,
    dump_batch: bool,
) -> bool:
    """
    A hook for third parties to validate the state_update before signing the new root. In addition,
    this optionally dumps the corresponding serialized batch to storage depending on the value of
    dump_batch.
    """
    return True
