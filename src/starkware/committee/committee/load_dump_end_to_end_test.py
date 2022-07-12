import random
from io import StringIO

import pytest

from committee.dump_trees import dump_orders_tree, dump_vaults_tree
from committee.load_trees_from_file import complete_tree, update_orders, update_vaults
from starkware.crypto.signature.fast_pedersen_hash import pedersen_hash_func
from starkware.starkware_utils.commitment_tree.merkle_tree.merkle_tree import MerkleTree
from starkware.starkware_utils.commitment_tree.merkle_tree.merkle_tree_node import MerkleTreeNode
from starkware.storage.dict_storage import DictStorage
from starkware.storage.storage import FactFetchingContext


@pytest.mark.asyncio
async def test_load_dump_vaults():
    VAULT_HEIGHT = 20
    MAX_VAULT = 2 ** VAULT_HEIGHT
    MAX_KEY = MAX_TOKEN = MAX_BALANCE = 10 ** 6
    vault_ids = random.sample(range(0, MAX_VAULT), 20)
    csv_input = "".join(
        f"{vault_id},{random.randint(1, MAX_KEY)},"
        + f"{random.randint(1, MAX_TOKEN)},{random.randint(1, MAX_BALANCE)}\n"
        for vault_id in vault_ids
    )

    storage = DictStorage()
    ffc = FactFetchingContext(storage, pedersen_hash_func)
    tree = await update_vaults(StringIO(csv_input), VAULT_HEIGHT, storage)

    output_file = StringIO()
    await dump_vaults_tree(ffc, tree, None, output_file)
    assert set(output_file.getvalue().splitlines()) == set(csv_input.splitlines())


@pytest.mark.asyncio
async def test_load_dump_orders():
    ORDER_HEIGHT = 16
    MAX_AMOUNT = 10 ** 6

    # Create 4 csv files which correspond to nodes 4, 5, 6 and 7 of the order tree.
    csv_inputs = []
    for i in range(4):
        min_idx = 2 ** ORDER_HEIGHT // 4 * i
        max_idx = 2 ** ORDER_HEIGHT // 4 * (i + 1)
        order_ids = random.sample(range(min_idx, max_idx), 8)
        csv_inputs.append(
            "".join(f"{order_id},{random.randint(0, MAX_AMOUNT)}\n" for order_id in order_ids)
        )

    storage = DictStorage()
    ffc = FactFetchingContext(storage, pedersen_hash_func)
    subtree_roots = []
    for i, csv_input in enumerate(csv_inputs, 4):
        partial_tree = await update_orders(StringIO(csv_input), ORDER_HEIGHT, storage)
        partial_tree_node = MerkleTreeNode(root=partial_tree.root, height=partial_tree.height)
        node = await partial_tree_node.get_node(ffc, i)
        subtree_roots.append(node.root)

    order_root = await complete_tree(subtree_roots, storage)
    tree = MerkleTree(root=order_root, height=ORDER_HEIGHT)

    # Dump data in 4 parts (nodes 4, 5, 6, 7).
    for i, csv_input in enumerate(csv_inputs, 4):
        output_file = StringIO()
        await dump_orders_tree(ffc, tree, output_file, i)
        assert set(output_file.getvalue().splitlines()) == set(csv_input.splitlines())
