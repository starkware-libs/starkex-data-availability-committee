import asyncio
import concurrent.futures as futures
import hashlib
import logging
import time
from abc import abstractmethod
from functools import wraps
from typing import Any, Callable, List, Optional, Tuple, TypeVar

import aerospike

from starkware.python.utils import from_bytes, to_bytes
from starkware.storage.storage import Storage

logger = logging.getLogger(__name__)

TCallable = TypeVar("TCallable", bound=Callable)

RETRY_COUNT = 3

RETRY_COUNT = 10


def run_with_retry_on_timeouts(
    count: int, fail_value: Any = None, reraise_on_fail: bool = False
) -> Callable[[TCallable], TCallable]:
    def _retrying(func: TCallable):
        @wraps(func)
        def wrapped(*args, **kwargs):
            for n_retries in range(1, count + 1):
                try:
                    return func(*args, **kwargs)
                except aerospike.exception.TimeoutError:
                    logger.debug(
                        f"Write to storage timed out, retry: {n_retries}, out of {count}.",
                        exc_info=(
                            n_retries == count
                        ),  # Only print traceback if all retries failed.
                    )

                    if n_retries == count and reraise_on_fail:
                        raise

                    time.sleep(1)

            return fail_value

        return wrapped

    return _retrying


def create_client(hosts: List[str], use_services_alternate: bool, policies: Optional[dict] = None):
    aerospike_hosts: List[Tuple[str, int]] = []
    for host in hosts:
        hostname, port = host.split(":")
        aerospike_hosts.append((hostname, int(port)))

    config = dict(
        hosts=aerospike_hosts,
        use_services_alternate=use_services_alternate,
    )
    if policies is not None:
        config["policies"] = policies

    while True:
        try:
            client = aerospike.client(config).connect()
            logger.info(f"Aerospike client is ready, nodes in cluster: {client.get_nodes()}")
            return client
        except (aerospike.exception.ClientError, aerospike.exception.TimeoutError):
            logger.warning("Aerospike client not ready, will try again in 1 sec.", exc_info=True)
            time.sleep(1)


class AerospikeThreadedStorageBase(Storage):
    def __init__(
        self,
        hosts: List[str],
        namespace: str,
        aero_set: str,
        use_services_alternate: Optional[bool] = None,
        max_workers: Optional[int] = None,
        custom_write_policy: Optional[dict] = None,
    ):

        if use_services_alternate is None:
            use_services_alternate = False

        if max_workers is None:
            max_workers = 32

        assert len(aero_set) <= 63, "Set name too long."
        self.aero_set = aero_set
        self.namespace = namespace

        # Default policy.
        policies = dict(
            write=dict(
                key=aerospike.POLICY_KEY_SEND,
                total_timeout=0,  # Set no timeout.
            ),
            read=dict(
                total_timeout=0,  # Set no timeout.
            ),
        )

        self.pool = futures.ThreadPoolExecutor(max_workers)
        if custom_write_policy is not None:
            policies["write"].update(custom_write_policy)

        self.client = create_client(
            hosts=hosts, use_services_alternate=use_services_alternate, policies=policies
        )
        self.setnx_write_policy = dict(exists=aerospike.POLICY_EXISTS_CREATE, **policies["write"])
        self.set_write_policy = dict(exists=aerospike.POLICY_EXISTS_IGNORE, **policies["write"])
        self.set_read_policy = dict(**policies["read"])

    async def setnx_value(self, key: bytes, value: bytes) -> bool:
        try:
            return await asyncio.get_event_loop().run_in_executor(
                self.pool, self.sync_set, key, value, self.setnx_write_policy
            )
        except aerospike.exception.RecordExistsError:
            return False

    async def set_value(self, key: bytes, value: bytes):
        await asyncio.get_event_loop().run_in_executor(
            self.pool, self.sync_set, key, value, self.set_write_policy
        )

    async def get_value(self, key: bytes) -> Optional[bytes]:
        val = await asyncio.get_event_loop().run_in_executor(
            self.pool, self.sync_get, key, self.set_read_policy
        )
        return val

    async def del_value(self, key: bytes):
        await asyncio.get_event_loop().run_in_executor(self.pool, self.sync_del, key)

    @abstractmethod
    def sync_set(self, key: bytes, value: bytes, write_policy: dict) -> bool:
        pass

    @abstractmethod
    def sync_get(self, key: bytes, read_policy: dict) -> Optional[bytes]:
        pass

    @abstractmethod
    def sync_del(self, key: bytes) -> bool:
        pass


class AerospikeStorage(AerospikeThreadedStorageBase):
    def __init__(
        self,
        hosts: List[str],
        namespace: str,
        aero_set: str,
        use_services_alternate: Optional[bool] = None,
        max_workers: Optional[int] = None,
    ):
        super().__init__(hosts, namespace, aero_set, use_services_alternate, max_workers)

    @run_with_retry_on_timeouts(reraise_on_fail=True, count=RETRY_COUNT)
    def sync_set(self, key: bytes, value: bytes, policy: dict) -> bool:
        try:
            self.client.put(
                (self.namespace, self.aero_set, bytearray(key)),
                {"value": bytearray(value)},
                policy=policy,
            )
            return True
        except aerospike.exception.RecordExistsError:
            return False
        except aerospike.exception.RecordTooBig:
            logger.error(
                f"Attempting to write an object that is too big to storage. "
                f"Object key: {key!r}, object size: {len(value)}B."
            )
            raise

    @run_with_retry_on_timeouts(reraise_on_fail=True, count=RETRY_COUNT)
    def sync_get(self, key: bytes, policy: dict) -> Optional[bytes]:
        try:
            _, _, record = self.client.get(
                (self.namespace, self.aero_set, bytearray(key)), policy=policy
            )
        except aerospike.exception.RecordNotFound:
            return None
        return bytes(record["value"])

    @run_with_retry_on_timeouts(fail_value=False, count=RETRY_COUNT)
    def sync_del(self, key: bytes) -> bool:
        try:
            self.client.remove((self.namespace, self.aero_set, bytearray(key)))
            return True
        except aerospike.exception.RecordNotFound:
            return False


class AerospikeLayeredStorage(AerospikeThreadedStorageBase):
    """
    Aerospike storage implementation using buckets of type map. Values written using this storage
    object are bucketed using {index_bits} bits of a hash on the key. Each bucket is an aerospike
    map object from the real key to the value.
    The reason we use this is to reduce the total amount of keys in aerospike, because they take
    RAM. When the values are small, this is inefficient. For maximum efficiency, the bucketing
    should give values of size ~ 10KB.
    """

    def __init__(
        self,
        hosts: List[str],
        namespace: str,
        aero_set: str,
        use_services_alternate: Optional[bool] = None,
        max_workers: Optional[int] = None,
        index_bits: Optional[int] = None,
    ):
        super().__init__(hosts, namespace, aero_set, use_services_alternate, max_workers)
        if index_bits is None:
            index_bits = 28
        self.index_bits = index_bits

    def get_bucket_key(self, key: bytes):
        # Returns the first self.index_bits bits of the hash of a key.
        x = from_bytes(hashlib.sha1(key).digest(), byte_order="little")
        return to_bytes(x & ((1 << self.index_bits) - 1), length=8, byte_order="little")

    @run_with_retry_on_timeouts(reraise_on_fail=True, count=RETRY_COUNT)
    def sync_get(self, key: bytes, policy: dict) -> Optional[bytes]:
        try:
            bucket_key = (self.namespace, self.aero_set, bytearray(self.get_bucket_key(key)))
            res = self.client.map_get_by_key(
                bucket_key, "value", bytearray(key), aerospike.MAP_RETURN_KEY_VALUE, policy=policy
            )
            if len(res) == 0:
                return None
            # res must be of length 1 here.
            _, res_value = res[0]
            return bytes(res_value)
        except aerospike.exception.RecordNotFound:
            return None

    @run_with_retry_on_timeouts(reraise_on_fail=True, count=RETRY_COUNT)
    def sync_set(self, key: bytes, value: bytes, policy: dict):
        try:
            bucket_key = (self.namespace, self.aero_set, bytearray(self.get_bucket_key(key)))
            self.client.map_put(
                bucket_key, "value", bytearray(key), bytearray(value), policy=policy
            )
            return True
        except aerospike.exception.RecordExistsError:
            return False

    @run_with_retry_on_timeouts(fail_value=False, count=RETRY_COUNT)
    def sync_del(self, key: bytes) -> bool:
        try:
            bucket_key = (self.namespace, self.aero_set, bytearray(self.get_bucket_key(key)))
            res = self.client.map_remove_by_key(
                bucket_key, "value", bytearray(key), aerospike.MAP_RETURN_KEY_VALUE
            )
            return len(res) > 0
        except aerospike.exception.RecordNotFound:
            return False
