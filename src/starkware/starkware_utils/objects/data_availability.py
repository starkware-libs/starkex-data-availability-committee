import dataclasses
from typing import List

from onchain_data_availability.onchain_data_parser import parse_onchain_data
from onchain_data_availability.reconstruct_state_from_onchain_data import ReconstructedData
from starkware.starkware_utils.commitment_tree.merkle_tree.merkle_tree import MerkleTree
from starkware.starkware_utils.objects.starkex_state import VaultState
from starkware.storage.storage import FactFetchingContext


@dataclasses.dataclass
class StarkexReconstructedData(ReconstructedData):
    """
    Data that was reconstructed from the on-chain data.
    Members:
    :param vault_tree: The reconstructed vault tree.
    :type vault_tree: Merkle Tree
    """

    vault_tree: MerkleTree

    async def apply_update(
        self, batch_onchain_data: List[int], ffc: FactFetchingContext
    ) -> "StarkexReconstructedData":
        """
        Returns the resulted vault tree after applying batch transactions.
        """
        onchain_data = parse_onchain_data(values=batch_onchain_data)
        modifications = [
            (
                vault_update.vault_id,
                VaultState(
                    stark_key=vault_update.stark_key,
                    token=vault_update.token,
                    balance=vault_update.balance,
                ),
            )
            for vault_update in onchain_data.updates
        ]
        updated_vault_tree = await self.vault_tree.update(ffc=ffc, modifications=modifications)
        return StarkexReconstructedData(vault_tree=updated_vault_tree)

    def get_state_tree(self) -> MerkleTree:
        return self.vault_tree
