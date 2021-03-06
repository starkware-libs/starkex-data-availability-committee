from starkware.crypto.signature.signature import FIELD_PRIME

FIELD_SIZE = FIELD_PRIME

ORDER_MERKLE_TREE_HEIGHT = 64
POSITION_MERKLE_TREE_HEIGHT = 64

AMOUNT_UPPER_BOUND = 2 ** 64
ASSET_ID_UPPER_BOUND = 2 ** 120
ASSET_NAME_UPPER_BOUND = 2 ** 128
ASSET_RESOLUTION_LOWER_BOUND = 1
ASSET_RESOLUTION_UPPER_BOUND = 2 ** 64
BALANCE_UPPER_BOUND = 2 ** 63
BALANCE_LOWER_BOUND = -BALANCE_UPPER_BOUND
COLLATERAL_ASSET_ID_UPPER_BOUND = 2 ** 250
EXTERNAL_PRICE_LOWER_BOUND = 1
EXTERNAL_PRICE_UPPER_BOUND = 2 ** 120
FIXED_POINT_PRECISION = 32
FIXED_POINT_UNIT = 2 ** FIXED_POINT_PRECISION
FUNDING_INDEX_UPPER_BOUND = 2 ** 63
FUNDING_INDEX_LOWER_BOUND = -(2 ** 63)
FUNDING_RATE_UPPER_BOUND = 2 ** 64
N_ASSETS_UPPER_BOUND = 2 ** 16
ONCHAIN_DATA_ASSET_ID_OFFSET = 64
ORACLE_NAME_UPPER_BOUND = 2 ** 40
ORACLE_PRICE_QUORUM_LOWER_BOUND = 1
ORACLE_PRICE_QUORUM_UPPER_BOUND = 2 ** 32
# Oracle_price_signed_asset_id = asset_name | oracle_name.
ORACLE_PRICE_SIGNED_ASSET_ID_UPPER_BOUND = ORACLE_NAME_UPPER_BOUND * ASSET_NAME_UPPER_BOUND
POSITION_ID_UPPER_BOUND = 2 ** POSITION_MERKLE_TREE_HEIGHT
PRICE_LOWER_BOUND = 1
REDUCED_PRICE_UPPER_BOUND = 2 ** 32
PRICE_UPPER_BOUND = REDUCED_PRICE_UPPER_BOUND * FIXED_POINT_UNIT
PUBLIC_KEY_UPPER_BOUND = FIELD_SIZE
RISK_FACTOR_LOWER_BOUND = 1
RISK_FACTOR_UPPER_BOUND = FIXED_POINT_UNIT
TIMESTAMP_UPPER_BOUND = 2 ** 32

# Perpetual-state object paths.
POSITION_STATE_PATH_PERPETUAL = (
    "services.perpetual.public.business_logic.state_objects.PositionState"
)
ORDER_STATE_PATH_PERPETUAL = "services.perpetual.public.business_logic.state_objects.OrderState"
POSITION_TREE_PATH_PERPETUAL = (
    "starkware.starkware_utils.commitment_tree.merkle_tree.merkle_tree.MerkleTree"
)
ORDER_TREE_PATH_PERPETUAL = (
    "starkware.starkware_utils.commitment_tree.merkle_tree.merkle_tree.MerkleTree"
)
BATCH_RESPONSE_PATH_PERPETUAL = (
    "services.perpetual.public.business_logic.state_objects.BatchDataResponse"
)
