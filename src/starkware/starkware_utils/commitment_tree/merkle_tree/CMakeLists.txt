python_lib(starkware_utils_merkle_tree_test_utils_lib
    PREFIX starkware/starkware_utils/commitment_tree/merkle_tree

    FILES
    test_utils.py

    LIBS
    starkware_storage_lib
    starkware_utils_lib
)

python_lib(starkware_dump_tree_diff_lib
    PREFIX starkware/starkware_utils/commitment_tree/merkle_tree

    FILES
    dump_tree_diff.py

    LIBS
    starkware_storage_lib
    starkware_utils_lib
)
