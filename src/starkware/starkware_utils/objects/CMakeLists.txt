
python_lib(starkware_starkex_constants_lib
    PREFIX starkware/starkware_utils/objects

    FILES
    starkex_constants.py
)

python_lib(starkware_starkex_utils_lib
    PREFIX starkware/starkware_utils/objects

    FILES
    availability.py
    starkex_state.py

    LIBS
    starkware_commitment_tree_facts_lib
    starkware_dataclasses_utils_lib
    starkware_error_handling_lib
    starkware_storage_lib
    starkware_utils_lib
    pip_marshmallow_dataclass
)
