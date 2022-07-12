import argparse
import asyncio
import json
import logging
import os
import subprocess
import tarfile
from tempfile import TemporaryDirectory

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


async def main():
    parser = argparse.ArgumentParser(
        description="""\
Loads all the state associated with a certain batch to the database.
    """
    )
    logging.basicConfig()
    parser.add_argument(
        "--data_file",
        type=argparse.FileType("rb"),
        default="state.bz2",
        help="Name of the input file",
    )
    parser.add_argument(
        "--config_file", type=str, help="path to config file with storage configuration"
    )
    parser.add_argument(
        "--n_processes", type=int, default=5, help="number of processes used to load the state"
    )
    args = parser.parse_args()

    config_file = f"-config_file={args.config_file}" if args.config_file else None
    with tarfile.open(fileobj=args.data_file) as tar, TemporaryDirectory() as tmp_dir:
        tar.extractall(tmp_dir)

        info_file = os.path.join(tmp_dir, "info.json")
        orders_n_processes = len(json.load(open(info_file, "r"))["order_subtree_roots"])

        queue = asyncio.Queue()
        for node_idx in range(orders_n_processes, 2 * orders_n_processes):
            file_name = f"orders_{node_idx}.csv"
            queue.put_nowait(
                (
                    [
                        "python",
                        "-m",
                        "committee.load_trees_from_file",
                        "orders",
                        f"--node_idx={node_idx}",
                        config_file,
                        "--orders_file",
                    ],
                    file_name,
                )
            )

        queue.put_nowait(
            (
                [
                    "python",
                    "-m",
                    "committee.load_trees_from_file",
                    "vaults",
                    config_file,
                    "--vaults_file",
                ],
                "vaults.csv",
            )
        )

        completed = 0
        total = queue.qsize()

        async def worker_func():
            while True:
                cmd, filename = await queue.get()
                filepath = os.path.join(tmp_dir, filename)
                try:
                    p = await asyncio.create_subprocess_exec(*filter(None, cmd + [filepath]))
                    ret_code = await p.wait()
                    if ret_code:
                        exit(ret_code)

                    nonlocal completed
                    completed += 1
                    print(f"{completed}/{total} tasks were completed")

                finally:
                    queue.task_done()

        # Run several workers to process the nodes.
        workers = asyncio.gather(*(worker_func() for _ in range(args.n_processes)))

        await queue.join()

        workers.cancel()
        try:
            await workers
        except asyncio.CancelledError:
            pass

        assert queue.empty()

        subprocess.check_call(
            filter(
                None,
                [
                    "python",
                    "-m",
                    "committee.load_trees_from_file",
                    "info",
                    config_file,
                    "--set_next_batch_id",
                    "--info_file",
                    info_file,
                ],
            )
        )


def run_main():
    asyncio.run(main())
