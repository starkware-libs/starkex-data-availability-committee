include(CMakeLists_common.txt)

add_subdirectory(commitment_tree)
add_subdirectory(objects)

python_lib(starkware_utils_lib
    PREFIX starkware/starkware_utils

    FILES
    availability_claim.py
    commitment_tree/binary_fact_tree.py
    commitment_tree/binary_fact_tree_da_utils.py
    commitment_tree/binary_fact_tree_node.py
    commitment_tree/calculation.py
    commitment_tree/merkle_tree/merkle_calculation_node.py
    commitment_tree/merkle_tree/merkle_tree.py
    commitment_tree/merkle_tree/merkle_tree_node.py
    commitment_tree/merkle_tree/traverse_tree.py
    commitment_tree/patricia_tree/nodes.py
    commitment_tree/patricia_tree/patricia_tree.py
    commitment_tree/patricia_tree/virtual_calculation_node.py
    commitment_tree/patricia_tree/virtual_patricia_node.py
    commitment_tree/update_tree.py
    executor.py
    http_handler.py
    subsequence.py

    LIBS
    starkware_config_utils_lib
    starkware_custom_dict_utils_lib
    starkware_dataclasses_utils_lib
    starkware_error_handling_lib
    starkware_python_utils_lib
    starkware_serializability_utils_lib
    pip_aiohttp
    pip_marshmallow_dataclass
    pip_web3
)
