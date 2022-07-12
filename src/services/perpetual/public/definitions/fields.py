import marshmallow.fields as mfields

from services.perpetual.public.definitions import constants
from services.perpetual.public.definitions.error_codes import StarkPerpetualErrorCode
from starkware.starkware_utils.error_handling import StarkErrorCode
from starkware.starkware_utils.marshmallow_dataclass_fields import IntAsHex, IntAsStr
from starkware.starkware_utils.validated_fields import (
    RangeValidatedField,
    int_as_hex_metadata,
    int_as_str_metadata,
)

AmountField = RangeValidatedField(
    lower_bound=0,
    upper_bound=constants.AMOUNT_UPPER_BOUND,
    name="Amount",
    error_code=StarkErrorCode.OUT_OF_RANGE_AMOUNT,
    formatter=None,
)

amount_field_metadata = int_as_str_metadata(validated_field=AmountField)

AssetIdField = RangeValidatedField(
    lower_bound=0,
    upper_bound=constants.ASSET_ID_UPPER_BOUND,
    name="Asset ID",
    error_code=StarkPerpetualErrorCode.OUT_OF_RANGE_ASSET_ID,
    formatter=hex,
)

asset_id_marshmallow_field = IntAsHex(required=True, validate=AssetIdField.validate)
asset_id_field_metadata = dict(
    marshmallow_field=asset_id_marshmallow_field, validated_field=AssetIdField
)

AssetResolutionField = RangeValidatedField(
    lower_bound=constants.ASSET_RESOLUTION_LOWER_BOUND,
    upper_bound=constants.ASSET_RESOLUTION_UPPER_BOUND,
    name="Asset resolution",
    error_code=StarkPerpetualErrorCode.OUT_OF_RANGE_ASSET_RESOLUTION,
    formatter=hex,
)

asset_resolution_field_metadata = int_as_hex_metadata(validated_field=AssetResolutionField)

BalanceField = RangeValidatedField(
    lower_bound=constants.BALANCE_LOWER_BOUND,
    upper_bound=constants.BALANCE_UPPER_BOUND,
    name="Balance",
    error_code=StarkErrorCode.OUT_OF_RANGE_BALANCE,
    formatter=None,
)

balance_field_metadata = int_as_str_metadata(validated_field=BalanceField)

CollateralAssetIdField = RangeValidatedField(
    lower_bound=0,
    upper_bound=constants.COLLATERAL_ASSET_ID_UPPER_BOUND,
    name="Collateral asset ID",
    error_code=StarkPerpetualErrorCode.OUT_OF_RANGE_COLLATERAL_ASSET_ID,
    formatter=hex,
)

collateral_asset_id_marshmallow_field = IntAsHex(
    required=True, validate=CollateralAssetIdField.validate
)
collateral_asset_id_field_metadata = dict(
    marshmallow_field=collateral_asset_id_marshmallow_field, validated_field=CollateralAssetIdField
)

ExternalPriceField = RangeValidatedField(
    lower_bound=constants.EXTERNAL_PRICE_LOWER_BOUND,
    upper_bound=constants.EXTERNAL_PRICE_UPPER_BOUND,
    name="External price",
    error_code=StarkPerpetualErrorCode.OUT_OF_RANGE_EXTERNAL_PRICE,
    formatter=None,
)

external_price_field_metadata = int_as_str_metadata(validated_field=ExternalPriceField)

FundingIndexField = RangeValidatedField(
    lower_bound=constants.FUNDING_INDEX_LOWER_BOUND,
    upper_bound=constants.FUNDING_INDEX_UPPER_BOUND,
    name="Funding index",
    error_code=StarkPerpetualErrorCode.OUT_OF_RANGE_FUNDING_INDEX,
    formatter=None,
)

funding_index_field_marshmallow_field = IntAsStr(required=True, validate=FundingIndexField.validate)
funding_index_field_metadata = dict(
    marshmallow_field=funding_index_field_marshmallow_field, validated_field=FundingIndexField
)

funding_indices_field_metadata = dict(
    marshmallow_field=mfields.Dict(
        keys=asset_id_marshmallow_field, values=funding_index_field_marshmallow_field
    )
)

FundingRateField = RangeValidatedField(
    lower_bound=0,
    upper_bound=constants.FUNDING_RATE_UPPER_BOUND,
    name="Funding rate",
    error_code=StarkPerpetualErrorCode.OUT_OF_RANGE_FUNDING_RATE,
    formatter=None,
)

funding_rate_field_metadata = int_as_str_metadata(validated_field=FundingRateField)

OraclePriceQuorumField = RangeValidatedField(
    lower_bound=constants.ORACLE_PRICE_QUORUM_LOWER_BOUND,
    upper_bound=constants.ORACLE_PRICE_QUORUM_UPPER_BOUND,
    name="Asset oracle price quorum",
    error_code=StarkErrorCode.OUT_OF_RANGE_ORACLE_PRICE_QUORUM,
    formatter=hex,
)

oracle_price_quorum_metadata = int_as_hex_metadata(validated_field=OraclePriceQuorumField)

OraclePriceSignedAssetIdField = RangeValidatedField(
    lower_bound=0,
    upper_bound=constants.ORACLE_PRICE_SIGNED_ASSET_ID_UPPER_BOUND,
    name="Oracle price signed asset ID",
    error_code=StarkPerpetualErrorCode.OUT_OF_RANGE_ORACLE_PRICE_SIGNED_ASSET_ID,
    formatter=hex,
)

oracle_price_signed_asset_id_marshmallow_field = IntAsHex(
    required=True, validate=OraclePriceSignedAssetIdField.validate
)
oracle_price_signed_asset_id_field_metadata = dict(
    marshmallow_field=oracle_price_signed_asset_id_marshmallow_field,
    validated_field=OraclePriceSignedAssetIdField,
)

PositionIdField = RangeValidatedField(
    lower_bound=0,
    upper_bound=constants.POSITION_ID_UPPER_BOUND,
    name="Position ID",
    error_code=StarkPerpetualErrorCode.OUT_OF_RANGE_POSITION_ID,
    formatter=None,
)

position_id_field_metadata = int_as_str_metadata(validated_field=PositionIdField)

PriceField = RangeValidatedField(
    lower_bound=constants.PRICE_LOWER_BOUND,
    upper_bound=constants.PRICE_UPPER_BOUND,
    name="Price",
    error_code=StarkPerpetualErrorCode.OUT_OF_RANGE_PRICE,
    formatter=None,
)

price_field_metadata = int_as_str_metadata(validated_field=PriceField)

PublicKeyField = RangeValidatedField(
    lower_bound=0,
    upper_bound=constants.PUBLIC_KEY_UPPER_BOUND,
    name="Public key",
    error_code=StarkErrorCode.OUT_OF_RANGE_PUBLIC_KEY,
    formatter=hex,
)

public_key_marshmallow_field = IntAsHex(required=True, validate=PublicKeyField.validate)
public_key_field_metadata = dict(
    marshmallow_field=public_key_marshmallow_field, validated_field=PublicKeyField
)

RiskFactorField = RangeValidatedField(
    lower_bound=constants.RISK_FACTOR_LOWER_BOUND,
    upper_bound=constants.RISK_FACTOR_UPPER_BOUND,
    name="Risk factor",
    error_code=StarkPerpetualErrorCode.OUT_OF_RANGE_RISK_FACTOR,
    formatter=None,
)

risk_factor_field_metadata = int_as_str_metadata(validated_field=RiskFactorField)

TimestampField = RangeValidatedField(
    lower_bound=0,
    upper_bound=constants.TIMESTAMP_UPPER_BOUND,
    name="Timestamp",
    error_code=StarkPerpetualErrorCode.OUT_OF_RANGE_TIMESTAMP,
    formatter=None,
)

timestamp_field_metadata = int_as_str_metadata(validated_field=TimestampField)
