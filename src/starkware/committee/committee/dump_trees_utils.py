from typing import List, Optional

import marshmallow_dataclass
import yaml

from committee.committee import CommitteeBatchInfo
from starkware.starkware_utils.validated_dataclass import ValidatedMarshmallowDataclass
from starkware.storage.storage import Storage


@marshmallow_dataclass.dataclass(frozen=True)
class DumpInfo(ValidatedMarshmallowDataclass):
    batch_id: int
    batch_info: CommitteeBatchInfo
    # The roots of the subtrees of the order tree. This is relevant when --order_node_idx is used.
    order_subtree_roots: List[str]


async def get_storage(config_file: Optional[str] = None):
    if config_file is not None:
        config = yaml.safe_load(open(config_file))
    else:
        # Default configuration assuming port forwarding.
        config = yaml.safe_load(
            """\
STORAGE:
    class: starkware.storage.aerospike_storage_threadpool.AerospikeLayeredStorage
    config:
        hosts:
        - localhost:3000
        namespace: starkware
        aero_set: starkware
        index_bits: 28
    """
        )

    return await Storage.create_instance_from_config(config=config["STORAGE"])


def is_power_of_2(x):
    return isinstance(x, int) and x > 0 and x & (x - 1) == 0
