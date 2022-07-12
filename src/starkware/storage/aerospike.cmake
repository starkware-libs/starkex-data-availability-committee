python_lib(starkware_storage_aerospike_lib
    PREFIX starkware/storage

    FILES
    aerospike_lock.py
    aerospike_storage_threadpool.py

    LIBS
    starkware_python_utils_lib
    starkware_storage_lib
    pip_aerospike
)
