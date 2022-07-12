import asyncio
import logging
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import field
from typing import Any, Dict, NamedTuple, Optional, Tuple, Type

import marshmallow.fields as mfields
import marshmallow_dataclass
from marshmallow.decorators import pre_load
from web3 import eth

from committee.availability_gateway_client import AvailabilityGatewayClient
from committee.committee_config import CommitteeConfig
from committee.custom_validation import is_valid
from starkware.crypto.signature.fast_pedersen_hash import pedersen_hash_func
from starkware.starkware_utils.availability_claim import hash_availability_claim
from starkware.starkware_utils.commitment_tree.binary_fact_tree import BinaryFactTree
from starkware.starkware_utils.commitment_tree.leaf_fact import LeafFact
from starkware.starkware_utils.config_base import fetch_service_config, load_config
from starkware.starkware_utils.executor import service_executor
from starkware.starkware_utils.marshmallow_dataclass_fields import BytesAsHex
from starkware.starkware_utils.objects.availability import (
    BatchDataResponseBase,
    StateBase,
    StateUpdateBase,
)
from starkware.starkware_utils.objects.starkex_constants import OBSOLETE_ORDER_TREE_ROOT_STR
from starkware.starkware_utils.validated_dataclass import ValidatedMarshmallowDataclass
from starkware.storage.dict_storage import CachedStorage
from starkware.storage.storage import FactFetchingContext, HashFunctionType, Storage

logger = logging.getLogger(__name__)
CommitteeObjectInfo = NamedTuple(
    "CommitteeObjectInfo",
    [("state_class", Type[StateBase]), ("tree_height", int), ("tree_class", Type[BinaryFactTree])],
)


@marshmallow_dataclass.dataclass(frozen=True)
class CommitteeBatchInfo(ValidatedMarshmallowDataclass):
    merkle_roots: dict = field(
        metadata=dict(
            marshmallow_field=mfields.Dict(keys=mfields.String, values=BytesAsHex(required=True))
        )
    )
    sequence_number: int

    @pre_load
    def from_v2(self, data: Dict[str, Any], many: bool, **kwargs) -> Dict[str, Any]:
        if "merkle_roots" not in data and "vaults_root" in data and "orders_root" in data:
            data["merkle_roots"] = {"vault": data["vaults_root"], "order": data["orders_root"]}
            del data["vaults_root"]
            del data["orders_root"]
        return data


class Committee:
    def __init__(
        self,
        config: CommitteeConfig,
        private_key: str,
        storage: Storage,
        fact_storage: Storage,
        hash_func: HashFunctionType,
        availability_gateway: AvailabilityGatewayClient,
    ):
        self.storage = storage
        self.fact_storage = CachedStorage(fact_storage, config.fact_storage_cache_size)
        self.hash_func = hash_func
        self.availability_gateway = availability_gateway
        self.account = eth.Account.from_key(private_key)
        self.polling_interval = config.polling_interval
        self.validate_orders = config.validate_orders
        self.validate_rollup: Optional[bool] = config.validate_rollup
        self.dump_batch: bool = config.dump_batch
        self.set_committee_objects(config)
        if self.validate_orders:
            logger.info("Full validation mode enabled.")
        else:
            logger.info("Partial validation mode enabled - orders not validated.")
        self.batch_data_response_class = BatchDataResponseBase.get_class_by_path(
            path=config.batch_data_response_class_path
        )

        self.stopped = False

    def stop(self):
        self.stopped = True

    @staticmethod
    def next_batch_id_key() -> bytes:
        return "committee_next_batch_id".encode("ascii")

    @staticmethod
    def committee_batch_info_key(batch_id: int) -> bytes:
        return f"new_committee_batch_info:{batch_id}".encode("ascii")

    @staticmethod
    def old_committee_batch_info_key(batch_id: int) -> bytes:
        return f"committee_batch_info:{batch_id}".encode("ascii")

    @staticmethod
    async def get_committee_batch_info(
        storage: Storage, batch_id: int
    ) -> Optional[CommitteeBatchInfo]:
        """
        Reads and returns the CommitteeBatchInfo from the given storage. If it doesn't exist,
        returns None.
        From StarkEx version 4.5 and onwards, the DB key used to store this object has changed. For
        backwards compatability, if the object does not exist under the updated key, an attempt is
        made to read the object from the old key. If successful, the object is copied to the new key
        and returned.
        """
        batch_info = await storage.get_value(
            key=Committee.committee_batch_info_key(batch_id=batch_id)
        )
        if batch_info is None:
            logger.warning(
                f"CommitteeBatchInfo not found at index {batch_id}, checking using old DB key..."
            )
            batch_info = await storage.get_value(
                key=Committee.old_committee_batch_info_key(batch_id=batch_id)
            )
            if batch_info is not None:
                logger.warning(
                    f"CommitteeBatchInfo found at index {batch_id} under old key, re-writing to "
                    "new key."
                )
                await storage.set_value(
                    key=Committee.committee_batch_info_key(batch_id=batch_id), value=batch_info
                )
        return None if batch_info is None else CommitteeBatchInfo.deserialize(data=batch_info)

    @staticmethod
    async def get_committee_batch_info_or_fail(
        storage: Storage, batch_id: int
    ) -> CommitteeBatchInfo:
        """
        Reads and returns the CommitteeBatchInfo from the given storage. If it doesn't exist, raises
        an exception.
        """
        batch_info = await Committee.get_committee_batch_info(storage=storage, batch_id=batch_id)
        assert batch_info is not None, f"No batch info at index {batch_id} exists in storage."
        return batch_info

    def set_committee_objects(self, config: CommitteeConfig):
        """
        Creates a list of committee objects with their tree heights.
        """
        self.committee_objects_info: Dict[str, CommitteeObjectInfo] = {}
        for item in config.committee_objects:
            state_class = StateBase.get_class_by_path(path=item["class"])
            tree_class = BinaryFactTree.from_config(import_path=item["tree_class"])
            self.committee_objects_info[item["name"]] = CommitteeObjectInfo(
                state_class=state_class,
                tree_height=int(item["merkle_height"]),
                tree_class=tree_class,
            )

    async def _compute_empty_root(self, object_name: str) -> bytes:
        """
        Computes and stores an empty tree for the given object. Returns the root of the empty tree.
        """
        ffc = FactFetchingContext(self.fact_storage, self.hash_func)
        state_object_class, tree_height, tree_class = self.committee_objects_info[object_name]
        leaf_fact = state_object_class.empty()
        assert isinstance(leaf_fact, LeafFact)
        tree = await tree_class.empty_tree(ffc=ffc, height=tree_height, leaf_fact=leaf_fact)
        return tree.root

    async def compute_initial_batch_info(self):
        """
        Computes a CommitteeBatchInfo with empty trees and sequence_number == -1.
        """
        roots_list = await asyncio.gather(
            *(
                self._compute_empty_root(object_name=object_name)
                for object_name in self.committee_objects_info
            )
        )
        initial_batch_info = CommitteeBatchInfo(
            merkle_roots=dict(zip(self.committee_objects_info.keys(), roots_list)),
            sequence_number=-1,
        ).serialize()
        await self.storage.set_value(
            key=self.committee_batch_info_key(-1), value=initial_batch_info
        )

    async def validate_data_availability(
        self,
        batch_id: int,
        state_update: StateUpdateBase,
        validate_orders: bool,
        validate_rollup: Optional[bool],
    ) -> Tuple[str, str]:
        """
        Given the state_update for a new batch, verify data availability by computing
        the roots for the new batch.

        The new roots are stored in storage along with the sequence number
        and a signed availability_claim is sent to the availability gateway.

        The validate_rollup flag must be one of three values: True, False or None (the None value is
        for backwards compatability).
        In any case, the rollup tree is not part of the hashed availability claim - it is only for
        (optional) rollup state sync verification.
        """

        logger.info(f"Processing batch {batch_id}")
        logger.info(f"Using batch {state_update.prev_batch_id} as reference")

        prev_batch_info = await Committee.get_committee_batch_info_or_fail(
            storage=self.storage, batch_id=state_update.prev_batch_id
        )

        # If the rollup tree does not exist in the roots dict, initialize an empty rollup tree.
        # Note that upgrading an old committee in a system that has a non-empty rollup tree will
        # cause errors.
        if (
            "rollup_vault" in self.committee_objects_info
            and "rollup_vault" not in prev_batch_info.merkle_roots
        ):
            prev_batch_info.merkle_roots["rollup_vault"] = await self._compute_empty_root(
                object_name="rollup_vault"
            )
            logger.warning("Initialized empty rollup tree.")

        async def compute_merkle_root(ffc, object_name, state_update):
            _, tree_height, tree_class = self.committee_objects_info[object_name]
            object_state_update = state_update.objects[object_name]
            tree = tree_class(root=prev_batch_info.merkle_roots[object_name], height=tree_height)
            tree = await tree.update(ffc, object_state_update.items())
            return object_name, tree.root

        # Only compute the orders root / rollup root if respective validation is active.
        validated_object_names = list(self.committee_objects_info.keys())
        if not validate_orders:
            validated_object_names.remove("order")
        if validate_rollup is False:
            validated_object_names.remove("rollup_vault")
        elif validate_rollup is None:
            assert "rollup_vault" not in validated_object_names

        # Verify consistency of data with roots.
        ffc = FactFetchingContext(self.fact_storage, self.hash_func)
        roots_list = await asyncio.gather(
            *(
                compute_merkle_root(ffc, object_name, state_update)
                for object_name in validated_object_names
            )
        )
        # roots_list is a list of tuples (object_name, root).
        roots_dict = dict(roots_list)

        for object_name in self.committee_objects_info:
            expected_root = state_update.roots[object_name]
            # Migration from StarkEx4.0 to StarkEx4.5 completely replaces the order tree topology;
            # old state updates contain obsolete order tree roots (can no longer be verified using
            # current order tree topology). Old state updates are marked with specific roots to
            # indicate they are obsolete.
            if object_name == "order" and expected_root == OBSOLETE_ORDER_TREE_ROOT_STR:
                logger.info(
                    f"The {object_name} root on the state update is obsolete; blindly signing."
                )
                continue
            if object_name in validated_object_names:
                root = roots_dict[object_name]
                assert root.hex() == expected_root, f"{object_name} root mismatch"
                logger.info(f"Verified {object_name} root: 0x{expected_root}")
            else:
                if object_name != "rollup_vault":
                    logger.info(f"Blindly signing {object_name} root: 0x{expected_root}")

        # Always prefer the root computed by the committee over the root reported in the state
        # update; only roots not computed by the committee should be taken from the state update.
        # The state update may contain an obsolete order root (post migration to StarkEx version
        # 4.5, the availability gateway may be unable to compute the correct order root for batches
        # created before version 4.5), but the committee can correctly compute it.
        # The roots variable contains all roots from the state update, and roots_dict contains all
        # roots computed by the committee.
        roots = {key: bytes.fromhex(value) for key, value in state_update.roots.items()}
        roots.update(roots_dict)
        batch_info = CommitteeBatchInfo(
            merkle_roots=roots, sequence_number=prev_batch_info.sequence_number + 1
        )

        await self.storage.set_value(
            self.committee_batch_info_key(batch_id), batch_info.serialize()
        )

        logger.info(f"Signing batch with sequence number {batch_info.sequence_number}")

        availability_claim = self.compute_hash_availability_claim(batch_info=batch_info)
        signature = eth.Account._sign_hash(availability_claim, self.account.key).signature.hex()
        return signature, availability_claim.hex()

    def compute_hash_availability_claim(self, batch_info: CommitteeBatchInfo):
        """
        hash_availability_claim() inputs are:
        - Tree root and tree height for the committee objects, barring the rollup vault tree root.
        - Batch sequence number.
        As the rollup data is provided publically, there is no need to hash the rollup vault tree
        root as part of the availability claim.
        """
        hash_object_names = [name for name in self.committee_objects_info if name != "rollup_vault"]
        assert len(hash_object_names) == 2, f"Unexpected number of objects: {hash_object_names}."
        vaults_object_name = "vault" if "vault" in hash_object_names else "position"
        assert "order" in hash_object_names
        return hash_availability_claim(
            vaults_root=batch_info.merkle_roots[vaults_object_name],
            vaults_height=self.committee_objects_info[vaults_object_name].tree_height,
            trades_root=batch_info.merkle_roots["order"],
            trades_height=self.committee_objects_info["order"].tree_height,
            seq_num=batch_info.sequence_number,
        )

    async def run(self):
        # Compute the initial batch info in any case as it may be used for aborted batches.
        await self.compute_initial_batch_info()

        next_batch_id = await self.storage.get_int(Committee.next_batch_id_key())
        if next_batch_id is None:
            next_batch_id = 0
            await self.storage.set_int(Committee.next_batch_id_key(), next_batch_id)

        while not self.stopped:
            try:
                availability_update = await self.availability_gateway.get_batch_data(
                    batch_id=next_batch_id, validate_rollup=self.validate_rollup
                )
                if availability_update is None:
                    logger.info(f"Waiting for batch {next_batch_id}")
                    await asyncio.sleep(self.polling_interval)
                    continue
                assert await is_valid(
                    state_update=availability_update,
                    storage=self.storage,
                    batch_id=next_batch_id,
                    availability_gateway=self.availability_gateway,
                    dump_batch=self.dump_batch,
                ), "Third party validation failed."
                signature, availability_claim = await self.validate_data_availability(
                    batch_id=next_batch_id,
                    state_update=availability_update,
                    validate_orders=self.validate_orders,
                    validate_rollup=self.validate_rollup,
                )
                await self.availability_gateway.send_signature(
                    next_batch_id, signature, self.account.address, availability_claim
                )
                next_batch_id += 1
                await self.storage.set_int(Committee.next_batch_id_key(), next_batch_id)
            except Exception as ex:
                logger.error(f"Got an exception: {ex}")
                logger.error("Exception details", exc_info=True)
                await asyncio.sleep(self.polling_interval)


async def main():
    config = load_config()
    committee_config = CommitteeConfig.load(data=fetch_service_config(config))

    private_key_path = os.environ.get("PRIVATE_KEY_PATH", committee_config.private_key_path)
    with open(private_key_path, "r") as private_key_file:
        # Read private_key from file (remove '\n' from end of line).
        private_key = private_key_file.read().rstrip()

    storage = await Storage.create_instance_from_config(config=config["STORAGE"])
    availability_gateway_endpoint = os.environ.get(
        "AVAILABILITY_GW_ENDPOINT", committee_config.availability_gateway_endpoint
    )
    certificates_path = os.environ.get("CERTIFICATES_PATH", committee_config.certificates_path)

    batch_data_response_class = BatchDataResponseBase.get_class_by_path(
        path=committee_config.batch_data_response_class_path
    )

    availability_gateway = AvailabilityGatewayClient(
        gateway_url=availability_gateway_endpoint,
        certificates_path=certificates_path,
        batch_data_response_class=batch_data_response_class,
        http_request_timeout=committee_config.http_request_timeout,
    )
    logger.info(f"Using {availability_gateway_endpoint} as an availability gateway")

    committee = Committee(
        config=committee_config,
        private_key=private_key,
        storage=storage,
        fact_storage=storage,
        hash_func=pedersen_hash_func,
        availability_gateway=availability_gateway,
    )
    with service_executor(ProcessPoolExecutor()):
        await committee.run()


def run_main():
    sys.exit(asyncio.run(main()))
