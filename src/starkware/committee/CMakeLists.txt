python_lib(starkware_committee_config_lib
    FILES
    committee/committee_config.py

    LIBS
    starkware_config_utils_lib
    starkware_dataclasses_utils_lib
    pip_marshmallow
    pip_marshmallow_dataclass
)

python_lib(starkware_committee_lib
    FILES
    committee/__init__.py
    committee/availability_gateway_client.py
    committee/batch_info.json
    committee/committee/__init__.py
    committee/committee/__main__.py
    committee/committee/committee.py
    committee/custom_validation.py
    committee/dump_state/__init__.py
    committee/dump_state/__main__.py
    committee/dump_state/dump_state.py
    committee/dump_trees_utils.py
    committee/dump_trees/__init__.py
    committee/dump_trees/__main__.py
    committee/dump_trees/dump_trees.py
    committee/load_state/__init__.py
    committee/load_state/__main__.py
    committee/load_state/load_state.py
    committee/load_trees_from_file/__init__.py
    committee/load_trees_from_file/__main__.py
    committee/load_trees_from_file/load_trees_from_file.py

    LIBS
    starkware_committee_config_lib
    starkware_config_utils_lib
    starkware_crypto_lib
    starkware_dataclasses_utils_lib
    starkware_dump_tree_diff_lib
    starkware_error_handling_lib
    starkware_python_utils_lib
    starkware_starkex_constants_lib
    starkware_storage_aerospike_lib
    starkware_storage_lib
    starkware_utils_lib
    pip_requests
)

python_venv(starkex_committee_venv
    PYTHON python3.7
    LIBS
    starkware_committee_lib
    perpetual_public_business_logic_lib
    starkware_starkex_utils_lib
)

python_exe(starkex_committee_exe
    VENV starkex_committee_venv
    MODULE committee.committee
)

# Tests.

full_python_test(starkware_committee_test
    PYTHON python3.7
    TESTED_MODULES committee

    FILES
    committee/committee_test.py
    committee/load_dump_end_to_end_test.py

    LIBS
    starkware_committee_config_lib
    starkware_committee_lib
    starkware_crypto_lib
    starkware_python_test_utils_lib
    starkware_starkex_constants_lib
    starkware_starkex_utils_lib
    starkware_storage_test_utils_lib
    starkware_utils_lib
    pip_fastecdsa
    pip_pytest
    pip_pytest_asyncio
)
