import asyncio
import csv
import logging
import os
import re
import subprocess
import tempfile
import time

import pytest
import requests
import yaml

from committee.dump_trees import dump_vaults_tree
from starkware.crypto.signature.fast_pedersen_hash import pedersen_hash_func
from starkware.python.utils import to_bytes
from starkware.starkware_utils.commitment_tree.binary_fact_tree import BinaryFactDict
from starkware.starkware_utils.commitment_tree.merkle_tree.merkle_tree import MerkleTree
from starkware.starkware_utils.objects.starkex_state import VaultState
from starkware.storage.storage import FactFetchingContext, Storage

logger = logging.getLogger(__name__)


async def dump_vaults_tree_test(storage_config):
    """
    The test dumps a vault tree with a specific root.
    After dumping all the data it goes over the dump and collects the information
    that is associated with a specific vault_id.
    It checks that the vault information is consistent with the hash of the corresponding leaf,
    and that the authentication path generated from the dumped data is correct.
    """

    root = 0x0109BBC8B615885CAFD7A2120E2F3C3218ABDE7B01A0ABE5F772AB32DFE55861
    height = 31
    vault_id = 2136494259

    storage = await Storage.create_instance_from_config(config=storage_config)
    ffc = FactFetchingContext(storage, pedersen_hash_func)
    tree = MerkleTree(root=to_bytes(root), height=height)

    nodes_file = tempfile.TemporaryFile(mode="r+")
    vaults_file = tempfile.TemporaryFile(mode="r+")
    await dump_vaults_tree(ffc, tree, nodes_file, vaults_file)

    vault_hash = None

    nodes_file.seek(0)
    reader = csv.reader(nodes_file, delimiter=",")

    index = vault_id + 2 ** height
    # Compute the indices of all the nodes in the authentication path.
    authentication_path_indices = [(index >> (height - 1 - depth)) ^ 1 for depth in range(height)]
    path = {}

    # Go over the csv file and collect the following hashes:
    # 1. vault_hash corresponding to vault_id
    # 2. hashes of nodes in the authentication path for the vault in 1.
    for row in reader:
        row_number = int(row[0])
        if row_number == index:
            vault_hash = row[1]
        if row_number in authentication_path_indices:
            path[row_number] = row[1]

    assert sorted(path.keys()) == authentication_path_indices

    vault_data = None

    vaults_file.seek(0)
    reader = csv.reader(vaults_file, delimiter=",")
    for row in reader:
        row_number = int(row[0])
        if row_number == index - 2 ** 31:
            vault_data = VaultState(int(row[1]), int(row[2]), int(row[3]))

    assert isinstance(vault_data, VaultState)
    computed_vault_hash = (vault_data._hash(pedersen_hash_func)).hex()
    assert computed_vault_hash == vault_hash, f"{computed_vault_hash} != {vault_hash}"

    sorted_path = [root for _index, root in sorted(path.items(), reverse=True)]

    # Build expected path.
    # In the tree indexes are zero-based, while here the vaults start at offset 2**args.height.
    authentication_index = index - 2 ** tree.height
    facts: BinaryFactDict = {}
    await tree.get_leaves(ffc=ffc, indices=[authentication_index], fact_cls=VaultState, facts=facts)

    expected_path = []
    directions = map(int, bin(authentication_index)[2:])
    for direction, (right, left) in zip(directions, facts.values()):
        node = left if direction == 0 else right
        expected_path.append(to_bytes(node).hex())

    assert sorted_path == list(reversed(expected_path))


def dump_logs(workdir, report_dir):
    os.makedirs(report_dir, exist_ok=True)
    log_file = tempfile.NamedTemporaryFile(
        prefix="log_", suffix=".txt", delete=False, dir=report_dir
    )
    print(f"Writing docker logs into {os.path.abspath(log_file.name)}")
    subprocess.call(["docker-compose", "logs", "--no-color"], cwd=workdir, stdout=log_file)


def wait_for_validation(required_validations, timeout=60):
    start_time = time.time()
    n_batches_validated = 0
    while n_batches_validated < required_validations:
        time.sleep(1)
        if time.time() - start_time > timeout:
            raise TimeoutError
        try:
            resp = requests.request(
                "GET", "http://localhost:9414/availability_gateway/get_num_validated_batches"
            )
        except requests.exceptions.ConnectionError as ex:
            logger.error(f"Failed to query gateway. Exception: {ex}")
            logger.debug("Exception details", exc_info=True)
            continue

        if resp.status_code != 200:
            logger.info(f"got code {resp.status_code}:, {resp.text}")
            continue

        n_batches_validated = int(resp.text)


def test_committee(flavor):
    """
    Tests the committee against a mock implementation of the availability verifier.
    """
    build_path = os.path.join(os.path.dirname(__file__), f"../../../build/{flavor}")
    workdir = os.path.join(build_path, "src/starkware/committee")
    report_dir = os.path.join(build_path, f"../reports/{flavor}")
    try:
        if os.environ.get("USE_LOCAL_DOCKERS") != "1":
            subprocess.check_call(["docker-compose", "down"], cwd=workdir)
            subprocess.check_call(["docker-compose", "build"], cwd=workdir)
            subprocess.check_call(["docker-compose", "up", "-d", "--force-recreate"], cwd=workdir)

        wait_for_validation(3, timeout=120)

        # Test dump_db flow after the db is initialized and before we bring it down.
        config = yaml.safe_load(
            open(os.path.join(workdir, "starkex_committee_docker/artifacts/", "config.yml"), "r")
        )
        # Use a non-standard port to avoid conflicts.
        config["STORAGE"]["config"]["hosts"] = ["localhost:3000"]
        asyncio.run(dump_vaults_tree_test(config["STORAGE"]))

    finally:
        dump_logs(workdir, report_dir)
        subprocess.call(["docker-compose", "logs", "mock-availability-gateway"], cwd=workdir)
        if os.environ.get("USE_LOCAL_DOCKERS") != "1":
            subprocess.call(["docker-compose", "down"], cwd=workdir)


@pytest.mark.skip(
    reason="Need to update escape scripts for use with patricia tree; "
    "see issue https://123starkex.atlassian.net/browse/VER4-80"
)
def test_load_dump_state(flavor):
    """
    Tests the committee against a mock implementation of the availability verifier.
    """
    build_path = os.path.join(os.path.dirname(__file__), f"../../../build/{flavor}")
    workdir = os.path.join(build_path, "src/starkware/committee")
    report_dir = os.path.join(build_path, f"../reports/{flavor}")
    try:
        subprocess.check_call(["docker-compose", "down"], cwd=workdir)
        subprocess.check_call(["docker-compose", "build"], cwd=workdir)
        subprocess.check_call(["docker-compose", "up", "-d", "--force-recreate"], cwd=workdir)

        wait_for_validation(1)

        with tempfile.NamedTemporaryFile() as dump_file:
            # Dump batch 0.
            subprocess.check_call(
                [
                    "python",
                    "-m",
                    "committee.dump_state",
                    "--batch_id=0",
                    f"--data_file={dump_file.name}",
                ]
            )

            # Stop all services.
            subprocess.check_call(["docker-compose", "down"], cwd=workdir)

            # Load the committee-aerospike and preload it with batch 0.
            subprocess.check_call(
                ["docker-compose", "up", "-d", "committee-aerospike"], cwd=workdir
            )

            subprocess.check_call(
                ["python", "-m", "committee.load_state", f"--data_file={dump_file.name}"]
            )

        subprocess.check_call(
            ["docker-compose", "up", "-d", "--no-recreate", "committee"], cwd=workdir
        )

        wait_for_validation(1)
        output = subprocess.check_output(["docker-compose", "logs", "committee"], cwd=workdir)
        m = re.search(br"Signing batch with sequence number (?P<seq_num>\d+)\n", output)
        assert (
            m is not None and m["seq_num"] == b"1"
        ), "Expecting the first signed batch to have the sequence number 1"
    finally:
        dump_logs(workdir, report_dir)
        subprocess.check_call(["docker-compose", "up", "-d", "committee-aerospike"], cwd=workdir)
        subprocess.call(["docker-compose", "down"], cwd=workdir)
