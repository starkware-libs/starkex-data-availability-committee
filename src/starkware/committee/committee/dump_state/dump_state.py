import argparse
import asyncio
import logging
import math
import os
import tarfile
from tempfile import TemporaryDirectory

from committee.dump_trees_utils import is_power_of_2

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


async def main():
    parser = argparse.ArgumentParser(
        description="""\
Dumps all the state associated with a certain batch from database.
    """
    )
    logging.basicConfig()
    parser.add_argument(
        "--data_file", type=str, default="state.bz2", help="Name of the output file"
    )
    parser.add_argument("--batch_id", type=int, required=True, help="Batch id")
    parser.add_argument(
        "--config_file", type=str, help="path to config file with storage configuration"
    )
    parser.add_argument(
        "--n_processes", type=int, default=5, help="number of processes used to dump the state"
    )
    parser.add_argument(
        "--n_order_dump_tasks",
        type=int,
        default=4,
        help="number of tasks used to dump the order tree",
    )
    args = parser.parse_args()

    # We use 1 process to dump the vaults tree and n_order_dump_tasks processes to dump the orders.
    # The batch_info dump is ignored in the process count.
    assert is_power_of_2(args.n_order_dump_tasks), "n_order_dump_tasks must be a power of two."

    config_file = f"-config_file={args.config_file}" if args.config_file else None

    with tarfile.open(args.data_file, mode="w:bz2") as tar, TemporaryDirectory() as tmp_dir:
        queue = asyncio.Queue()
        for node_idx in range(args.n_order_dump_tasks, 2 * args.n_order_dump_tasks):
            file_name = f"orders_{node_idx}.csv"
            queue.put_nowait(
                (
                    [
                        "python",
                        "-m",
                        "committee.dump_trees",
                        "orders",
                        f"--batch_id={args.batch_id}",
                        f"--order_node_idx={node_idx}",
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
                    "committee.dump_trees",
                    "vaults",
                    f"--batch_id={args.batch_id}",
                    config_file,
                    "--vaults_file",
                ],
                "vaults.csv",
            )
        )

        queue.put_nowait(
            (
                [
                    "python",
                    "-m",
                    "committee.dump_trees",
                    "info",
                    f"--batch_id={args.batch_id}",
                    f"--order_node_depth={int(math.log(args.n_order_dump_tasks, 2))}",
                    config_file,
                    "--dump_info_file",
                ],
                "info.json",
            )
        )

        completed = 0
        total = queue.qsize()

        async def worker_func():
            while True:
                cmd, filename = await queue.get()
                filepath = os.path.join(tmp_dir, filename)
                cmd = list(filter(None, cmd + [filepath]))
                try:
                    task = await asyncio.create_subprocess_exec(*cmd)
                    ret_code = await task.wait()
                    if ret_code:
                        # Avoid exiting here to avoid interrupting successful tasks.
                        print(f'failed to run: {" ".join(cmd)}')
                    else:
                        tar.add(filepath, arcname=filename)
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


def run_main():
    asyncio.run(main())
