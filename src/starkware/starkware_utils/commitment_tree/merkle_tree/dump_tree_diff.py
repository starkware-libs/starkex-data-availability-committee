import csv
from typing import Optional, Set, TextIO

from starkware.starkware_utils.commitment_tree.merkle_tree.merkle_tree import MerkleTree
from starkware.starkware_utils.commitment_tree.merkle_tree.merkle_tree_node import MerkleTreeNode
from starkware.starkware_utils.commitment_tree.merkle_tree.traverse_tree import traverse_tree
from starkware.storage.storage import FactFetchingContext


async def dump_tree_diff(
    ffc: FactFetchingContext,
    tree: MerkleTree,
    nodes_file: Optional[TextIO],
    leaves_file: Optional[TextIO],
    node_idx: int,
    dump_leaf_callback,
    default_leaf,
):
    empty_trees: Set[bytes] = set(
        MerkleTree.empty_tree_roots(tree.height, default_leaf, ffc.hash_func)
    )

    nodes_writer = csv.writer(nodes_file, delimiter=",") if nodes_file else None
    leaves_writer = csv.writer(leaves_file, delimiter=",") if leaves_file else None

    # Traverse the tree, obtaining data from leaves, and ignoring empty subtrees.
    async def process_node(node_tuple):
        index, node = node_tuple

        if nodes_writer is not None:
            data = node.root.hex()
            nodes_writer.writerow([index, data])

        if node.root in empty_trees:
            return

        if node.height == 0:
            if leaves_writer is not None:
                await dump_leaf_callback(ffc, tree, index, node, leaves_writer)
        else:
            node_children = await node.get_children(ffc)
            yield (2 * index, node_children[0])
            yield (2 * index + 1, node_children[1])

    tree_node = MerkleTreeNode(root=tree.root, height=tree.height)
    await traverse_tree(
        get_children_callback=process_node,
        root=(node_idx, await tree_node.get_node(ffc, node_idx)),
        n_workers=ffc.n_workers,
    )

    if nodes_file:
        nodes_file.flush()
    if leaves_file:
        leaves_file.flush()
