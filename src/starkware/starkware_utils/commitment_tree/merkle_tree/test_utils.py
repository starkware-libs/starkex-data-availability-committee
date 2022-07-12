from typing import List, Tuple

from starkware.starkware_utils.commitment_tree.leaf_fact import LeafFact
from starkware.starkware_utils.commitment_tree.merkle_tree.merkle_tree import MerkleTree
from starkware.storage.storage import FactFetchingContext

MerkleBytesRootPair = Tuple[bytes, bytes]


async def build_merkle_tree(
    ffc: FactFetchingContext,
    tree_height: int,
    empty_leaf_fact: LeafFact,
    non_empty_leaves: List[Tuple[int, LeafFact]],
) -> MerkleTree:
    merkle_tree = await MerkleTree.empty_tree(
        ffc=ffc, height=tree_height, leaf_fact=empty_leaf_fact
    )
    return await merkle_tree.update(ffc=ffc, modifications=non_empty_leaves)
