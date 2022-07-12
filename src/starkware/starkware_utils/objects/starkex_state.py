import dataclasses
from dataclasses import field
from typing import TYPE_CHECKING, Dict, Optional

import marshmallow_dataclass

from starkware.python.utils import to_bytes
from starkware.starkware_utils.commitment_tree.leaf_fact import LeafFact
from starkware.starkware_utils.error_handling import (
    StarkErrorCode,
    stark_assert,
    stark_assert_eq,
    stark_assert_le,
    stark_assert_ne,
)
from starkware.starkware_utils.marshmallow_dataclass_fields import IntAsHex, IntAsStr
from starkware.starkware_utils.objects.availability import (
    BatchDataResponseBase,
    StateBase,
    StateUpdateBase,
)
from starkware.starkware_utils.validated_dataclass import (
    ValidatedDataclass,
    ValidatedMarshmallowDataclass,
)
from starkware.storage.storage import HashFunctionType

# The Transaction type is needed only for annotation, and would cause cyclic dependency if imported.
if TYPE_CHECKING:
    from common.objects.transaction.raw_transaction import Transaction

MAX_AMOUNT = 2 ** 63
VaultsDict = Dict[int, "VaultState"]
OrdersDict = Dict[int, "OrderState"]


@dataclasses.dataclass(frozen=True)
class VaultUpdateData(ValidatedDataclass):
    vault_id: int
    stark_key: int = field(metadata=dict(marshmallow_field=IntAsHex(required=True)))
    token: int = field(metadata=dict(marshmallow_field=IntAsHex(required=True)))
    diff: int


@marshmallow_dataclass.dataclass
class VaultState(ValidatedMarshmallowDataclass, LeafFact, StateBase):
    """
    Vault state.

    :param stark_key: Public key of the party as registered on the StarkEx contract.
    :type stark_key: int
    :param token: Unique token ID as registered on the StarkEx contract.
    :type token: int
    :param balance: Vault balance.
    :type balance: int
    """

    stark_key: int = field(metadata=dict(marshmallow_field=IntAsHex(required=True)))
    token: int = field(metadata=dict(marshmallow_field=IntAsHex(required=True)))
    balance: int = field(metadata=dict(marshmallow_field=IntAsStr(required=True)))

    def __post_init__(self):
        super().__post_init__()

        stark_assert(
            0 <= self.balance < MAX_AMOUNT,
            code=StarkErrorCode.OUT_OF_RANGE_BALANCE,
            message="Balance is negative or out of range",
        )
        if self.balance == 0:
            self.stark_key = 0
            self.token = 0
        else:
            stark_assert_ne(
                0,
                self.stark_key,
                code=StarkErrorCode.INVALID_VAULT,
                message="A non empty vault cannot have an empty stark key",
            )
            stark_assert_ne(
                0,
                self.token,
                code=StarkErrorCode.INVALID_VAULT,
                message="A non empty vault cannot have an empty token",
            )

    @classmethod
    def empty(cls) -> "VaultState":
        return cls(stark_key=0, token=0, balance=0)

    @property
    def is_empty(self) -> bool:
        return self.stark_key == 0 and self.token == 0 and self.balance == 0

    def add(self, change: VaultUpdateData) -> "VaultState":
        if self.balance > 0:
            # Vault is non-empty - validate it.
            stark_assert_eq(
                self.stark_key,
                change.stark_key,
                code=StarkErrorCode.INVALID_VAULT,
                message="Vault does not match stark_key",
            )
            stark_assert_eq(
                self.token,
                change.token,
                code=StarkErrorCode.INVALID_VAULT,
                message="Vault does not match token",
            )

        new_balance = self.balance + change.diff
        stark_assert(
            0 <= new_balance < MAX_AMOUNT,
            code=StarkErrorCode.OUT_OF_RANGE_BALANCE,
            message=f"Vault change in vault {change.vault_id} causes balance to be negative or out "
            f"of range (adding a diff of {change.diff} to current balance of {self.balance})",
        )
        return self.__class__(stark_key=change.stark_key, token=change.token, balance=new_balance)

    def _hash(self, hash_func: HashFunctionType) -> bytes:
        hash0 = hash_func(to_bytes(self.stark_key), to_bytes(self.token))
        return hash_func(hash0, to_bytes(self.balance))


@dataclasses.dataclass(frozen=True)
class OrderUpdateData(ValidatedDataclass):
    """
    Represents a leaf update in the orders tree.
    """

    updating_tx: "Transaction"
    tree_index: int
    diff: int
    capacity: int


@marshmallow_dataclass.dataclass(frozen=True)
class OrderState(ValidatedMarshmallowDataclass, LeafFact, StateBase):
    """
    A leaf of the orders tree. May represent either the fulfillment state of an order or the minted
    state of a mintable asset.

    :param fulfilled_amount: If the leaf represents an order, this is the amount fulfilled; if the
        leaf represents a mintable asset, this is the amount minted.
    :type fulfilled_amount: int
    """

    fulfilled_amount: int = field(metadata=dict(marshmallow_field=IntAsStr(required=True)))

    def __post_init__(self):
        super().__post_init__()

        stark_assert(
            0 <= self.fulfilled_amount < MAX_AMOUNT,
            code=StarkErrorCode.OUT_OF_RANGE_AMOUNT,
            message="Fulfilled order amount / mint amount is negative or out of range",
        )

    @classmethod
    def empty(cls) -> "OrderState":
        """
        Returns a state object representing a 0 fulfilled order or an unminted mintable asset.
        """
        return cls(fulfilled_amount=0)

    @property
    def is_empty(self) -> bool:
        return self.fulfilled_amount == 0

    def add(self, change: OrderUpdateData) -> "OrderState":
        """
        Verifies the change is valid, and returns a new OrderState with the state after the change.
        """
        stark_assert(
            0 <= change.diff < MAX_AMOUNT,
            code=StarkErrorCode.OUT_OF_RANGE_AMOUNT,
            message=f"Negative or out of range order/mint amount. Update: {change}.",
        )
        stark_assert_le(
            self.fulfilled_amount + change.diff,
            change.capacity,
            code=StarkErrorCode.OUT_OF_RANGE_AMOUNT,
            message="Either attempted to mint previously minted asset, or order change exceeds "
            f"capacity (potential replay or over-subscription). Update: {change}.",
        )
        return self.__class__(self.fulfilled_amount + change.diff)

    def _hash(self, hash_func: HashFunctionType) -> bytes:
        return to_bytes(self.fulfilled_amount)


@marshmallow_dataclass.dataclass(frozen=True)
class StarkexStateUpdateBase(StateUpdateBase):
    """
    The information describing a state update.

    :param vaults: Dictionary mapping vault_id to vault state.
    :type vaults: dict
    :param orders: Dictionary mapping order_id to order state.
    :type orders: dict
    :param vault_root: expected vault root after update (hex str without prefix).
    :type vault_root: str
    :param order_root: expected order root after update (hex str without prefix).
    :type order_root: str
    :param prev_batch_id: Previous batch ID.
    :type prev_batch_id: int
    """

    vaults: Dict[int, VaultState]
    orders: Dict[int, OrderState]
    vault_root: str
    order_root: str

    @property
    def objects(self):
        return {"vault": self.vaults, "order": self.orders}

    @property
    def roots(self):
        return {"vault": self.vault_root, "order": self.order_root}


@marshmallow_dataclass.dataclass(frozen=True)
class StateUpdateVersion1(StarkexStateUpdateBase):
    pass


@marshmallow_dataclass.dataclass(frozen=True)
class StateUpdateVersion2(StarkexStateUpdateBase):
    """
    The information describing a state update with volition. Includes both validium and rollup
    updates and tree roots; validium updates/root is still referred to as 'vaults'/'vault_root' for
    backwards compatability.

    :param rollup_vaults: Dictionary mapping vault_id to vault state.
    :type rollup_vaults: dict
    :param rollup_vault_root: expected rollup vault root after update (hex str without prefix).
    :type rollup_vault_root: str
    """

    rollup_vaults: Dict[int, VaultState]
    rollup_vault_root: str

    @property
    def objects(self):
        return dict(super().objects, rollup_vault=self.rollup_vaults)

    @property
    def roots(self):
        return dict(super().roots, rollup_vault=self.rollup_vault_root)


StateUpdate = StateUpdateVersion2


@marshmallow_dataclass.dataclass(frozen=True)
class BatchDataResponseVersion1(BatchDataResponseBase):
    update: Optional[StateUpdateVersion1]


@marshmallow_dataclass.dataclass(frozen=True)
class BatchDataResponseVersion2(BatchDataResponseBase):
    update: Optional[StateUpdate]


BatchDataResponse = BatchDataResponseVersion2
