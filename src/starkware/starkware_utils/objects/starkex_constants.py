# Starkex-state object paths.
VAULT_STATE_PATH_STARKEX = "starkware.starkware_utils.objects.starkex_state.VaultState"
ORDER_STATE_PATH_STARKEX = "starkware.starkware_utils.objects.starkex_state.OrderState"
VAULT_TREE_PATH_STARKEX = (
    "starkware.starkware_utils.commitment_tree.merkle_tree.merkle_tree.MerkleTree"
)
ORDER_TREE_PATH_STARKEX = (
    "starkware.starkware_utils.commitment_tree.patricia_tree.patricia_tree.PatriciaTree"
)
BATCH_RESPONSE_PATH_STARKEX = "starkware.starkware_utils.objects.starkex_state.BatchDataResponse"

# Constant tree roots.
OBSOLETE_ORDER_TREE_ROOT_STR = "DEADBEEF" * 8
OBSOLETE_ORDER_TREE_ROOT = bytes.fromhex(OBSOLETE_ORDER_TREE_ROOT_STR)
assert len(OBSOLETE_ORDER_TREE_ROOT) == 32
