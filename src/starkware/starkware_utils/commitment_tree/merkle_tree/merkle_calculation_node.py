import dataclasses
from typing import List, Optional

from starkware.starkware_utils.commitment_tree.binary_fact_tree import BinaryFactDict
from starkware.starkware_utils.commitment_tree.calculation import (
    Calculation,
    CalculationNode,
    ConstantCalculation,
    HashCalculation,
    LeafFactCalculation,
    NodeFactDict,
)
from starkware.starkware_utils.commitment_tree.leaf_fact import LeafFact
from starkware.starkware_utils.commitment_tree.merkle_tree.merkle_tree_node import (
    MerkleNodeFact,
    MerkleTreeNode,
)
from starkware.starkware_utils.validated_dataclass import ValidatedDataclass
from starkware.storage.storage import FactFetchingContext, HashFunctionType


@dataclasses.dataclass(frozen=True)
class BinaryCalculation(HashCalculation, ValidatedDataclass):
    left: HashCalculation
    right: HashCalculation

    def get_dependency_calculations(self) -> List[Calculation[bytes]]:
        return [self.left, self.right]

    def calculate(
        self,
        dependency_results: List[bytes],
        hash_func: HashFunctionType,
        fact_nodes: NodeFactDict,
    ) -> bytes:
        left_hash, right_hash = dependency_results
        fact = MerkleNodeFact(left_node=left_hash, right_node=right_hash)
        fact_hash = fact._hash(hash_func=hash_func)
        fact_nodes[fact_hash] = fact
        return fact_hash


@dataclasses.dataclass(frozen=True)
class MerkleCalculationNode(CalculationNode[MerkleTreeNode], ValidatedDataclass):
    root_calculation: HashCalculation
    height: int

    def get_dependency_calculations(self) -> List[Calculation[bytes]]:
        return self.root_calculation.get_dependency_calculations()

    def calculate(
        self,
        dependency_results: List[bytes],
        hash_func: HashFunctionType,
        fact_nodes: NodeFactDict,
    ) -> MerkleTreeNode:
        root_value = self.root_calculation.calculate(
            dependency_results=dependency_results, hash_func=hash_func, fact_nodes=fact_nodes
        )
        return MerkleTreeNode(root=root_value, height=self.height)

    @classmethod
    async def combine(
        cls,
        ffc: FactFetchingContext,
        left: "MerkleCalculationNode",
        right: "MerkleCalculationNode",
        facts: Optional[BinaryFactDict],
    ) -> "MerkleCalculationNode":
        """
        Builds a parent node from two BinaryFactTreeNode objects left and right representing
        children nodes.

        If facts argument is not None, this dictionary is filled with facts read from the DB.
        """
        assert right.height == left.height, (
            "Only trees of same height can be combined; "
            f"got: left={left.height} right={right.height}."
        )
        return cls(
            root_calculation=BinaryCalculation(
                left=left.root_calculation, right=right.root_calculation
            ),
            height=left.height + 1,
        )

    @classmethod
    def create_from_node(cls, node: MerkleTreeNode) -> "MerkleCalculationNode":
        return cls(
            root_calculation=ConstantCalculation(value=node.root),
            height=node.height,
        )

    @classmethod
    def create_from_fact(cls, fact: LeafFact) -> "MerkleCalculationNode":
        return cls(root_calculation=LeafFactCalculation(fact=fact), height=0)
