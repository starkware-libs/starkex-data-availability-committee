import dataclasses
from typing import Optional, Tuple, Type, TypeVar

import marshmallow_dataclass

from starkware.python.utils import from_bytes, to_bytes
from starkware.starkware_utils.commitment_tree.binary_fact_tree import BinaryFactDict
from starkware.starkware_utils.commitment_tree.binary_fact_tree_node import (
    BinaryFactTreeNode,
    read_node_fact,
)
from starkware.starkware_utils.commitment_tree.inner_node_fact import InnerNodeFact
from starkware.starkware_utils.validated_dataclass import ValidatedDataclass
from starkware.storage.storage import HASH_BYTES, Fact, FactFetchingContext, HashFunctionType

TMerkleNodeFact = TypeVar("TMerkleNodeFact", bound="MerkleNodeFact")
TLeafNodeFact = TypeVar("TLeafNodeFact", bound=Fact)


@dataclasses.dataclass(frozen=True)
class MerkleNodeFact(InnerNodeFact, ValidatedDataclass):
    left_node: bytes
    right_node: bytes

    def serialize(self) -> bytes:
        return b"".join(map(to_bytes, self.to_tuple()))

    @classmethod
    def deserialize(cls: Type[TMerkleNodeFact], data: bytes) -> TMerkleNodeFact:
        assert len(data) == 2 * HASH_BYTES
        return cls(left_node=data[:HASH_BYTES], right_node=data[HASH_BYTES:])

    def _hash(self, hash_func: HashFunctionType) -> bytes:
        return hash_func(self.left_node, self.right_node)

    @classmethod
    def prefix(cls) -> bytes:
        return b"merkle_node"

    def to_tuple(self) -> Tuple[int, ...]:
        """
        Returns a representation of the fact's preimage as a tuple.
        """
        return from_bytes(self.left_node), from_bytes(self.right_node)


@marshmallow_dataclass.dataclass(frozen=True)
class MerkleTreeNode(BinaryFactTreeNode):
    """
    An immutable Merkle tree backed by an immutable fact storage.
    """

    root: bytes
    height: int

    @property
    def _leaf_hash(self) -> bytes:
        return self.root

    @classmethod
    def create_leaf(cls, hash_value: bytes) -> "MerkleTreeNode":
        return cls(root=hash_value, height=0)

    def get_height_in_tree(self) -> int:
        return self.height

    async def get_children(
        self, ffc: FactFetchingContext, facts: Optional[BinaryFactDict] = None
    ) -> Tuple["MerkleTreeNode", "MerkleTreeNode"]:
        """
        Returns the two MerkleTrees which are the subtrees of the current MerkleTreeNode.
        """
        root_fact = await read_node_fact(
            ffc=ffc, inner_node_fact_cls=MerkleNodeFact, fact_hash=self.root, facts=facts
        )

        return (
            MerkleTreeNode(root=root_fact.left_node, height=self.height - 1),
            MerkleTreeNode(root=root_fact.right_node, height=self.height - 1),
        )

    async def get_node(self, ffc: FactFetchingContext, index: int) -> "MerkleTreeNode":
        """
        Returns the node at the given index, where 1 is self, 2 is its left child, 3 is its right
        child and so on.
        """
        # Get the left/right directions from the root to the node.
        # For example, for node #14, the binary representation is 1110 which translates to
        # 1 - node depth, 1 - right, 1 - right, 0 - left.
        dirs = list(map(int, bin(index)[2:]))[1:]

        node = self
        for direction in dirs:
            node = (await node.get_children(ffc))[direction]

        return node

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MerkleTreeNode):
            return NotImplemented
        return self.root == other.root and self.height == other.height
