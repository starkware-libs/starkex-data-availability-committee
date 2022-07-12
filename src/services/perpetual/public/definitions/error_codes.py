from enum import auto

from starkware.starkware_utils.error_handling import ErrorCode


class StarkPerpetualErrorCode(ErrorCode):
    #: New position after transaction-induced updates has larger absolute value of synthetic asset.
    ILLEGAL_POSITION_TRANSITION_ENLARGING_SYNTHETIC_HOLDINGS = 0
    #: New position after transaction-induced updates has smaller tv / tr.
    ILLEGAL_POSITION_TRANSITION_REDUCING_TOTAL_VALUE_RISK_RATIO = auto()
    #: Position before transaction-induced updates has tr = 0 and tv got smaller.
    ILLEGAL_POSITION_TRANSITION_NO_RISK_REDUCED_VALUE = auto()
    #: Asset oracle price is not valid (for example, median price does not match the signed prices).
    INVALID_ASSET_ORACLE_PRICE = auto()
    #: Collateral asset id does not match the configured collateral asset id.
    INVALID_COLLATERAL_ASSET_ID = auto()
    #: Fee position is participating in a transaction it can't participate in (trade, liquidate).
    INVALID_FEE_POSITION_PARTICIPATION = auto()
    #: Forced transaction is not valid (for example, is_valid is wrong).
    INVALID_FORCED_TRANSACTION = auto()
    #: Synthetic/collateral order ratio not satisfied in fulfillment transaction.
    INVALID_FULFILLMENT_ASSETS_RATIO = auto()
    #: Fee/synthetic order ratio not satisfied in fulfillment transaction.
    INVALID_FULFILLMENT_FEE_RATIO = auto()
    #: Fulfillment transaction and order amounts mismatch.
    INVALID_FULFILLMENT_INFO = auto()
    #: Funding tick rate is out of range.
    INVALID_FUNDING_TICK_RATE = auto()
    #: Funding tick timestamp is not valid, not progressing compared to the previous.
    INVALID_FUNDING_TICK_TIMESTAMP = auto()
    #: Liquidate didnt create a smaller position.
    INVALID_LIQUIDATE = auto()
    #: Mismatching assets for orders in fulfillment transaction.
    INVALID_ORDER_ASSETS = auto()
    #: Order is_buying property is not set correctly.
    INVALID_ORDER_IS_BUYING_PROPERTY = auto()
    #: Public key is not valid (for example, does not match the position's public key).
    INVALID_PUBLIC_KEY = auto()
    #: Synthetic asset id does not match any of the configured synthetic asset ids.
    INVALID_SYNTHETIC_ASSET_ID = auto()
    #: Tick's timestamp isn't close enough to the blockchain time.
    INVALID_TICK_TIMESTAMP_DISTANCE_FROM_BLOCKCHAIN_TIME = auto()
    #: Missing global funding index for synthetic asset.
    MISSING_GLOBAL_FUNDING_INDEX = auto()
    #: Missing oracle price for synthetic asset.
    MISSING_ORACLE_PRICE = auto()
    #: Missing oracle price for synthetic asset with enough signatures in valid time range.
    MISSING_ORACLE_PRICE_SIGNED_IN_TIME_RANGE = auto()
    #: Missing signed oracle price for synthetic asset (not enough signatures).
    MISSING_SIGNED_ORACLE_PRICE = auto()
    #: Missing synthetic asset id.
    MISSING_SYNTHETIC_ASSET_ID = auto()
    #: Asset ID value is out of range.
    OUT_OF_RANGE_ASSET_ID = auto()
    #: Synthetic asset resolution is out of range.
    OUT_OF_RANGE_ASSET_RESOLUTION = auto()
    #: Collateral asset ID value is out of range.
    OUT_OF_RANGE_COLLATERAL_ASSET_ID = auto()
    #: Contract address value is out of range.
    OUT_OF_RANGE_CONTRACT_ADDRESS = auto()
    #: External price value is out of range.
    OUT_OF_RANGE_EXTERNAL_PRICE = auto()
    #: External asset ID value is out of range.
    OUT_OF_RANGE_ORACLE_PRICE_SIGNED_ASSET_ID = auto()
    #: Fact value is out of range.
    OUT_OF_RANGE_FACT = auto()
    #: Funding index value is out of range.
    OUT_OF_RANGE_FUNDING_INDEX = auto()
    #: Funding rate value is out of range.
    OUT_OF_RANGE_FUNDING_RATE = auto()
    #: Position ID value is out of range.
    OUT_OF_RANGE_POSITION_ID = auto()
    #: Price value is out of range.
    OUT_OF_RANGE_PRICE = auto()
    #: Risk factor value is out of range.
    OUT_OF_RANGE_RISK_FACTOR = auto()
    #: Timestamp value is out of range.
    OUT_OF_RANGE_TIMESTAMP = auto()
    #: Total risk is out of range.
    OUT_OF_RANGE_TOTAL_RISK = auto()
    #: Total value is out of range.
    OUT_OF_RANGE_TOTAL_VALUE = auto()
    #: A transaction involving two parties cannot be between a position and itself.
    SAME_POSITION_ID = auto()
    #: System time must not decrease.
    SYSTEM_TIME_DECREASING = auto()
    #: A position has too many synthetic assets.
    TOO_MANY_SYNTHETIC_ASSETS_IN_POSITION = auto()
    #: The general config contains too many synthetic assets.
    TOO_MANY_SYNTHETIC_ASSETS_IN_SYSTEM = auto()
    #: Transaction received successfully by the gateway.
    TRANSACTION_RECEIVED = auto()
    #: Deleverage is not fair, not deleveraging the maxmum amount.
    UNFAIR_DELEVERAGE = auto()
    #: Position containing funds and is unassigned to a public key.
    UNASSIGNED_POSITION_FUNDS = auto()
    #: Position can not be deleveraged.
    UNDELEVERAGABLE_POSITION = auto()
    #: Position can not be liquidated.
    UNLIQUIDATABLE_POSITION = auto()


class UnsupportedPerpetualTransactionException(Exception):
    pass
