import dataclasses
from dataclasses import asdict, field
from typing import Dict, Mapping, Optional

import marshmallow
import marshmallow_dataclass
from frozendict import frozendict

from services.perpetual.public.definitions import constants, fields
from services.perpetual.public.definitions.error_codes import StarkPerpetualErrorCode
from starkware.crypto.signature.signature import FIELD_PRIME
from starkware.python.fixed_point import FixedPoint
from starkware.python.utils import to_bytes
from starkware.starkware_utils.commitment_tree.leaf_fact import LeafFact
from starkware.starkware_utils.error_handling import stark_assert
from starkware.starkware_utils.marshmallow_dataclass_fields import FrozenDictField
from starkware.starkware_utils.objects.availability import (
    BatchDataResponseBase,
    StateBase,
    StateUpdateBase,
)
from starkware.starkware_utils.validated_dataclass import ValidatedMarshmallowDataclass
from starkware.storage.storage import HASH_BYTES, HashFunctionType


@marshmallow_dataclass.dataclass(frozen=True)
class PositionAsset(ValidatedMarshmallowDataclass):
    """
    Position asset.

    :param balance: Quantized asset amount in the position.
    :type balance: int
    :param cached_funding_index: A snapshot of the funding index at the last time that funding was
       applied on the position.
    :type cached_funding_index: int
    """

    balance: int = field(metadata=fields.balance_field_metadata)
    cached_funding_index: int = field(metadata=fields.funding_index_field_metadata)

    def calculate_message(self, asset_id: int) -> bytes:
        balance_range_size = constants.BALANCE_UPPER_BOUND - constants.BALANCE_LOWER_BOUND

        funding_index_range_size = (
            constants.FUNDING_INDEX_UPPER_BOUND - constants.FUNDING_INDEX_LOWER_BOUND
        )
        assert (
            constants.ASSET_ID_UPPER_BOUND * funding_index_range_size * balance_range_size
            < FIELD_PRIME
        )

        asset_packed = asset_id * funding_index_range_size + (
            self.cached_funding_index - constants.FUNDING_INDEX_LOWER_BOUND
        )
        shifted_balance = self.balance - constants.BALANCE_LOWER_BOUND

        asset_packed = asset_packed * balance_range_size + shifted_balance
        return to_bytes(asset_packed)


@marshmallow_dataclass.dataclass(frozen=True)
class FundingIndicesState(ValidatedMarshmallowDataclass):
    """
    **FundingIndicesState**

    Represents a collection of timestamped global funding indices for all assets.

    :param indices: Map of synthetic asset to its global funding index.
    :type indices: Mapping[int, int]
    :param timestamp: The timestamp for which the funding indices are valid for.
    :type timestamp: int
    """

    indices: Mapping[int, int] = field(metadata=fields.funding_indices_field_metadata)
    timestamp: int = field(metadata=fields.timestamp_field_metadata)

    @classmethod
    def empty(cls) -> "FundingIndicesState":
        return cls(indices={}, timestamp=0)

    def __eq__(self, other) -> bool:
        return isinstance(other, FundingIndicesState) and asdict(self) == asdict(other)


@marshmallow_dataclass.dataclass(frozen=True)
class AssetPrice(ValidatedMarshmallowDataclass):
    """
    **AssetPrices**

    Represents a single synthetic asset and its price value.

    :param price: The price value of the asset.
    :type price: int
    """

    price: int = field(metadata=fields.price_field_metadata)


AssetPricesMapping = Mapping[int, AssetPrice]


@marshmallow_dataclass.dataclass(frozen=True)
class PositionState(ValidatedMarshmallowDataclass, LeafFact, StateBase):
    """
    Position state.

    :param public_key: Public key of the position's owner.
    :type public_key: int
    :param collateral_balance: The amount of the collateral asset in the position.
    :type collateral_balance: int
    :param assets: Information on each synthetic asset in the position.
    :type assets: :py:class:`~services.perpetual.public.business_logic.state_objects.PositionAsset`
    """

    public_key: int = field(metadata=fields.public_key_field_metadata)
    collateral_balance: int = field(metadata=fields.balance_field_metadata)
    assets: Mapping[int, PositionAsset] = field(
        metadata=dict(
            marshmallow_field=FrozenDictField(
                keys=fields.asset_id_marshmallow_field,
                values=marshmallow.fields.Nested(PositionAsset.Schema),
            )
        )
    )

    @classmethod
    def empty(cls) -> "PositionState":
        return cls(public_key=0, collateral_balance=0, assets=frozendict())

    @property
    def is_empty(self) -> bool:
        return self.public_key == 0 and self.collateral_balance == 0 and len(self.assets) == 0

    @classmethod
    def prefix(cls):
        return b"position"

    def _hash(self, hash_func: HashFunctionType) -> bytes:
        position_packed = self.collateral_balance - constants.BALANCE_LOWER_BOUND
        position_packed = position_packed * constants.N_ASSETS_UPPER_BOUND + len(self.assets)

        # Hash on the assets is calculated on the sorted assets (by their asset IDs).
        asset_msgs = [
            asset.calculate_message(asset_id) for asset_id, asset in sorted(self.assets.items())
        ]
        assets_hash = b"\x00" * HASH_BYTES
        for asset_msg in asset_msgs:
            assets_hash = hash_func(assets_hash, asset_msg)

        fact_hash = hash_func(
            hash_func(assets_hash, to_bytes(self.public_key)),
            to_bytes(position_packed),
        )

        return fact_hash

    def __eq__(self, other) -> bool:
        if not isinstance(other, PositionState):
            return False
        return (
            self.public_key == other.public_key
            and self.collateral_balance == other.collateral_balance
            and self.assets == other.assets
        )

    @staticmethod
    def asset_value(asset: PositionAsset, asset_price: AssetPrice) -> FixedPoint:
        """
        Converts synthetic asset balance to collateral asset balance.
        Returns a fixed point number with FIXED_POINT_PRECISION precision.
        """
        return asset.balance * FixedPoint(
            rep=asset_price.price, precision_bits=constants.FIXED_POINT_PRECISION
        )

    def total_value(self, asset_prices: AssetPricesMapping) -> FixedPoint:
        """
        Calculates the total value of the position.
        Returns a fixed point number with FIXED_POINT_PRECISION precision.
        """
        total_value = FixedPoint(0, constants.FIXED_POINT_PRECISION)
        total_value += self.collateral_balance
        for asset_id, asset in self.assets.items():
            total_value += self.asset_value(asset=asset, asset_price=asset_prices[asset_id])
        return total_value

    def apply_funding(self, global_funding_indices: FundingIndicesState):
        """
        Computes the total funding for the position and updates the collateral balance
        accordingly. For each synthetic asset in the position, updates the cached funding index.
        """
        updated_assets = {}
        funding_delta = 0
        for asset_id, asset in self.assets.items():
            verify_asset_index_exists(
                asset_id=asset_id, global_funding_indices=global_funding_indices
            )

            global_funding_index = global_funding_indices.indices[asset_id]
            funding_diff = global_funding_index - asset.cached_funding_index

            # Increase of funding index means less collateral balance, and vice versa.
            funding_delta -= asset.balance * funding_diff
            updated_assets[asset_id] = dataclasses.replace(
                asset, cached_funding_index=global_funding_index
            )
        funding_delta //= constants.FIXED_POINT_UNIT

        return dataclasses.replace(
            self, collateral_balance=self.collateral_balance + funding_delta, assets=updated_assets
        )


@marshmallow_dataclass.dataclass(frozen=True)
class OrderState(ValidatedMarshmallowDataclass, LeafFact, StateBase):
    """
    Order state.

    :param fulfilled_amount: Order fulfilled amount.
    :type fulfilled_amount: int
    """

    fulfilled_amount: int = field(metadata=fields.amount_field_metadata)

    @classmethod
    def empty(cls) -> "OrderState":
        return cls(fulfilled_amount=0)

    @property
    def is_empty(self) -> bool:
        return self.fulfilled_amount == 0

    def _hash(self, hash_func: HashFunctionType) -> bytes:
        return to_bytes(self.fulfilled_amount)

    def add(self, fulfilled_amount: int, capacity: int) -> "OrderState":
        stark_assert(
            fulfilled_amount >= 0,
            code=StarkPerpetualErrorCode.INVALID_FULFILLMENT_INFO,
            message=f"Order can't be fulfilled by a negative amount.",
        )
        stark_assert(
            self.fulfilled_amount + fulfilled_amount <= capacity,
            code=StarkPerpetualErrorCode.INVALID_FULFILLMENT_INFO,
            message=f"Order is over fulfilled.",
        )
        return OrderState(fulfilled_amount=self.fulfilled_amount + fulfilled_amount)


@marshmallow_dataclass.dataclass(frozen=True)
class StateUpdate(StateUpdateBase):
    """
    The information describing a state update.

    :param positions: Dictionary mapping position_id to position state.
    :type positions: dict
    :param orders: Dictionary mapping order_id to order state.
    :type orders: dict
    :param position_root: expected position root after update (hex str without prefix).
    :type position_root: str
    :param order_root: expected order root after update (hex str without prefix).
    :type order_root: str
    :param prev_batch_id: Previous batch ID.
    :type prev_batch_id: int
    """

    positions: Dict[int, PositionState]
    orders: Dict[int, OrderState]
    position_root: str
    order_root: str

    @property
    def objects(self):
        return {"position": self.positions, "order": self.orders}

    @property
    def roots(self):
        return {"position": self.position_root, "order": self.order_root}


@marshmallow_dataclass.dataclass(frozen=True)
class BatchDataResponse(BatchDataResponseBase):
    update: Optional[StateUpdate]


def verify_asset_index_exists(asset_id: int, global_funding_indices: FundingIndicesState):
    stark_assert(
        asset_id in global_funding_indices.indices,
        code=StarkPerpetualErrorCode.MISSING_GLOBAL_FUNDING_INDEX,
        message=f"Funding index for asset {hex(asset_id)} does not appear in state.",
    )
