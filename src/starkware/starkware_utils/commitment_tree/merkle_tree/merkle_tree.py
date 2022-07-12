from typing import Collection, Dict, List, Optional, Tuple, Type

import marshmallow_dataclass

from starkware.starkware_utils.commitment_tree.binary_fact_tree import (
    BinaryFactDict,
    BinaryFactTree,
    TLeafFact,
)
from starkware.starkware_utils.commitment_tree.binary_fact_tree_node import write_node_fact
from starkware.starkware_utils.commitment_tree.leaf_fact import LeafFact
from starkware.starkware_utils.commitment_tree.merkle_tree.merkle_calculation_node import (
    MerkleCalculationNode,
)
from starkware.starkware_utils.commitment_tree.merkle_tree.merkle_tree_node import (
    MerkleNodeFact,
    MerkleTreeNode,
)
from starkware.starkware_utils.commitment_tree.update_tree import update_tree
from starkware.storage.storage import FactFetchingContext, HashFunctionType

MerkleBytesRootPair = Tuple[bytes, bytes]
MerkleBytesRootTriplet = Tuple[bytes, bytes, bytes]
MerkleTreePair = Tuple["MerkleTree", "MerkleTree"]


@marshmallow_dataclass.dataclass(frozen=True)
class MerkleTree(BinaryFactTree):
    """
    An immutable Merkle tree backed by an immutable fact storage.
    """

    @classmethod
    async def empty_tree(
        cls, ffc: FactFetchingContext, height: int, leaf_fact: LeafFact
    ) -> "MerkleTree":
        """
        Initializes an empty MerkleTree of the given height. Each layer contains exactly one
        object - The leaf layer contains the given leaf_fact, and each other layer contains
        one node with the two left and right children pointing to the object in the layer
        below it.
        """
        assert height >= 0, f"Trying to create a tree with negative height {height}."
        tree = cls(root=await leaf_fact.set_fact(ffc=ffc), height=0)
        for _ in range(height):
            root_fact = MerkleNodeFact(left_node=tree.root, right_node=tree.root)
            root = await write_node_fact(ffc=ffc, inner_node_fact=root_fact, facts=None)
            tree = cls(root=root, height=tree.height + 1)

        return tree

    @staticmethod
    def empty_tree_roots(
        max_height: int, leaf_fact: LeafFact, hash_func: HashFunctionType
    ) -> List[bytes]:
        """
        Returns a list of roots of empty trees with height up to 'max_height'.
        """
        assert max_height >= 0
        roots = [leaf_fact._hash(hash_func)]

        for _ in range(max_height):
            roots.append(hash_func(roots[-1], roots[-1]))
        return roots

    async def _get_leaves(
        self,
        ffc: FactFetchingContext,
        indices: Collection[int],
        fact_cls: Type[TLeafFact],
        facts: Optional[BinaryFactDict] = None,
    ) -> Dict[int, TLeafFact]:
        """
        Returns the values of the leaves whose indices are given and the facts of their paths from
        the root.
        """
        merkle_tree_node = MerkleTreeNode(root=self.root, height=self.height)
        return await merkle_tree_node._get_leaves(
            ffc=ffc, indices=indices, fact_cls=fact_cls, facts=facts
        )

    async def update(
        self,
        ffc: FactFetchingContext,
        modifications: Collection[Tuple[int, LeafFact]],
        facts: Optional[BinaryFactDict] = None,
    ) -> "MerkleTree":
        """
        Updates the tree with the given list of modifications, writes all the new facts to the
        storage and returns a new MerkleTree representing the fact of the root of the new tree.

        If facts argument is not None, this dictionary is filled during traversal through the tree
        by the facts of their paths from the root down.
        """
        merkle_tree_node = MerkleTreeNode(root=self.root, height=self.height)
        merkle_tree_node = await update_tree(
            tree=merkle_tree_node,
            ffc=ffc,
            modifications=modifications,
            facts=facts,
            calculation_node_cls=MerkleCalculationNode,
        )
        return MerkleTree(root=merkle_tree_node.root, height=merkle_tree_node.height)
