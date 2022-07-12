import dataclasses
import os
from typing import Optional

import pytest

from committee.availability_gateway_client import AvailabilityGatewayClient
from committee.committee import Committee
from committee.committee.committee import CommitteeBatchInfo
from committee.committee_config import CommitteeConfig
from starkware.crypto.signature.fast_pedersen_hash import pedersen_hash_func
from starkware.python.test_utils import maybe_raises
from starkware.starkware_utils.commitment_tree.merkle_tree.merkle_tree import MerkleTree
from starkware.starkware_utils.objects.starkex_constants import (
    BATCH_RESPONSE_PATH_STARKEX,
    ORDER_STATE_PATH_STARKEX,
    ORDER_TREE_PATH_STARKEX,
    VAULT_STATE_PATH_STARKEX,
    VAULT_TREE_PATH_STARKEX,
)
from starkware.starkware_utils.objects.starkex_state import (
    BatchDataResponse,
    StateUpdate,
    VaultState,
)
from starkware.storage.test_utils import MockStorage

EXPECTED_ROLLUP_VAULT_ROOT = "0075364111a7a336756626d19fc8ec8df6328a5e63681c68ffaa312f6bf98c5c"
VAULT_HEIGHT = 31
ROLLUP_VAULT_HEIGHT = 31


class DummyAvailabilityGatewayClient(AvailabilityGatewayClient):
    """
    A client with no functionality (for testing).
    """

    def __init__(self):
        pass


@pytest.fixture
def validate_rollup(request) -> Optional[bool]:
    return getattr(request, "param", None)


@pytest.fixture
def validate_orders(request) -> bool:
    return getattr(request, "param", True)


@pytest.fixture
def committee(validate_rollup: Optional[bool], validate_orders: bool) -> Committee:
    committee_objects = [
        {
            "name": "vault",
            "class": VAULT_STATE_PATH_STARKEX,
            "tree_class": VAULT_TREE_PATH_STARKEX,
            "merkle_height": f"{VAULT_HEIGHT}",
        },
        {
            "name": "order",
            "class": ORDER_STATE_PATH_STARKEX,
            "tree_class": ORDER_TREE_PATH_STARKEX,
            "merkle_height": "251",
        },
    ]
    if validate_rollup is not None:
        committee_objects += [
            {
                "name": "rollup_vault",
                "class": VAULT_STATE_PATH_STARKEX,
                "tree_class": VAULT_TREE_PATH_STARKEX,
                "merkle_height": f"{ROLLUP_VAULT_HEIGHT}",
            },
        ]

    return Committee(
        config=CommitteeConfig(
            availability_gateway_endpoint="http://localhost:9414/",
            committee_objects=committee_objects,
            batch_data_response_class_path=BATCH_RESPONSE_PATH_STARKEX,
            validate_orders=validate_orders,
            validate_rollup=validate_rollup,
        ),
        private_key="0xbfb1d570ddf495e378a1a85140e72d177a92637223fa540e05aaa061179f4290",
        storage=MockStorage(),
        fact_storage=MockStorage(),
        hash_func=pedersen_hash_func,
        availability_gateway=DummyAvailabilityGatewayClient(),
    )


@pytest.fixture
def state_update() -> StateUpdate:
    """
    Returns a StateUpdate object from a JSON file.

    batch_info.json is the batch availability data for batch-0 from end_to_end_test.
    To generate this file:
    - Run end_to_end_test.
    - While the test is running, use curl to call get_batch_data for batch_id 0:
      curl localhost:9414/availability_gateway/get_batch_data?batch_id=0
    - Save the response.
    """
    batch_info_file = os.path.join(os.path.dirname(__file__), "batch_info.json")
    with open(batch_info_file) as fp:
        batch_info = fp.read()
    state_update = BatchDataResponse.loads(data=batch_info).update
    return state_update


@pytest.fixture
def expected_signature() -> str:
    """
    The expected signature on the roots in the used config file.
    """
    return (
        "0x91139636b0d42fbb362411c09459f82025fdb34ffed9ce4dc4df0131a7e3e6e1"
        "51fb0c683975d500b93d392284afd6a92bd398694002d13171241020da499a331b"
    )


@pytest.mark.asyncio
async def test_get_committee_batch_info(committee: Committee):
    """
    Tests the get_committee_batch_info and get_committee_batch_info_or_fail functions.
    """
    assert await Committee.get_committee_batch_info(storage=committee.storage, batch_id=-1) is None
    with pytest.raises(expected_exception=AssertionError):
        await Committee.get_committee_batch_info_or_fail(storage=committee.storage, batch_id=-1)
    await committee.compute_initial_batch_info()
    assert (
        await Committee.get_committee_batch_info(storage=committee.storage, batch_id=-1) is not None
    )
    assert (
        await Committee.get_committee_batch_info_or_fail(storage=committee.storage, batch_id=-1)
        is not None
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("validate_rollup", [True], indirect=True)
async def test_initialization(committee: Committee):
    """
    Test committee initialization.
    """
    assert await Committee.get_committee_batch_info(storage=committee.storage, batch_id=-1) is None
    assert await committee.storage.get_int(Committee.next_batch_id_key()) is None
    await committee.compute_initial_batch_info()
    batch_info = await Committee.get_committee_batch_info_or_fail(
        storage=committee.storage, batch_id=-1
    )
    assert batch_info.sequence_number == -1
    # Both the validium and rollup vault roots should be the same after update (same diff).
    assert (
        batch_info.merkle_roots["vault"].hex()
        == batch_info.merkle_roots["rollup_vault"].hex()
        == EXPECTED_ROLLUP_VAULT_ROOT
    )
    # The root of an empty Patricia tree is zero (32 bytes).
    assert (
        batch_info.merkle_roots["order"].hex()
        == "0000000000000000000000000000000000000000000000000000000000000000"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("validate_rollup", [True, False, None], indirect=True)
@pytest.mark.parametrize(
    "prev_rollup_root",
    [None, EXPECTED_ROLLUP_VAULT_ROOT],
    ids=["create_empty_root", "dont_change_existing_root"],
)
async def test_rollup_initialization(
    committee: Committee, state_update: StateUpdate, prev_rollup_root: Optional[str]
):
    """
    Tests rollup initialization scenarios:
    1. If the previous CommitteeBatchInfo doesn't contain a rollup root, it should be created.
    2. If the previous CommitteeBatchInfo does contain a rollup root, it should not be overwritten.
    """
    # Delete the rollup update from the state update, so the rollup root doesn't change.
    state_update = dataclasses.replace(state_update, rollup_vaults={})

    # Set the expected new rollup root depending on prev_rollup_root (if it's None, the tree should
    # be initialized empty).
    expected_root = EXPECTED_ROLLUP_VAULT_ROOT
    if prev_rollup_root is None:
        expected_root = MerkleTree.empty_tree_roots(
            max_height=ROLLUP_VAULT_HEIGHT,
            leaf_fact=VaultState.empty(),
            hash_func=pedersen_hash_func,
        )[-1].hex()
    state_update = dataclasses.replace(state_update, rollup_vault_root=expected_root)

    # Run one validation iteration, make sure the final rollup root exists and is as expected.
    await committee.compute_initial_batch_info()
    await committee.validate_data_availability(
        batch_id=0,
        state_update=state_update,
        validate_orders=committee.validate_orders,
        validate_rollup=committee.validate_rollup,
    )
    batch_info_data = await committee.storage.get_value(key=committee.committee_batch_info_key(0))
    batch_info = CommitteeBatchInfo.deserialize(data=batch_info_data)
    assert batch_info.sequence_number == 0
    assert batch_info.merkle_roots["rollup_vault"].hex() == expected_root


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "validate_orders",
    [True, False],
    ids=["validate_orders", "do_not_validate_orders"],
    indirect=True,
)
@pytest.mark.parametrize(
    "validate_rollup",
    [True, False, None],
    ids=["validate_rollup", "do_not_validate_rollup", "no_validate_rollup_flag"],
    indirect=True,
)
@pytest.mark.parametrize(
    "valid_vault_root", [True, False], ids=["valid_vault_root", "invalid_vault_root"]
)
@pytest.mark.parametrize(
    "valid_rollup_root", [True, False], ids=["valid_rollup_root", "invalid_rollup_root"]
)
@pytest.mark.parametrize(
    "valid_order_root", [True, False], ids=["valid_order_root", "invalid_order_root"]
)
async def test_validate_data_availability(
    committee: Committee,
    state_update: StateUpdate,
    expected_signature: str,
    validate_orders: bool,
    validate_rollup: Optional[bool],
    valid_vault_root: bool,
    valid_rollup_root: bool,
    valid_order_root: bool,
):
    """
    Test committee validate_data_availability().
    """
    await committee.compute_initial_batch_info()

    # Corrupt vault data if needed.
    if not valid_vault_root:
        state_update.objects["vault"].popitem()

    # Corrupt rollup vault data if needed.
    if valid_rollup_root is False:
        state_update.objects["rollup_vault"].popitem()

    # Corrupt order data if needed.
    if not valid_order_root:
        state_update.objects["order"].popitem()

    # The committee should fail if at least one of the validated objects is invalid.
    # Validium vaults ("vault_root") are always validated.
    expect_error = (
        (not valid_vault_root)
        or (validate_orders and not valid_order_root)
        or (validate_rollup and not valid_rollup_root)
    )
    error_message = "root mismatch" if expect_error else None
    with maybe_raises(expected_exception=AssertionError, error_message=error_message):
        signature, _ = await committee.validate_data_availability(
            batch_id=0,
            state_update=state_update,
            validate_orders=validate_orders,
            validate_rollup=validate_rollup,
        )
    if not expect_error:
        assert signature == expected_signature
