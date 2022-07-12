"""
Dumps the vault tree from the database to files.

Run this script using:
  python -m committee.dump_trees <args...>
Make sure the committee package is installed or in PYTHONPATH.
"""

import argparse
import asyncio
import json
import sys
from typing import IO, Optional, TextIO

from committee.committee import Committee
from committee.dump_trees_utils import DumpInfo, get_storage
from starkware.crypto.signature.fast_pedersen_hash import pedersen_hash_func
from starkware.python.utils import to_bytes
from starkware.starkware_utils.commitment_tree.merkle_tree.dump_tree_diff import dump_tree_diff
from starkware.starkware_utils.commitment_tree.merkle_tree.merkle_tree import MerkleTree
from starkware.starkware_utils.objects.starkex_state import OrderState, VaultState
from starkware.storage.storage import FactFetchingContext


class MainHandler:
    async def main(self):
        parser = argparse.ArgumentParser(
            description="""\
Dumps a vaults tree from the database.

The output is composed of two csv files.
A nodes file and a vaults file.
The structure of the nodes file is:
"index node_hash"
where index is the index of the node in a "binary tree in array represention",
i.e. 2**(node_layer) + node_index_in_layer.

The structure of the vaults file is:
"vault_id stark_key token_id balance"
    """
        )
        parser.add_argument("--batch_id", type=int, help="Batch id")
        parser.add_argument(
            "--config_file", type=str, help="path to config file with storage configuration"
        )

        commands = {
            "vaults": self.dump_vault_tree,
            "orders": self.dump_order_tree,
            "info": self.dump_info,
        }
        parser.add_argument("command", choices=commands.keys())

        args, command_specific_args = parser.parse_known_args()
        self.storage = await get_storage(args.config_file)
        self.ffc = FactFetchingContext(self.storage, pedersen_hash_func)

        self.batch_id = self.batch_info = self.vault_root = self.order_root = None
        if args.batch_id is not None:
            self.batch_id = args.batch_id
            self.batch_info = await Committee.get_committee_batch_info_or_fail(
                storage=self.storage, batch_id=args.batch_id
            )
            self.vault_root = self.batch_info.merkle_roots["vault"]
            self.order_root = self.batch_info.merkle_roots["order"]

        await commands[args.command](command_specific_args)

    async def dump_vault_tree(self, command_specific_args):
        parser = argparse.ArgumentParser()
        parser.add_argument("--vault_root", type=str, help="Root of the vault Merkle tree")
        parser.add_argument(
            "--vault_height", type=int, default=31, help="Height of vaults Merkle Tree"
        )
        parser.add_argument(
            "--nodes_file", type=argparse.FileType("w"), help="Name of the output nodes csv file"
        )
        parser.add_argument(
            "--vaults_file", type=argparse.FileType("w"), help="Name of the output vaults csv file"
        )

        args = parser.parse_args(command_specific_args)

        if self.vault_root is None:
            self.vault_root = to_bytes(int(args.vault_root, 16))
        else:
            assert (
                args.vault_root is None
            ), "--vault_root cannot be explicitly specified if --batch_id is given."

        await dump_vaults_tree(
            self.ffc, self.vault_tree(args.vault_height), args.nodes_file, args.vaults_file
        )

    async def dump_order_tree(self, command_specific_args):
        parser = argparse.ArgumentParser()
        parser.add_argument("--order_root", type=str, help="Root of the order Merkle tree")
        parser.add_argument(
            "--order_height", type=int, default=251, help="Height of orders Merkle Tree"
        )
        parser.add_argument(
            "--orders_file", type=argparse.FileType("w"), help="Name of the output orders csv file"
        )
        parser.add_argument(
            "--order_node_idx",
            type=int,
            default=1,
            help="If specified, only dumps orders below the given node.",
        )

        args = parser.parse_args(command_specific_args)

        if self.order_root is None:
            self.order_root = to_bytes(int(args.order_root, 16))
        else:
            assert (
                args.order_root is None
            ), "--order_root cannot be explicitly specified if --batch_id is given."

        await dump_orders_tree(
            self.ffc,
            self.order_tree(args.order_height),
            args.orders_file,
            node_idx=args.order_node_idx,
        )

    async def dump_info(self, command_specific_args):
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--dump_info_file",
            type=argparse.FileType("w"),
            help="Name of the output dump info file",
        )
        parser.add_argument(
            "--order_node_depth",
            type=int,
            default=0,
            help='The depth of the nodes used in "dump_trees orders --order_node_idx=*"',
        )
        args = parser.parse_args(command_specific_args)

        assert self.batch_info is not None, '--batch_id must be specified with the "info" command.'
        first_order_node_idx = 2 ** args.order_node_depth
        # Note that 0 is not the height of the tree, but it has no effect on the code below.
        order_tree = self.order_tree(0)
        assert self.batch_id is not None
        dump_info_content = DumpInfo(
            batch_id=self.batch_id,
            batch_info=self.batch_info,
            order_subtree_roots=[
                (await order_tree.get_node(self.ffc, i)).root.hex()
                for i in range(first_order_node_idx, 2 * first_order_node_idx)
            ],
        )
        json.dump(dump_info_content.dump(), args.dump_info_file, indent=4)

    def vault_tree(self, height):
        return MerkleTree(root=self.vault_root, height=height)

    def order_tree(self, height):
        return MerkleTree(root=self.order_root, height=height)


async def dump_vaults_tree(
    ffc: FactFetchingContext,
    tree: MerkleTree,
    nodes_file: Optional[IO[str]],
    vaults_file: Optional[IO[str]],
):
    """
    Dump 'tree' into the given output files.
    """
    await dump_tree_diff(ffc, tree, nodes_file, vaults_file, 1, dump_vault_leaf, VaultState.empty())


async def dump_orders_tree(
    ffc: FactFetchingContext, tree: MerkleTree, orders_file: TextIO, node_idx: int
):
    """
    Dump 'tree' into the given output files.
    """
    await dump_tree_diff(
        ffc, tree, None, orders_file, node_idx, dump_order_leaf, OrderState.empty()
    )


async def dump_vault_leaf(ffc, tree, index, node, csv_writer):
    data = await VaultState.get_or_fail(storage=ffc.storage, suffix=node.root)
    vault_id = index - 2 ** tree.height
    csv_writer.writerow([vault_id, data.stark_key, data.token, data.balance])


async def dump_order_leaf(ffc, tree, index, node, csv_writer):
    data = await OrderState.get_or_fail(storage=ffc.storage, suffix=node.root)
    order_id = index - 2 ** tree.height
    csv_writer.writerow([order_id, data.fulfilled_amount])


def run_main():
    sys.exit(asyncio.run(MainHandler().main()))
